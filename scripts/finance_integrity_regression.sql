-- Isolated regression for 20261117_financial_integrity.sql.
-- Run ONLY against a disposable database that already has the full migration chain applied
-- (schema.sql, migrations/*.sql, migration_security.sql) and the anon/authenticated/service_role
-- roles. Every failed expectation raises; reaching the end means all scenarios passed.
-- Destructive: it truncates SP, Core ledger and registry tables.

-- ── permissions: browser roles cannot reach registry tables or the finance RPCs ─────────
DO $$
DECLARE
    role_name text;
    privilege text;
    signature text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        FOREACH privilege IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE'] LOOP
            IF has_table_privilege(role_name, 'public.member_registry', privilege) THEN
                RAISE EXCEPTION '% has % on member_registry', role_name, privilege;
            END IF;
        END LOOP;
        FOREACH signature IN ARRAY ARRAY[
            'public.apply_siphoned_import(jsonb)',
            'public.import_siphoned_snapshot(jsonb, text)',
            'public.reset_siphoned_points()',
            'public.sp_period_totals(integer)',
            'public.claim_core_credit(text, text, text, text, integer, text, text, text)',
            'public.transition_core_credit(text, text, text)',
            'public.reconcile_core_credit(text, text, text, text, text, text, text, text, text, boolean)'
        ] LOOP
            IF has_function_privilege(role_name, signature, 'EXECUTE') THEN
                RAISE EXCEPTION '% can execute %', role_name, signature;
            END IF;
            IF NOT has_function_privilege('service_role', signature, 'EXECUTE') THEN
                RAISE EXCEPTION 'service_role cannot execute %', signature;
            END IF;
        END LOOP;
    END LOOP;
    -- The replaced 9-argument reconcile overload must be gone (named RPC calls would be ambiguous).
    IF to_regprocedure('public.reconcile_core_credit(text, text, text, text, text, text, text, text, text)') IS NOT NULL THEN
        RAISE EXCEPTION 'old reconcile_core_credit overload still exists';
    END IF;
END;
$$;

-- Actual attempts, not only catalog privilege flags.
DO $$
DECLARE
    role_name text;
    statement text;
    denied integer;
BEGIN
    DELETE FROM public.member_registry;
    INSERT INTO public.member_registry (discord_id, player_id, ign) VALUES ('1', 'p1', 'Seed');
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        denied := 0;
        FOREACH statement IN ARRAY ARRAY[
            'SELECT * FROM public.member_registry',
            'INSERT INTO public.member_registry (discord_id, player_id, ign) VALUES (''2'', ''p2'', ''X'')',
            'UPDATE public.member_registry SET ign = ''Y''',
            'DELETE FROM public.member_registry'
        ] LOOP
            BEGIN
                EXECUTE format('SET LOCAL ROLE %I', role_name);
                EXECUTE statement;
                RESET ROLE;
            EXCEPTION WHEN insufficient_privilege THEN
                RESET ROLE;
                denied := denied + 1;
            END;
        END LOOP;
        IF denied <> 4 THEN
            RAISE EXCEPTION '% was allowed % of 4 registry statements', role_name, 4 - denied;
        END IF;
    END LOOP;
    SET LOCAL ROLE service_role;
    INSERT INTO public.member_registry (discord_id, player_id, ign) VALUES ('3', 'p3', 'Svc');
    UPDATE public.member_registry SET ign = 'Svc2' WHERE discord_id = '3';
    IF (SELECT count(*) FROM public.member_registry) <> 2 THEN
        RAISE EXCEPTION 'service_role cannot read/write registry';
    END IF;
    DELETE FROM public.member_registry;
    RESET ROLE;
END;
$$;

-- ── SP import ────────────────────────────────────────────────────────────────────────
-- same-second supplemental row, identical lines, replay, older rows
DO $$
DECLARE
    result jsonb;
    t1 text := '2026-01-01 10:00:00';
    t2 text := '2026-01-01 10:00:05';
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    SET LOCAL ROLE service_role;

    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t1, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 3 OR result->>'last_update' <> t2 THEN
        RAISE EXCEPTION 'first import wrong: %', result;
    END IF;

    -- identical replay of the full export: nothing applied, 2 identical rows at the boundary kept
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t1, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 0 OR (result->>'boundary_duplicates')::int <> 2 THEN
        RAISE EXCEPTION 'replay applied rows: %', result;
    END IF;

    -- overlapping later export: supplemental C and a third identical B line in the same second
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'C', 'amount', 7, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t1, 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 2 THEN
        RAISE EXCEPTION 'supplemental rows wrong: %', result;
    END IF;
    IF (SELECT silver_pieces FROM public.user_economy WHERE user_id = 'B') <> 15
       OR (SELECT silver_pieces FROM public.user_economy WHERE user_id = 'C') <> 7
       OR (SELECT silver_pieces FROM public.user_economy WHERE user_id = 'A') <> 10 THEN
        RAISE EXCEPTION 'balances wrong after supplemental import';
    END IF;
    IF (SELECT count(*) FROM public.sp_transactions WHERE reason IS NULL) <> 0 THEN
        RAISE EXCEPTION 'reason was not stored';
    END IF;

    -- a newer row listed BEFORE boundary rows must not move the boundary: counts stay per stored watermark
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'Z', 'amount', 1, 'log_timestamp', '2026-01-01 10:00:09', 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', t2, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'Y', 'amount', 2, 'log_timestamp', t2, 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 3 OR (result->>'boundary_duplicates')::int <> 3
       OR result->>'last_update' <> '2026-01-01 10:00:09' THEN
        RAISE EXCEPTION 'newer-first file broke boundary counts: %', result;
    END IF;
    IF (SELECT silver_pieces FROM public.user_economy WHERE user_id = 'B') <> 20 THEN
        RAISE EXCEPTION 'B balance wrong after newer-first import';
    END IF;

    -- a different reason with the same player/amount/second is a different identity
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'Z', 'amount', 1, 'log_timestamp', '2026-01-01 10:00:09', 'reason', 'Other')));
    IF (result->>'applied')::int <> 1 THEN
        RAISE EXCEPTION 'reason is not part of identity: %', result;
    END IF;
    RESET ROLE;
END;
$$;

-- legacy history (reason NULL) at the watermark second still dedupes; unknown boundary stays strict
DO $$
DECLARE
    result jsonb;
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    INSERT INTO public.sp_metadata (id, last_update, last_update_ts)
    VALUES (1, '2026-01-02 00:00:00', '2026-01-02 00:00:00');
    INSERT INTO public.sp_transactions (player_name, amount, log_timestamp)
    VALUES ('L', 4, '2026-01-02 00:00:00');
    SET LOCAL ROLE service_role;
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'L', 'amount', 4, 'log_timestamp', '2026-01-02 00:00:00', 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'M', 'amount', 6, 'log_timestamp', '2026-01-02 00:00:00', 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 1 OR NOT EXISTS (SELECT 1 FROM public.user_economy WHERE user_id = 'M') THEN
        RAISE EXCEPTION 'legacy boundary wrong: %', result;
    END IF;
    RESET ROLE;

    -- watermark without any stored row for that second (snapshot/old reset): strict skip
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy;
    UPDATE public.sp_metadata SET last_update_ts = '2026-01-03 00:00:00', last_update = '2026-01-03 00:00:00';
    SET LOCAL ROLE service_role;
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'N', 'amount', 6, 'log_timestamp', '2026-01-03 00:00:00', 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 0 THEN
        RAISE EXCEPTION 'unknown boundary was not strict: %', result;
    END IF;
    RESET ROLE;
END;
$$;

-- future timestamps: skipped, never advance the watermark; a future stored watermark is loud
DO $$
DECLARE
    result jsonb;
    future_text text := to_char((now() AT TIME ZONE 'UTC') + interval '3 days', 'YYYY-MM-DD HH24:MI:SS');
    ok_text text := to_char((now() AT TIME ZONE 'UTC') + interval '2 hours', 'YYYY-MM-DD HH24:MI:SS');
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    SET LOCAL ROLE service_role;
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'F', 'amount', 1, 'log_timestamp', '2026-01-01 00:00:00', 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'F', 'amount', 9, 'log_timestamp', future_text, 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'G', 'amount', 2, 'log_timestamp', ok_text, 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 2 OR (result->>'future')::int <> 1 OR result->>'last_update' <> ok_text THEN
        RAISE EXCEPTION 'future handling wrong: %', result;
    END IF;
    IF (SELECT silver_pieces FROM public.user_economy WHERE user_id = 'F') <> 1 THEN
        RAISE EXCEPTION 'future row was applied';
    END IF;
    RESET ROLE;

    UPDATE public.sp_metadata SET last_update_ts = (now() AT TIME ZONE 'UTC') + interval '9 days';
    SET LOCAL ROLE service_role;
    BEGIN
        PERFORM public.apply_siphoned_import(jsonb_build_array(
            jsonb_build_object('player_name', 'H', 'amount', 1, 'log_timestamp', '2026-01-01 00:00:00', 'reason', 'x')));
        RAISE EXCEPTION 'future watermark was accepted';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE 'SP watermark%' THEN RAISE; END IF;
    END;
    RESET ROLE;
END;
$$;

-- reset keeps history and watermark, so an old export cannot be counted again
DO $$
DECLARE
    result jsonb;
    export_rows jsonb := jsonb_build_array(
        jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', '2026-01-01 10:00:00', 'reason', 'Deposit'),
        jsonb_build_object('player_name', 'B', 'amount', 5, 'log_timestamp', '2026-01-01 10:00:05', 'reason', 'Deposit'));
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    SET LOCAL ROLE service_role;
    PERFORM public.apply_siphoned_import(export_rows);
    IF NOT public.reset_siphoned_points() THEN RAISE EXCEPTION 'reset failed'; END IF;
    IF (SELECT count(*) FROM public.user_economy) <> 0 THEN RAISE EXCEPTION 'balances survived reset'; END IF;
    IF (SELECT count(*) FROM public.sp_transactions) <> 2 THEN RAISE EXCEPTION 'reset rewrote history'; END IF;
    IF (SELECT last_update_ts FROM public.sp_metadata WHERE id = 1) IS NULL THEN
        RAISE EXCEPTION 'reset cleared the watermark';
    END IF;
    result := public.apply_siphoned_import(export_rows);
    IF (result->>'applied')::int <> 0 OR (SELECT count(*) FROM public.user_economy) <> 0 THEN
        RAISE EXCEPTION 'old export replayed after reset: %', result;
    END IF;
    RESET ROLE;

    -- the old reset cleared the scalar but left history: the next import must not replay it
    UPDATE public.sp_metadata SET last_update_ts = NULL;
    SET LOCAL ROLE service_role;
    result := public.apply_siphoned_import(export_rows);
    IF (result->>'applied')::int <> 0 THEN
        RAISE EXCEPTION 'history was replayed when the scalar watermark was null: %', result;
    END IF;
    RESET ROLE;
END;
$$;

-- snapshot: atomic totals + parsed watermark, populated target rejected, bad row rolls everything back
DO $$
DECLARE
    result jsonb;
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    SET LOCAL ROLE service_role;
    BEGIN
        PERFORM public.import_siphoned_snapshot(jsonb_build_array(
            jsonb_build_object('player_name', 'S1', 'amount', 3),
            jsonb_build_object('player_name', 'S2', 'amount', 'oops')), '2026-01-01 00:00:00');
        RAISE EXCEPTION 'bad snapshot row was accepted';
    EXCEPTION WHEN raise_exception OR invalid_text_representation THEN
        IF SQLERRM LIKE 'bad snapshot%' THEN RAISE; END IF;
    END;
    IF EXISTS (SELECT 1 FROM public.user_economy) THEN RAISE EXCEPTION 'partial snapshot committed'; END IF;

    result := public.import_siphoned_snapshot(jsonb_build_array(
        jsonb_build_object('player_name', 'S1', 'amount', 3),
        jsonb_build_object('player_name', 'S2', 'amount', 4)), '2026-01-01 00:00:00');
    IF (result->>'imported')::int <> 2
       OR (SELECT last_update_ts FROM public.sp_metadata WHERE id = 1) <> '2026-01-01 00:00:00'::timestamp THEN
        RAISE EXCEPTION 'snapshot result wrong: %', result;
    END IF;
    BEGIN
        PERFORM public.import_siphoned_snapshot(jsonb_build_array(
            jsonb_build_object('player_name', 'S3', 'amount', 1)), '2026-01-05 00:00:00');
        RAISE EXCEPTION 'populated target accepted';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE 'SP snapshot target is not empty%' THEN RAISE; END IF;
    END;
    -- a snapshot watermark with no stored rows keeps its boundary strict
    result := public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'S1', 'amount', 3, 'log_timestamp', '2026-01-01 00:00:00', 'reason', 'Deposit')));
    IF (result->>'applied')::int <> 0 THEN RAISE EXCEPTION 'snapshot boundary replayed: %', result; END IF;
    RESET ROLE;
END;
$$;

-- placeholder watermark with non-empty totals is rejected before anything is written
DO $$
DECLARE
    placeholder text;
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    SET LOCAL ROLE service_role;
    FOREACH placeholder IN ARRAY ARRAY['N/A', 'Chưa có dữ liệu', '', 'garbage'] LOOP
        BEGIN
            PERFORM public.import_siphoned_snapshot(
                jsonb_build_array(jsonb_build_object('player_name', 'S1', 'amount', 3)), placeholder);
            RAISE EXCEPTION 'snapshot accepted watermark %', placeholder;
        EXCEPTION WHEN raise_exception THEN
            IF SQLERRM NOT LIKE 'SP snapshot needs%' THEN RAISE; END IF;
        END;
    END LOOP;
    RESET ROLE;
    IF EXISTS (SELECT 1 FROM public.user_economy) OR EXISTS (SELECT 1 FROM public.sp_metadata) THEN
        RAISE EXCEPTION 'rejected snapshot left balances or metadata behind';
    END IF;
END;
$$;

-- one legacy (reason NULL) row is one wildcard for the whole player/amount/second group
DO $$
DECLARE
    result jsonb;
    t text := '2026-02-01 00:00:00';
    r1 jsonb := jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t, 'reason', 'R1');
    r2 jsonb := jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t, 'reason', 'R2');
    r3 jsonb := jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t, 'reason', 'R3');
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    INSERT INTO public.sp_metadata (id, last_update, last_update_ts) VALUES (1, t, t::timestamp);
    INSERT INTO public.sp_transactions (player_name, amount, log_timestamp) VALUES ('A', 10, t::timestamp);
    SET LOCAL ROLE service_role;
    result := public.apply_siphoned_import(jsonb_build_array(r1, r2));
    IF (result->>'applied')::int <> 1 THEN RAISE EXCEPTION 'legacy wildcard reused per reason: %', result; END IF;
    result := public.apply_siphoned_import(jsonb_build_array(r1, r2));
    IF (result->>'applied')::int <> 0 THEN RAISE EXCEPTION 'legacy replay applied: %', result; END IF;
    result := public.apply_siphoned_import(jsonb_build_array(r3, r2, r1));
    IF (result->>'applied')::int <> 1 THEN RAISE EXCEPTION 'new reason / reordered file wrong: %', result; END IF;
    result := public.apply_siphoned_import(jsonb_build_array(r3, r2, r1, r1));
    IF (result->>'applied')::int <> 1 THEN RAISE EXCEPTION 'duplicate multiplicity wrong: %', result; END IF;
    IF (SELECT silver_pieces FROM public.user_economy WHERE user_id = 'A') <> 30 THEN
        RAISE EXCEPTION 'legacy group balance wrong';
    END IF;
    IF (SELECT count(*) FROM public.sp_transactions WHERE reason IS NULL) <> 1 THEN
        RAISE EXCEPTION 'legacy row was rewritten';
    END IF;
    RESET ROLE;
END;
$$;

-- migration-first rollout: an old bot (no reason) followed by the new bot must not double-count
DO $$
DECLARE
    result jsonb;
    t text := '2026-03-01 00:00:00';
    old_row jsonb := jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t);
    new_row jsonb := jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t, 'reason', 'Deposit');
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    SET LOCAL ROLE service_role;
    PERFORM public.apply_siphoned_import(jsonb_build_array(old_row, old_row));
    IF (SELECT count(*) FROM public.sp_transactions WHERE reason IS NULL) <> 2 THEN
        RAISE EXCEPTION 'missing reason was not stored as NULL';
    END IF;
    result := public.apply_siphoned_import(jsonb_build_array(new_row, new_row));
    IF (result->>'applied')::int <> 0 THEN RAISE EXCEPTION 'old-format rows re-applied: %', result; END IF;
    result := public.apply_siphoned_import(jsonb_build_array(
        new_row, new_row, jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t, 'reason', 'Other')));
    IF (result->>'applied')::int <> 1 THEN RAISE EXCEPTION 'supplemental reason wrong: %', result; END IF;
    result := public.apply_siphoned_import(jsonb_build_array(
        new_row, new_row, jsonb_build_object('player_name', 'A', 'amount', 10, 'log_timestamp', t, 'reason', 'Other')));
    IF (result->>'applied')::int <> 0
       OR (SELECT silver_pieces FROM public.user_economy WHERE user_id = 'A') <> 30 THEN
        RAISE EXCEPTION 'replay doubled balances: %', result;
    END IF;
    -- blank reason is also NULL; a non-empty reason is preserved
    PERFORM public.apply_siphoned_import(jsonb_build_array(
        jsonb_build_object('player_name', 'B', 'amount', 1, 'log_timestamp', '2026-03-02 00:00:00', 'reason', '  '),
        jsonb_build_object('player_name', 'B', 'amount', 1, 'log_timestamp', '2026-03-02 00:00:01', 'reason', 'Deposit')));
    IF (SELECT count(*) FROM public.sp_transactions WHERE player_name = 'B' AND reason IS NULL) <> 1
       OR (SELECT count(*) FROM public.sp_transactions WHERE player_name = 'B' AND reason = 'Deposit') <> 1 THEN
        RAISE EXCEPTION 'blank/non-empty reason storage wrong';
    END IF;
    RESET ROLE;
END;
$$;

-- >1000 players aggregate without truncation; window uses log time (UTC)
DO $$
DECLARE
    result jsonb;
BEGIN
    DELETE FROM public.sp_transactions; DELETE FROM public.user_economy; DELETE FROM public.sp_metadata;
    INSERT INTO public.sp_transactions (player_name, amount, log_timestamp, reason)
    SELECT 'P' || n, n, (now() AT TIME ZONE 'UTC') - interval '1 day', 'Deposit'
    FROM generate_series(1, 1500) AS n;
    INSERT INTO public.sp_transactions (player_name, amount, log_timestamp, reason)
    VALUES ('P1', 100000, (now() AT TIME ZONE 'UTC') - interval '40 days', 'Deposit'),
           ('P1', -1, (now() AT TIME ZONE 'UTC') - interval '2 days', 'Withdrawal'),
           ('Old', 5, (now() AT TIME ZONE 'UTC') - interval '400 days', 'Deposit');
    -- inserted_at is "now" for all of them: only log_timestamp may decide the window
    SET LOCAL ROLE service_role;
    result := public.sp_period_totals(30);
    IF jsonb_array_length(result) <> 1500 THEN RAISE EXCEPTION 'truncated aggregate: %', jsonb_array_length(result); END IF;
    IF result->0->>'player_name' <> 'P1500' OR (result->0->>'total')::bigint <> 1500 THEN
        RAISE EXCEPTION 'ordering wrong: %', result->0;
    END IF;
    IF (SELECT (e->>'total')::bigint FROM jsonb_array_elements(result) e WHERE e->>'player_name' = 'P1') <> 0 THEN
        RAISE EXCEPTION '40-day-old row leaked into 30d window or negative row lost';
    END IF;
    IF jsonb_array_length(public.sp_period_totals(NULL)) <> 1501 THEN RAISE EXCEPTION 'all-time aggregate wrong'; END IF;
    RESET ROLE;
END;
$$;

-- ── CoreBank ledger ──────────────────────────────────────────────────────────────────
DO $$
DECLARE
    result jsonb;
    key text := '900:green';
BEGIN
    DELETE FROM public.core_credited;
    INSERT INTO public.guild_config (guild_id) VALUES ('g'), ('other-guild') ON CONFLICT DO NOTHING;
    SET LOCAL ROLE service_role;
    result := public.claim_core_credit(key, 'g', 'off1', 'rec', 100, 'green', 'Green', 'G');
    IF NOT (result->>'claimed')::boolean THEN RAISE EXCEPTION 'first claim failed'; END IF;
    IF (public.claim_core_credit(key, 'g', 'off1', 'rec', 100, 'green', 'Green', 'G')->>'claimed')::boolean THEN
        RAISE EXCEPTION 'pending claim was claimed twice';
    END IF;

    -- not_paid on a pending claim needs the worker-stopped acknowledgement
    BEGIN
        PERFORM public.reconcile_core_credit(key, 'not_paid', 'op', 'looked at provider');
        RAISE EXCEPTION 'not_paid accepted for pending without acknowledgement';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE 'pending Core claim%' THEN RAISE; END IF;
    END;
    IF (SELECT status FROM public.core_credited WHERE message_id = key) <> 'pending' THEN
        RAISE EXCEPTION 'refused reconcile changed status';
    END IF;
    result := public.reconcile_core_credit(key, 'not_paid', 'op', 'bot stopped, provider shows none',
        p_worker_quiesced => true);
    IF result->>'status' <> 'retryable'
       OR (result->'entry'->>'reconciliation_evidence') NOT LIKE '%worker_quiesced acknowledged%' THEN
        RAISE EXCEPTION 'acknowledged not_paid wrong: %', result;
    END IF;

    -- unknown stays reconcilable without acknowledgement (worker already finished)
    PERFORM public.claim_core_credit(key, 'g', 'off1', 'rec', 100, 'green', 'Green', 'G');
    IF NOT public.transition_core_credit(key, 'pending', 'unknown') THEN RAISE EXCEPTION 'to unknown failed'; END IF;
    IF public.reconcile_core_credit(key, 'not_paid', 'op', 'evidence')->>'status' <> 'retryable' THEN
        RAISE EXCEPTION 'unknown not_paid failed';
    END IF;
    -- retryable requires the same snapshot
    IF (public.claim_core_credit(key, 'g', 'off2', 'rec', 100, 'green', 'Green', 'G')->>'claimed')::boolean THEN
        RAISE EXCEPTION 'retryable claimed with another officer';
    END IF;
    IF NOT (public.claim_core_credit(key, 'g', 'off1', 'rec', 100, 'green', 'Green', 'G')->>'claimed')::boolean THEN
        RAISE EXCEPTION 'retryable not re-claimed';
    END IF;

    IF public.transition_core_credit(key, 'pending', 'retryable') THEN RAISE EXCEPTION 'pending->retryable allowed'; END IF;
    IF public.transition_core_credit(key, 'pending', 'reverted') THEN RAISE EXCEPTION 'pending->reverted allowed'; END IF;
    IF NOT public.transition_core_credit(key, 'pending', 'credited') THEN RAISE EXCEPTION 'credit failed'; END IF;

    -- credited -> reverting -> reverted, then a fresh reaction re-claims with the current snapshot
    IF (public.claim_core_credit(key, 'g', 'off1', 'rec', 100, 'green', 'Green', 'G')->>'claimed')::boolean THEN
        RAISE EXCEPTION 'credited claimed again';
    END IF;
    PERFORM public.transition_core_credit(key, 'credited', 'reverting');
    IF (public.claim_core_credit(key, 'g', 'off1', 'rec', 100, 'green', 'Green', 'G')->>'claimed')::boolean THEN
        RAISE EXCEPTION 'reverting claimed (refund in flight)';
    END IF;
    PERFORM public.transition_core_credit(key, 'reverting', 'reverted');
    IF (public.claim_core_credit(key, 'other-guild', 'off1', 'rec', 100, 'green', 'Green', 'G')->>'claimed')::boolean THEN
        RAISE EXCEPTION 'reverted claimed from another guild';
    END IF;
    result := public.claim_core_credit(key, 'g', 'off2', 'rec2', 250, 'green', 'Green+', 'G2');
    IF NOT (result->>'claimed')::boolean OR result->'entry'->>'status' <> 'pending'
       OR (result->'entry'->>'amount')::int <> 250 OR result->'entry'->>'user_id' <> 'off2'
       OR (result->'entry'->>'attempt_count')::int <> 2 OR result->'entry'->>'credited_at' IS NOT NULL THEN
        RAISE EXCEPTION 're-claim after reverted wrong: %', result;
    END IF;
    IF (public.claim_core_credit(key, 'g', 'off2', 'rec2', 250, 'green', 'Green+', 'G2')->>'claimed')::boolean THEN
        RAISE EXCEPTION 'reverted re-claim was not compare-and-swap';
    END IF;
    RESET ROLE;
END;
$$;

SELECT 'finance_integrity_regression: all scenarios passed' AS result;
