-- Bootstrap schema-only. Không seed hoặc UPSERT dữ liệu vận hành.
-- Apply bằng scripts/apply_schema.py trước versioned migrations và RLS hardening.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.guild_config (
    guild_id text PRIMARY KEY,
    is_onboard_enabled boolean DEFAULT true,
    apply_channel_id text,
    member_role_id text,
    officer_role_id text,
    rules_channel_id text,
    chat_channel_id text,
    question_channel_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.ai_config (
    guild_id text PRIMARY KEY,
    model text,
    available_models jsonb DEFAULT '[]'::jsonb,
    channel_buffers jsonb DEFAULT '{}'::jsonb,
    intercept_channels jsonb DEFAULT '[]'::jsonb,
    autowiki_channels jsonb DEFAULT '[]'::jsonb,
    library_channel_ids jsonb DEFAULT '[]'::jsonb,
    vision_channels jsonb DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.user_activity (
    user_id text PRIMARY KEY,
    last_seen text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.user_economy (
    user_id text PRIMARY KEY,
    silver_pieces integer DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.sp_metadata (
    id integer PRIMARY KEY DEFAULT 1,
    last_update text DEFAULT 'Chưa có dữ liệu',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.sp_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    player_name text NOT NULL,
    amount integer NOT NULL,
    log_timestamp timestamp NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    guild_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.alo_tts_config (
    id integer PRIMARY KEY DEFAULT 1,
    read_name jsonb DEFAULT '{}'::jsonb,
    rejoin jsonb DEFAULT '{}'::jsonb,
    afk jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.json_storage (
    file_name text PRIMARY KEY,
    data jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.corebank_config (
    guild_id text PRIMARY KEY,
    core_channel_id text DEFAULT '',
    bank_channel_id text DEFAULT '',
    unbelievaboat_token text DEFAULT '',
    emoji_map jsonb DEFAULT '{}'::jsonb,
    auto_react boolean DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.core_credited (
    message_id text PRIMARY KEY,
    user_id text,
    amount integer,
    credited_at timestamptz DEFAULT now(),
    guild_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.blacklist (
    discord_id text PRIMARY KEY,
    ingame_name text,
    ingame_id text,
    reason text,
    added_by_discord_id text,
    source_guild_id text,
    timestamp timestamptz DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.discord_channels (
    id text PRIMARY KEY,
    name text NOT NULL,
    type text,
    guild_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.discord_roles (
    id text PRIMARY KEY,
    name text NOT NULL,
    color text,
    guild_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.system_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    level text NOT NULL,
    module text NOT NULL,
    message text NOT NULL,
    guild_id text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Bảng lịch sử chatbot: giữ contract đã có, không chuyển dữ liệu repo khác.
CREATE TABLE IF NOT EXISTS public.chat_history (
    id text PRIMARY KEY,
    user_id text NOT NULL,
    author_name text NOT NULL,
    channel_id text NOT NULL,
    channel_name text,
    content text NOT NULL,
    guild_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
