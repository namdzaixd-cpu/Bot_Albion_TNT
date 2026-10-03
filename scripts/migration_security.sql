-- Apply sau schema.sql và versioned migrations bằng một transaction.
-- Backend service_role; browser anon/authenticated không có table privileges.
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'guild_config', 'ai_config', 'user_activity', 'user_economy',
        'sp_metadata', 'sp_transactions', 'alo_tts_config', 'json_storage',
        'corebank_config', 'core_credited', 'blacklist', 'discord_channels',
        'discord_roles', 'system_logs', 'chat_history'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', table_name);
        EXECUTE format('GRANT ALL ON TABLE public.%I TO service_role', table_name);
        EXECUTE format('DROP POLICY IF EXISTS pol_service_all ON public.%I', table_name);
        EXECUTE format('CREATE POLICY pol_service_all ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)', table_name);
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION public.trg_json_storage_size()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF pg_column_size(NEW.data) > 1048576 THEN
        RAISE EXCEPTION 'json_storage.data quá lớn (>1MB)';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_json_storage_size ON public.json_storage;
CREATE TRIGGER trg_json_storage_size
BEFORE INSERT OR UPDATE ON public.json_storage
FOR EACH ROW EXECUTE FUNCTION public.trg_json_storage_size();
