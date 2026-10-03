-- Apply after 20261004_financial.sql adds CoreBank ledger lifecycle columns.
CREATE OR REPLACE FUNCTION public.dashboard_overview_metrics(p_guild_id text)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    corebank_total bigint;
    blacklist_count bigint;
    ai_today bigint;
    siphoned_count bigint;
BEGIN
    IF p_guild_id IS NULL OR btrim(p_guild_id) = '' THEN
        RAISE EXCEPTION 'guild id is required';
    END IF;

    -- Count only confirmed payments that have not reached a confirmed refund.
    -- Unknown, pending, legacy, retryable, and reverted entries are excluded.
    SELECT COALESCE(SUM(amount), 0)::bigint
      INTO corebank_total
      FROM public.core_credited
     WHERE guild_id = p_guild_id
       AND status IN ('credited', 'reverting');

    SELECT COUNT(*)
      INTO blacklist_count
      FROM public.blacklist
     WHERE source_guild_id = p_guild_id;

    SELECT COUNT(*)
      INTO ai_today
      FROM public.system_logs
     WHERE guild_id = p_guild_id
       AND lower(module) = 'ai'
       AND created_at >= date_trunc('day', now());

    SELECT COUNT(*)
      INTO siphoned_count
      FROM public.user_economy;

    RETURN jsonb_build_object(
        'corebank_total', corebank_total,
        'blacklist_count', blacklist_count,
        'ai_today', ai_today,
        'siphoned_count', siphoned_count
    );
END;
$$;

REVOKE ALL ON FUNCTION public.dashboard_overview_metrics(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.dashboard_overview_metrics(text) TO service_role;
