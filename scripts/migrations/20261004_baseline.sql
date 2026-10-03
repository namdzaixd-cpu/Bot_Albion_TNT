-- Bổ sung columns trên schema legacy; không reset dữ liệu và không đổi kiểu đã có.
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'guild_config', 'ai_config', 'user_activity', 'user_economy',
        'sp_metadata', 'sp_transactions', 'alo_tts_config', 'json_storage',
        'corebank_config', 'core_credited', 'blacklist',
        'discord_channels', 'discord_roles', 'chat_history'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now()', table_name);
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now()', table_name);
        EXECUTE format('DROP TRIGGER IF EXISTS trg_updated_at ON public.%I', table_name);
        EXECUTE format('CREATE TRIGGER trg_updated_at BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', table_name);
    END LOOP;
END;
$$;

ALTER TABLE public.ai_config ADD COLUMN IF NOT EXISTS library_channel_ids jsonb DEFAULT '[]'::jsonb;
ALTER TABLE public.ai_config ADD COLUMN IF NOT EXISTS vision_channels jsonb DEFAULT '[]'::jsonb;
ALTER TABLE public.core_credited ADD COLUMN IF NOT EXISTS guild_id text;
ALTER TABLE public.core_credited ADD COLUMN IF NOT EXISTS credited_at timestamptz DEFAULT now();
ALTER TABLE public.sp_transactions ADD COLUMN IF NOT EXISTS guild_id text;
ALTER TABLE public.system_logs ADD COLUMN IF NOT EXISTS guild_id text;
ALTER TABLE public.chat_history ADD COLUMN IF NOT EXISTS guild_id text;

-- NOT VALID giữ nguyên orphan legacy; vẫn kiểm tra mọi INSERT/UPDATE mới.
-- Không map nhãn nguồn cũ thành guild ID giả hoặc xóa row để migration xanh.
DO $$
DECLARE relation_name text;
    column_name text;
    constraint_name text;
    delete_action text;
BEGIN
    FOR relation_name, column_name, constraint_name, delete_action IN
        SELECT * FROM (VALUES
            ('core_credited', 'guild_id', 'fk_core_guild', 'SET NULL'),
            ('sp_transactions', 'guild_id', 'fk_sp_guild', 'SET NULL'),
            ('blacklist', 'source_guild_id', 'fk_blacklist_guild', 'SET NULL'),
            ('discord_channels', 'guild_id', 'fk_chan_guild', 'CASCADE'),
            ('discord_roles', 'guild_id', 'fk_role_guild', 'CASCADE'),
            ('system_logs', 'guild_id', 'fk_log_guild', 'SET NULL')
        ) AS relations(table_name, field_name, fk_name, delete_mode)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = format('public.%I', relation_name)::regclass
              AND conname = constraint_name
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES public.guild_config(guild_id) ON DELETE %s NOT VALID',
                relation_name, constraint_name, column_name, delete_action
            );
        END IF;
    END LOOP;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_blacklist_discord ON public.blacklist(discord_id);
CREATE INDEX IF NOT EXISTS idx_blacklist_ingame ON public.blacklist(ingame_id);
CREATE INDEX IF NOT EXISTS idx_blacklist_guild ON public.blacklist(source_guild_id);
CREATE INDEX IF NOT EXISTS idx_core_guild ON public.core_credited(guild_id);
CREATE INDEX IF NOT EXISTS idx_sp_player ON public.sp_transactions(player_name);
CREATE INDEX IF NOT EXISTS idx_sp_inserted ON public.sp_transactions(inserted_at DESC);
CREATE INDEX IF NOT EXISTS idx_sp_guild ON public.sp_transactions(guild_id);
CREATE INDEX IF NOT EXISTS idx_chan_guild ON public.discord_channels(guild_id);
CREATE INDEX IF NOT EXISTS idx_role_guild ON public.discord_roles(guild_id);
CREATE INDEX IF NOT EXISTS idx_logs_created ON public.system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_guild ON public.system_logs(guild_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_updated ON public.user_activity(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_economy_silver ON public.user_economy(silver_pieces DESC);
