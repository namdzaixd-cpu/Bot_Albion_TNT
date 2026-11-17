-- Additive financial integrity round 2. Replaces RPC definitions from 20261004_financial.sql;
-- never rewrites existing sp_transactions / core_credited rows.

ALTER TABLE public.sp_transactions ADD COLUMN IF NOT EXISTS reason text;
CREATE INDEX IF NOT EXISTS idx_sp_log_identity
    ON public.sp_transactions(log_timestamp, player_name, amount);
ALTER TABLE public.core_credited
    ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 1;

-- SP import contract: the file is a complete original export (every line of each
-- second). Rows older than the watermark second are skipped, rows newer are applied,
-- and rows in the watermark second are applied only beyond the per-identity count
-- (log_timestamp, player, reason, amount) already stored in sp_transactions, so a
-- supplemental row or a genuinely identical second line is kept while a replay is not.
-- History rows written before this migration have reason NULL: a player/amount/second group that
-- contains any is deduped by its total row count instead of per reason.
-- shortcut: Albion log times are naive UTC, so "future" allows one day of clock/zone
-- skew; tighten if the log source is ever proven to be exact UTC.
CREATE OR REPLACE FUNCTION public.apply_siphoned_import(p_rows jsonb)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    item jsonb;
    player text;
    reason_text text;
    delta integer;
    row_ts timestamp without time zone;
    stored_watermark timestamp without time zone;
    watermark timestamp without time zone;
    max_applied timestamp without time zone;
    upper_bound timestamp without time zone := (now() AT TIME ZONE 'UTC') + interval '1 day';
    boundary_known boolean := false;
    base_counts jsonb := '{}'::jsonb;
    seen_counts jsonb := '{}'::jsonb;
    identity text;
    group_key text;
    seen_n integer;
    last_display text;
    applied_count integer := 0;
    skipped_count integer := 0;
    future_count integer := 0;
    duplicate_count integer := 0;
BEGIN
    IF p_rows IS NULL OR jsonb_typeof(p_rows) <> 'array' THEN
        RAISE EXCEPTION 'SP import rows must be a JSON array';
    END IF;

    INSERT INTO public.sp_metadata (id, last_update)
    VALUES (1, 'Chưa có dữ liệu')
    ON CONFLICT (id) DO NOTHING;
    SELECT last_update_ts, last_update
    INTO stored_watermark, last_display
    FROM public.sp_metadata
    WHERE id = 1
    FOR UPDATE;

    watermark := stored_watermark;
    IF watermark IS NULL THEN
        -- Reset by the old code cleared the scalar but kept history: never replay it.
        SELECT max(log_timestamp) INTO watermark
        FROM public.sp_transactions
        WHERE log_timestamp <= upper_bound;
    END IF;
    IF watermark IS NOT NULL AND watermark > upper_bound THEN
        RAISE EXCEPTION 'SP watermark % is in the future; an operator must repair it before importing', watermark;
    END IF;
    max_applied := watermark;
    -- Without stored rows for the watermark second its counts are unknown: stay strict.
    IF watermark IS NOT NULL THEN
        boundary_known := EXISTS (
            SELECT 1 FROM public.sp_transactions WHERE log_timestamp = watermark
        );
    END IF;

    FOR item IN SELECT value FROM jsonb_array_elements(p_rows)
    LOOP
        BEGIN
            player := NULLIF(btrim(item->>'player_name'), '');
            delta := NULLIF(item->>'amount', '')::integer;
            row_ts := NULLIF(item->>'log_timestamp', '')::timestamp without time zone;
            reason_text := COALESCE(btrim(item->>'reason'), '');
        EXCEPTION WHEN OTHERS THEN
            skipped_count := skipped_count + 1;
            CONTINUE;
        END;
        IF player IS NULL OR delta IS NULL OR row_ts IS NULL THEN
            skipped_count := skipped_count + 1;
            CONTINUE;
        END IF;
        IF row_ts > upper_bound THEN
            future_count := future_count + 1;
            CONTINUE;
        END IF;

        IF watermark IS NOT NULL THEN
            IF row_ts < watermark THEN
                skipped_count := skipped_count + 1;
                CONTINUE;
            ELSIF row_ts = watermark THEN
                IF NOT boundary_known THEN
                    skipped_count := skipped_count + 1;
                    CONTINUE;
                END IF;
                group_key := jsonb_build_array(player, delta)::text;
                identity := jsonb_build_array(player, reason_text, delta)::text;
                -- Stored counts are read once, before this import inserts anything.
                IF base_counts->>group_key IS NULL THEN
                    base_counts := base_counts || jsonb_build_object(group_key, (
                        SELECT count(*) FROM public.sp_transactions AS tx
                        WHERE tx.log_timestamp = row_ts AND tx.player_name = player AND tx.amount = delta
                    ));
                    base_counts := base_counts || jsonb_build_object('legacy:' || group_key, (
                        SELECT count(*) FROM public.sp_transactions AS tx
                        WHERE tx.log_timestamp = row_ts AND tx.player_name = player AND tx.amount = delta
                          AND tx.reason IS NULL
                    ));
                END IF;
                IF base_counts->>identity IS NULL THEN
                    base_counts := base_counts || jsonb_build_object(identity, (
                        SELECT count(*) FROM public.sp_transactions AS tx
                        WHERE tx.log_timestamp = row_ts AND tx.player_name = player AND tx.amount = delta
                          AND tx.reason = reason_text
                    ));
                END IF;
                -- A group holding legacy rows (reason NULL) cannot attribute them to a reason, so it
                -- dedupes by group total (same player/amount/second, so balances are unaffected by
                -- attribution); every other group dedupes per reason identity.
                IF (base_counts->>('legacy:' || group_key))::integer > 0 THEN
                    identity := group_key;
                END IF;
                seen_n := COALESCE((seen_counts->>identity)::integer, 0) + 1;
                seen_counts := seen_counts || jsonb_build_object(identity, seen_n);
                IF seen_n <= (base_counts->>identity)::integer THEN
                    skipped_count := skipped_count + 1;
                    duplicate_count := duplicate_count + 1;
                    CONTINUE;
                END IF;
            END IF;
        END IF;

        INSERT INTO public.user_economy AS existing (user_id, silver_pieces, updated_at)
        VALUES (player, delta, now())
        ON CONFLICT (user_id) DO UPDATE
        SET silver_pieces = COALESCE(existing.silver_pieces, 0) + EXCLUDED.silver_pieces,
            updated_at = now();
        INSERT INTO public.sp_transactions (player_name, amount, log_timestamp, reason)
        VALUES (player, delta, row_ts, reason_text);
        applied_count := applied_count + 1;
        IF max_applied IS NULL OR row_ts > max_applied THEN
            max_applied := row_ts;
        END IF;
    END LOOP;

    IF applied_count > 0 AND max_applied IS DISTINCT FROM stored_watermark THEN
        last_display := to_char(max_applied, 'YYYY-MM-DD HH24:MI:SS');
        UPDATE public.sp_metadata
        SET last_update = last_display, last_update_ts = max_applied, updated_at = now()
        WHERE id = 1;
    END IF;
    RETURN jsonb_build_object(
        'applied', applied_count,
        'skipped', skipped_count,
        'future', future_count,
        'boundary_duplicates', duplicate_count,
        'last_update', COALESCE(last_display, 'Chưa có dữ liệu')
    );
END;
$$;

-- Atomic legacy snapshot: totals and the parsed watermark commit together, and only
-- into an untouched target (no balances, no history, no watermark).
CREATE OR REPLACE FUNCTION public.import_siphoned_snapshot(
    p_totals jsonb,
    p_last_update text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    item jsonb;
    player text;
    total integer;
    display text := COALESCE(NULLIF(btrim(p_last_update), ''), 'Chưa có dữ liệu');
    snapshot_ts timestamp without time zone;
    imported_count integer := 0;
    stored_watermark timestamp without time zone;
BEGIN
    IF p_totals IS NULL OR jsonb_typeof(p_totals) <> 'array' THEN
        RAISE EXCEPTION 'SP snapshot totals must be a JSON array';
    END IF;
    IF display ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN
        snapshot_ts := display::timestamp without time zone;
        IF snapshot_ts > (now() AT TIME ZONE 'UTC') + interval '1 day' THEN
            RAISE EXCEPTION 'SP snapshot watermark is in the future';
        END IF;
    ELSE
        RAISE EXCEPTION 'SP snapshot needs a last_update log timestamp watermark';
    END IF;

    INSERT INTO public.sp_metadata (id, last_update)
    VALUES (1, 'Chưa có dữ liệu')
    ON CONFLICT (id) DO NOTHING;
    SELECT last_update_ts INTO stored_watermark
    FROM public.sp_metadata WHERE id = 1 FOR UPDATE;
    IF stored_watermark IS NOT NULL
       OR EXISTS (SELECT 1 FROM public.user_economy)
       OR EXISTS (SELECT 1 FROM public.sp_transactions) THEN
        RAISE EXCEPTION 'SP snapshot target is not empty; refusing to import';
    END IF;

    FOR item IN SELECT value FROM jsonb_array_elements(p_totals)
    LOOP
        player := NULLIF(btrim(item->>'player_name'), '');
        total := NULLIF(item->>'amount', '')::integer;
        IF player IS NULL OR total IS NULL THEN
            RAISE EXCEPTION 'invalid SP snapshot row';
        END IF;
        INSERT INTO public.user_economy (user_id, silver_pieces, updated_at)
        VALUES (player, total, now());
        imported_count := imported_count + 1;
    END LOOP;
    IF imported_count = 0 AND snapshot_ts IS NULL THEN
        RAISE EXCEPTION 'SP snapshot has neither totals nor a watermark';
    END IF;

    UPDATE public.sp_metadata
    SET last_update = CASE WHEN snapshot_ts IS NULL THEN display
                           ELSE to_char(snapshot_ts, 'YYYY-MM-DD HH24:MI:SS') END,
        last_update_ts = snapshot_ts,
        updated_at = now()
    WHERE id = 1;
    RETURN jsonb_build_object('imported', imported_count, 'last_update', display);
END;
$$;

-- Reset clears balances only; history and the watermark stay so old exports cannot replay.
CREATE OR REPLACE FUNCTION public.reset_siphoned_points()
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO public.sp_metadata (id, last_update)
    VALUES (1, 'Chưa có dữ liệu')
    ON CONFLICT (id) DO NOTHING;
    PERFORM 1 FROM public.sp_metadata WHERE id = 1 FOR UPDATE;
    DELETE FROM public.user_economy WHERE true;
    RETURN true;
END;
$$;

-- Aggregated in SQL (no row limit); the window is measured in Albion log time (UTC).
CREATE OR REPLACE FUNCTION public.sp_period_totals(p_days integer DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF p_days IS NOT NULL AND p_days <= 0 THEN
        RAISE EXCEPTION 'p_days must be positive';
    END IF;
    RETURN COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object('player_name', totals.player_name, 'total', totals.total)
            ORDER BY totals.total DESC, totals.player_name
        )
        FROM (
            SELECT tx.player_name, SUM(tx.amount)::bigint AS total
            FROM public.sp_transactions AS tx
            WHERE p_days IS NULL
               OR tx.log_timestamp >= (now() AT TIME ZONE 'UTC') - make_interval(days => p_days)
            GROUP BY tx.player_name
        ) AS totals
    ), '[]'::jsonb);
END;
$$;

CREATE OR REPLACE FUNCTION public.claim_core_credit(
    p_message_id text,
    p_guild_id text,
    p_officer_id text,
    p_recipient_id text,
    p_amount integer,
    p_emoji_key text,
    p_core_name text,
    p_core_display text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    claimed_row public.core_credited%ROWTYPE;
BEGIN
    IF NULLIF(btrim(p_message_id), '') IS NULL
       OR NULLIF(btrim(p_guild_id), '') IS NULL
       OR NULLIF(btrim(p_officer_id), '') IS NULL
       OR NULLIF(btrim(p_recipient_id), '') IS NULL
       OR NULLIF(btrim(p_emoji_key), '') IS NULL
       OR NULLIF(btrim(p_core_name), '') IS NULL
       OR NULLIF(btrim(p_core_display), '') IS NULL
       OR p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'invalid Core credit snapshot';
    END IF;

    INSERT INTO public.core_credited (
        message_id, user_id, amount, guild_id, recipient_id, emoji_key,
        core_name, core_display, credited_at, status
    ) VALUES (
        p_message_id, p_officer_id, p_amount, p_guild_id, p_recipient_id,
        p_emoji_key, p_core_name, p_core_display, NULL, 'pending'
    ) ON CONFLICT (message_id) DO NOTHING
    RETURNING * INTO claimed_row;

    IF FOUND THEN
        RETURN jsonb_build_object('claimed', true, 'entry', to_jsonb(claimed_row));
    END IF;

    UPDATE public.core_credited AS ledger
    SET status = 'pending', updated_at = now()
    WHERE ledger.message_id = p_message_id
      AND ledger.status = 'retryable'
      AND ledger.guild_id = p_guild_id
      AND ledger.user_id = p_officer_id
      AND ledger.recipient_id = p_recipient_id
      AND ledger.amount = p_amount
      AND ledger.emoji_key = p_emoji_key
      AND ledger.core_name = p_core_name
      AND ledger.core_display = p_core_display
    RETURNING ledger.* INTO claimed_row;

    IF FOUND THEN
        RETURN jsonb_build_object('claimed', true, 'entry', to_jsonb(claimed_row));
    END IF;

    -- A confirmed refund returned the money, so a fresh reaction is a fresh credit with
    -- the current snapshot. The status predicate makes concurrent re-adds a compare-and-swap.
    UPDATE public.core_credited AS ledger
    SET status = 'pending',
        user_id = p_officer_id,
        recipient_id = p_recipient_id,
        amount = p_amount,
        emoji_key = p_emoji_key,
        core_name = p_core_name,
        core_display = p_core_display,
        credited_at = NULL,
        attempt_count = ledger.attempt_count + 1,
        updated_at = now()
    WHERE ledger.message_id = p_message_id
      AND ledger.status = 'reverted'
      AND ledger.guild_id = p_guild_id
    RETURNING ledger.* INTO claimed_row;

    IF FOUND THEN
        RETURN jsonb_build_object('claimed', true, 'entry', to_jsonb(claimed_row));
    END IF;
    RETURN jsonb_build_object('claimed', false, 'entry', NULL);
END;
$$;

-- not_paid from a still-pending claim needs the operator's acknowledgement that the bot
-- worker is stopped: age alone cannot prove the provider call is no longer in flight.
DROP FUNCTION IF EXISTS public.reconcile_core_credit(text, text, text, text, text, text, text, text, text);
CREATE OR REPLACE FUNCTION public.reconcile_core_credit(
    p_message_id text,
    p_decision text,
    p_actor_id text,
    p_evidence text,
    p_guild_id text DEFAULT NULL,
    p_recipient_id text DEFAULT NULL,
    p_emoji_key text DEFAULT NULL,
    p_core_name text DEFAULT NULL,
    p_core_display text DEFAULT NULL,
    p_worker_quiesced boolean DEFAULT false
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    ledger public.core_credited%ROWTYPE;
    next_status text;
    evidence text := btrim(p_evidence);
BEGIN
    IF NULLIF(btrim(p_actor_id), '') IS NULL OR NULLIF(evidence, '') IS NULL THEN
        RAISE EXCEPTION 'actor and evidence are required';
    END IF;

    SELECT * INTO ledger
    FROM public.core_credited
    WHERE message_id = p_message_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Core ledger row not found';
    END IF;

    IF p_decision = 'paid' AND ledger.status IN ('pending', 'unknown', 'legacy_unknown') THEN
        next_status := 'credited';
    ELSIF p_decision = 'not_paid' AND ledger.status IN ('unknown', 'legacy_unknown') THEN
        next_status := 'retryable';
    ELSIF p_decision = 'not_paid' AND ledger.status = 'pending' THEN
        IF NOT COALESCE(p_worker_quiesced, false) THEN
            RAISE EXCEPTION 'pending Core claim may still have a provider call in flight; stop the bot worker and acknowledge it before not_paid';
        END IF;
        evidence := evidence || ' [worker_quiesced acknowledged]';
        next_status := 'retryable';
    ELSIF p_decision = 'refund_applied' AND ledger.status IN ('reverting', 'refund_unknown') THEN
        next_status := 'reverted';
    ELSIF p_decision = 'refund_not_applied' AND ledger.status IN ('reverting', 'refund_unknown') THEN
        next_status := 'credited';
    ELSE
        RAISE EXCEPTION 'decision is not compatible with ledger status %', ledger.status;
    END IF;
    IF next_status IN ('credited', 'retryable')
       AND (ledger.amount IS NULL OR ledger.amount <= 0) THEN
        RAISE EXCEPTION 'Core ledger amount must be positive before reconciliation';
    END IF;

    IF ledger.status = 'legacy_unknown'
       AND (NULLIF(btrim(p_guild_id), '') IS NULL
            OR NULLIF(btrim(p_recipient_id), '') IS NULL
            OR NULLIF(btrim(p_emoji_key), '') IS NULL
            OR NULLIF(btrim(p_core_name), '') IS NULL
            OR NULLIF(btrim(p_core_display), '') IS NULL) THEN
        RAISE EXCEPTION 'legacy Core rows require guild, recipient, emoji, name, and display snapshots';
    END IF;

    UPDATE public.core_credited
    SET status = next_status,
        guild_id = COALESCE(guild_id, p_guild_id),
        recipient_id = COALESCE(recipient_id, p_recipient_id),
        emoji_key = COALESCE(emoji_key, p_emoji_key),
        core_name = COALESCE(core_name, p_core_name),
        core_display = COALESCE(core_display, p_core_display),
        reconciled_by = p_actor_id,
        credited_at = CASE
            WHEN p_decision = 'paid' THEN now()
            WHEN p_decision = 'not_paid' THEN NULL
            ELSE credited_at
        END,
        reconciliation_evidence = evidence,
        reconciled_at = now(),
        updated_at = now()
    WHERE message_id = p_message_id
    RETURNING * INTO ledger;
    RETURN jsonb_build_object('status', ledger.status, 'entry', to_jsonb(ledger));
END;
$$;

REVOKE ALL ON FUNCTION public.apply_siphoned_import(jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.import_siphoned_snapshot(jsonb, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reset_siphoned_points() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.sp_period_totals(integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.claim_core_credit(text, text, text, text, integer, text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reconcile_core_credit(text, text, text, text, text, text, text, text, text, boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_siphoned_import(jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.import_siphoned_snapshot(jsonb, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.reset_siphoned_points() TO service_role;
GRANT EXECUTE ON FUNCTION public.sp_period_totals(integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_core_credit(text, text, text, text, integer, text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.reconcile_core_credit(text, text, text, text, text, text, text, text, text, boolean) TO service_role;

NOTIFY pgrst, 'reload schema';
