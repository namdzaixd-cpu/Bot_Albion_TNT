-- Additive financial state and atomic stored procedures. No operational rows are overwritten.

ALTER TABLE public.core_credited
    ADD COLUMN IF NOT EXISTS recipient_id text,
    ADD COLUMN IF NOT EXISTS emoji_key text,
    ADD COLUMN IF NOT EXISTS core_name text,
    ADD COLUMN IF NOT EXISTS core_display text,
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'legacy_unknown',
    ADD COLUMN IF NOT EXISTS reconciled_by text,
    ADD COLUMN IF NOT EXISTS reconciliation_evidence text,
    ADD COLUMN IF NOT EXISTS reconciled_at timestamptz,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

UPDATE public.core_credited
SET status = 'legacy_unknown'
WHERE status IS NULL OR status NOT IN (
    'legacy_unknown', 'pending', 'unknown', 'retryable', 'credited',
    'reverting', 'refund_unknown', 'reverted'
);

ALTER TABLE public.core_credited
    DROP CONSTRAINT IF EXISTS core_credited_status_check;
ALTER TABLE public.core_credited
    ADD CONSTRAINT core_credited_status_check
    CHECK (status IN (
        'legacy_unknown', 'pending', 'unknown', 'retryable', 'credited',
        'reverting', 'refund_unknown', 'reverted'
    ));

ALTER TABLE public.sp_metadata
    ADD COLUMN IF NOT EXISTS last_update_ts timestamp without time zone;

DO $$
DECLARE
    legacy_row record;
    parsed_timestamp timestamp without time zone;
BEGIN
    FOR legacy_row IN
        SELECT id, last_update
        FROM public.sp_metadata
        WHERE last_update_ts IS NULL
          AND last_update ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$'
    LOOP
        BEGIN
            parsed_timestamp := legacy_row.last_update::timestamp without time zone;
        EXCEPTION WHEN OTHERS THEN
            CONTINUE;
        END;
        UPDATE public.sp_metadata
        SET last_update_ts = parsed_timestamp
        WHERE id = legacy_row.id;
    END LOOP;
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
    RETURN jsonb_build_object('claimed', false, 'entry', NULL);
END;
$$;

CREATE OR REPLACE FUNCTION public.transition_core_credit(
    p_message_id text,
    p_expected_status text,
    p_next_status text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    changed integer;
BEGIN
    IF NOT (
        (p_expected_status = 'pending' AND p_next_status IN ('credited', 'unknown'))
        OR (p_expected_status = 'credited' AND p_next_status = 'reverting')
        OR (p_expected_status = 'reverting' AND p_next_status IN ('reverted', 'refund_unknown'))
    ) THEN
        RETURN false;
    END IF;

    UPDATE public.core_credited
    SET status = p_next_status,
        credited_at = CASE WHEN p_next_status = 'credited' THEN now() ELSE credited_at END,
        updated_at = now()
    WHERE message_id = p_message_id AND status = p_expected_status;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END;
$$;

CREATE OR REPLACE FUNCTION public.reconcile_core_credit(
    p_message_id text,
    p_decision text,
    p_actor_id text,
    p_evidence text,
    p_guild_id text DEFAULT NULL,
    p_recipient_id text DEFAULT NULL,
    p_emoji_key text DEFAULT NULL,
    p_core_name text DEFAULT NULL,
    p_core_display text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    ledger public.core_credited%ROWTYPE;
    next_status text;
BEGIN
    IF NULLIF(btrim(p_actor_id), '') IS NULL OR NULLIF(btrim(p_evidence), '') IS NULL THEN
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
    ELSIF p_decision = 'not_paid' AND ledger.status IN ('pending', 'unknown', 'legacy_unknown') THEN
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
        reconciliation_evidence = p_evidence,
        reconciled_at = now(),
        updated_at = now()
    WHERE message_id = p_message_id
    RETURNING * INTO ledger;
    RETURN jsonb_build_object('status', ledger.status, 'entry', to_jsonb(ledger));
END;
$$;

CREATE OR REPLACE FUNCTION public.apply_siphoned_import(p_rows jsonb)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    item jsonb;
    player text;
    delta integer;
    row_timestamp timestamp without time zone;
    locked_watermark timestamp without time zone;
    max_applied timestamp without time zone;
    last_display text;
    applied_count integer := 0;
    skipped_count integer := 0;
BEGIN
    IF p_rows IS NULL OR jsonb_typeof(p_rows) <> 'array' THEN
        RAISE EXCEPTION 'SP import rows must be a JSON array';
    END IF;

    INSERT INTO public.sp_metadata (id, last_update)
    VALUES (1, 'Chưa có dữ liệu')
    ON CONFLICT (id) DO NOTHING;
    SELECT last_update_ts, last_update
    INTO locked_watermark, last_display
    FROM public.sp_metadata
    WHERE id = 1
    FOR UPDATE;
    max_applied := locked_watermark;

    FOR item IN SELECT value FROM jsonb_array_elements(p_rows)
    LOOP
        BEGIN
            player := NULLIF(btrim(item->>'player_name'), '');
            delta := NULLIF(item->>'amount', '')::integer;
            row_timestamp := NULLIF(item->>'log_timestamp', '')::timestamp without time zone;
        EXCEPTION WHEN OTHERS THEN
            skipped_count := skipped_count + 1;
            CONTINUE;
        END;
        IF player IS NULL OR delta IS NULL OR row_timestamp IS NULL THEN
            skipped_count := skipped_count + 1;
            CONTINUE;
        END IF;
        IF locked_watermark IS NOT NULL AND row_timestamp <= locked_watermark THEN
            skipped_count := skipped_count + 1;
            CONTINUE;
        END IF;

        INSERT INTO public.user_economy AS existing (user_id, silver_pieces, updated_at)
        VALUES (player, delta, now())
        ON CONFLICT (user_id) DO UPDATE
        SET silver_pieces = COALESCE(existing.silver_pieces, 0) + EXCLUDED.silver_pieces,
            updated_at = now();
        INSERT INTO public.sp_transactions (player_name, amount, log_timestamp)
        VALUES (player, delta, row_timestamp);
        applied_count := applied_count + 1;
        IF max_applied IS NULL OR row_timestamp > max_applied THEN
            max_applied := row_timestamp;
        END IF;
    END LOOP;

    IF max_applied IS DISTINCT FROM locked_watermark THEN
        last_display := to_char(max_applied, 'YYYY-MM-DD HH24:MI:SS');
        UPDATE public.sp_metadata
        SET last_update = last_display, last_update_ts = max_applied, updated_at = now()
        WHERE id = 1;
    END IF;
    RETURN jsonb_build_object(
        'applied', applied_count,
        'skipped', skipped_count,
        'last_update', COALESCE(last_display, 'Chưa có dữ liệu')
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.adjust_siphoned_points(
    p_adjustments jsonb,
    p_only_existing boolean DEFAULT false
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    item jsonb;
    player text;
    delta integer;
    affected integer;
    current_balance integer;
    result_rows jsonb := '[]'::jsonb;
BEGIN
    IF p_adjustments IS NULL OR jsonb_typeof(p_adjustments) <> 'array' THEN
        RAISE EXCEPTION 'SP adjustments must be a JSON array';
    END IF;
    INSERT INTO public.sp_metadata (id, last_update)
    VALUES (1, 'Chưa có dữ liệu')
    ON CONFLICT (id) DO NOTHING;
    PERFORM 1 FROM public.sp_metadata WHERE id = 1 FOR UPDATE;

    FOR item IN SELECT value FROM jsonb_array_elements(p_adjustments)
    LOOP
        player := NULLIF(btrim(item->>'player_name'), '');
        delta := NULLIF(item->>'amount', '')::integer;
        IF player IS NULL OR delta IS NULL THEN
            RAISE EXCEPTION 'invalid SP adjustment';
        END IF;
        IF p_only_existing THEN
            UPDATE public.user_economy AS economy
            SET silver_pieces = COALESCE(economy.silver_pieces, 0) + delta, updated_at = now()
            WHERE economy.user_id = player;
            GET DIAGNOSTICS affected = ROW_COUNT;
            IF affected = 0 THEN
                result_rows := result_rows || jsonb_build_array(jsonb_build_object(
                    'user_id', player, 'applied', false, 'silver_pieces', NULL
                ));
                CONTINUE;
            END IF;
        ELSE
            INSERT INTO public.user_economy AS existing (user_id, silver_pieces, updated_at)
            VALUES (player, delta, now())
            ON CONFLICT (user_id) DO UPDATE
            SET silver_pieces = COALESCE(existing.silver_pieces, 0) + EXCLUDED.silver_pieces,
                updated_at = now();
        END IF;
        SELECT economy.silver_pieces INTO current_balance
        FROM public.user_economy AS economy
        WHERE economy.user_id = player;
        result_rows := result_rows || jsonb_build_array(jsonb_build_object(
            'user_id', player, 'applied', true, 'silver_pieces', current_balance
        ));
    END LOOP;
    RETURN result_rows;
END;
$$;

CREATE OR REPLACE FUNCTION public.delete_siphoned_users(p_user_ids text[])
RETURNS text[]
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    deleted_ids text[];
BEGIN
    INSERT INTO public.sp_metadata (id, last_update)
    VALUES (1, 'Chưa có dữ liệu')
    ON CONFLICT (id) DO NOTHING;
    PERFORM 1 FROM public.sp_metadata WHERE id = 1 FOR UPDATE;
    WITH deleted AS (
        DELETE FROM public.user_economy AS economy
        WHERE economy.user_id = ANY(p_user_ids)
        RETURNING economy.user_id
    )
    SELECT COALESCE(array_agg(deleted.user_id), ARRAY[]::text[])
    INTO deleted_ids
    FROM deleted;
    RETURN deleted_ids;
END;
$$;

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
    DELETE FROM public.user_economy;
    UPDATE public.sp_metadata
    SET last_update = 'N/A', last_update_ts = NULL, updated_at = now()
    WHERE id = 1;
    RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_core_credit(text, text, text, text, integer, text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.transition_core_credit(text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reconcile_core_credit(text, text, text, text, text, text, text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.apply_siphoned_import(jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.adjust_siphoned_points(jsonb, boolean) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.delete_siphoned_users(text[]) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reset_siphoned_points() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_core_credit(text, text, text, text, integer, text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.transition_core_credit(text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.reconcile_core_credit(text, text, text, text, text, text, text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.apply_siphoned_import(jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.adjust_siphoned_points(jsonb, boolean) TO service_role;
GRANT EXECUTE ON FUNCTION public.delete_siphoned_users(text[]) TO service_role;
GRANT EXECUTE ON FUNCTION public.reset_siphoned_points() TO service_role;
