-- Atomic dashboard config patches.
-- Applied after schema.sql has created these tables.

CREATE OR REPLACE FUNCTION public.dashboard_get_corebank_config(p_guild_id text)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    config_row jsonb;
BEGIN
    IF p_guild_id IS NULL OR btrim(p_guild_id) = '' THEN
        RAISE EXCEPTION 'guild id is required';
    END IF;

    -- Preserve the legacy settings, but never replace a row already belonging
    -- to the configured guild. Keep the legacy row for explicit reconciliation.
    IF p_guild_id <> 'default' THEN
        INSERT INTO public.corebank_config (
            guild_id,
            core_channel_id,
            bank_channel_id,
            unbelievaboat_token,
            emoji_map,
            auto_react
        )
        SELECT
            p_guild_id,
            legacy.core_channel_id,
            legacy.bank_channel_id,
            legacy.unbelievaboat_token,
            legacy.emoji_map,
            legacy.auto_react
        FROM public.corebank_config AS legacy
        WHERE legacy.guild_id = 'default'
          AND NOT EXISTS (
              SELECT 1
              FROM public.corebank_config AS current
              WHERE current.guild_id = p_guild_id
          )
        ON CONFLICT (guild_id) DO NOTHING;
    END IF;

    SELECT to_jsonb(config)
      INTO config_row
      FROM public.corebank_config AS config
     WHERE config.guild_id = p_guild_id;

    RETURN config_row;
END;
$$;

CREATE OR REPLACE FUNCTION public.dashboard_patch_corebank_config(
    p_guild_id text,
    p_patch jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    config_row jsonb;
    allowed_keys constant text[] := ARRAY[
        'core_channel_id', 'bank_channel_id', 'unbelievaboat_token', 'auto_react'
    ];
    patch_key text;
BEGIN
    IF p_guild_id IS NULL OR btrim(p_guild_id) = '' THEN
        RAISE EXCEPTION 'guild id is required';
    END IF;
    IF p_patch IS NULL OR jsonb_typeof(p_patch) <> 'object' THEN
        RAISE EXCEPTION 'patch must be a JSON object';
    END IF;

    FOR patch_key IN SELECT jsonb_object_keys(p_patch) LOOP
        IF NOT patch_key = ANY (allowed_keys) THEN
            RAISE EXCEPTION 'unsupported CoreBank field';
        END IF;
        IF patch_key = 'auto_react' AND jsonb_typeof(p_patch -> patch_key) <> 'boolean' THEN
            RAISE EXCEPTION 'auto_react must be a boolean';
        ELSIF patch_key <> 'auto_react' AND jsonb_typeof(p_patch -> patch_key) <> 'string' THEN
            RAISE EXCEPTION 'CoreBank fields must be strings';
        END IF;
    END LOOP;

    PERFORM public.dashboard_get_corebank_config(p_guild_id);

    INSERT INTO public.corebank_config AS current (
        guild_id,
        core_channel_id,
        bank_channel_id,
        unbelievaboat_token,
        auto_react
    )
    VALUES (
        p_guild_id,
        COALESCE(p_patch ->> 'core_channel_id', ''),
        COALESCE(p_patch ->> 'bank_channel_id', ''),
        COALESCE(p_patch ->> 'unbelievaboat_token', ''),
        COALESCE((p_patch ->> 'auto_react')::boolean, true)
    )
    ON CONFLICT (guild_id) DO UPDATE SET
        core_channel_id = CASE
            WHEN p_patch ? 'core_channel_id' THEN p_patch ->> 'core_channel_id'
            ELSE current.core_channel_id
        END,
        bank_channel_id = CASE
            WHEN p_patch ? 'bank_channel_id' THEN p_patch ->> 'bank_channel_id'
            ELSE current.bank_channel_id
        END,
        unbelievaboat_token = CASE
            WHEN p_patch ? 'unbelievaboat_token' THEN p_patch ->> 'unbelievaboat_token'
            ELSE current.unbelievaboat_token
        END,
        auto_react = CASE
            WHEN p_patch ? 'auto_react' THEN (p_patch ->> 'auto_react')::boolean
            ELSE current.auto_react
        END,
        updated_at = now()
    RETURNING to_jsonb(current) INTO config_row;

    RETURN config_row;
END;
$$;

CREATE OR REPLACE FUNCTION public.dashboard_mutate_corebank_emoji(
    p_guild_id text,
    p_key text,
    p_value jsonb,
    p_remove boolean
)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    config_row jsonb;
BEGIN
    IF p_guild_id IS NULL OR btrim(p_guild_id) = '' THEN
        RAISE EXCEPTION 'guild id is required';
    END IF;
    IF p_key IS NULL OR p_key = '' THEN
        RAISE EXCEPTION 'emoji key is required';
    END IF;
    IF p_remove IS NULL OR (NOT p_remove AND (p_value IS NULL OR jsonb_typeof(p_value) <> 'object')) THEN
        RAISE EXCEPTION 'emoji value must be a JSON object';
    END IF;

    PERFORM public.dashboard_get_corebank_config(p_guild_id);

    INSERT INTO public.corebank_config (guild_id, emoji_map)
    VALUES (p_guild_id, '{}'::jsonb)
    ON CONFLICT (guild_id) DO NOTHING;

    UPDATE public.corebank_config AS config
       SET emoji_map = CASE
            WHEN p_remove THEN COALESCE(config.emoji_map, '{}'::jsonb) - p_key
            ELSE COALESCE(config.emoji_map, '{}'::jsonb) || jsonb_build_object(p_key, p_value)
       END,
           updated_at = now()
     WHERE config.guild_id = p_guild_id
    RETURNING to_jsonb(config) INTO config_row;

    RETURN config_row;
END;
$$;

CREATE OR REPLACE FUNCTION public.dashboard_get_ai_config(p_guild_id text)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    config_row jsonb;
BEGIN
    IF p_guild_id IS NULL OR btrim(p_guild_id) = '' THEN
        RAISE EXCEPTION 'guild id is required';
    END IF;

    IF p_guild_id <> 'default' THEN
        INSERT INTO public.ai_config (
            guild_id,
            model,
            available_models,
            channel_buffers,
            intercept_channels,
            autowiki_channels,
            library_channel_ids,
            vision_channels
        )
        SELECT
            p_guild_id,
            legacy.model,
            legacy.available_models,
            legacy.channel_buffers,
            legacy.intercept_channels,
            legacy.autowiki_channels,
            legacy.library_channel_ids,
            legacy.vision_channels
        FROM public.ai_config AS legacy
        WHERE legacy.guild_id = 'default'
          AND NOT EXISTS (
              SELECT 1
              FROM public.ai_config AS current
              WHERE current.guild_id = p_guild_id
          )
        ON CONFLICT (guild_id) DO NOTHING;
    END IF;

    SELECT to_jsonb(config)
      INTO config_row
      FROM public.ai_config AS config
     WHERE config.guild_id = p_guild_id;

    RETURN config_row;
END;
$$;

CREATE OR REPLACE FUNCTION public.dashboard_patch_ai_config(
    p_guild_id text,
    p_patch jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    config_row jsonb;
    allowed_keys constant text[] := ARRAY[
        'model', 'intercept_channels', 'autowiki_channels', 'library_channel_ids', 'vision_channels'
    ];
    patch_key text;
BEGIN
    IF p_guild_id IS NULL OR btrim(p_guild_id) = '' THEN
        RAISE EXCEPTION 'guild id is required';
    END IF;
    IF p_patch IS NULL OR jsonb_typeof(p_patch) <> 'object' THEN
        RAISE EXCEPTION 'patch must be a JSON object';
    END IF;

    FOR patch_key IN SELECT jsonb_object_keys(p_patch) LOOP
        IF NOT patch_key = ANY (allowed_keys) THEN
            RAISE EXCEPTION 'unsupported AI config field';
        END IF;
        IF patch_key = 'model' THEN
            IF jsonb_typeof(p_patch -> patch_key) <> 'string' THEN
                RAISE EXCEPTION 'model must be a string';
            END IF;
        ELSIF jsonb_typeof(p_patch -> patch_key) <> 'array' OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(p_patch -> patch_key) AS item(value)
            WHERE jsonb_typeof(item.value) <> 'string'
        ) THEN
            RAISE EXCEPTION 'AI channel fields must be arrays of strings';
        END IF;
    END LOOP;
    PERFORM public.dashboard_get_ai_config(p_guild_id);


    INSERT INTO public.ai_config AS current (
        guild_id,
        model,
        intercept_channels,
        autowiki_channels,
        library_channel_ids,
        vision_channels
    )
    VALUES (
        p_guild_id,
        COALESCE(p_patch ->> 'model', 'inclusionai/ling-3.0-flash:free'),
        COALESCE(p_patch -> 'intercept_channels', '[]'::jsonb),
        COALESCE(p_patch -> 'autowiki_channels', '[]'::jsonb),
        COALESCE(p_patch -> 'library_channel_ids', '[]'::jsonb),
        COALESCE(p_patch -> 'vision_channels', '[]'::jsonb)
    )
    ON CONFLICT (guild_id) DO UPDATE SET
        model = CASE
            WHEN p_patch ? 'model' THEN p_patch ->> 'model'
            ELSE current.model
        END,
        intercept_channels = CASE
            WHEN p_patch ? 'intercept_channels' THEN p_patch -> 'intercept_channels'
            ELSE current.intercept_channels
        END,
        autowiki_channels = CASE
            WHEN p_patch ? 'autowiki_channels' THEN p_patch -> 'autowiki_channels'
            ELSE current.autowiki_channels
        END,
        library_channel_ids = CASE
            WHEN p_patch ? 'library_channel_ids' THEN p_patch -> 'library_channel_ids'
            ELSE current.library_channel_ids
        END,
        vision_channels = CASE
            WHEN p_patch ? 'vision_channels' THEN p_patch -> 'vision_channels'
            ELSE current.vision_channels
        END,
        updated_at = now()
    RETURNING to_jsonb(current) INTO config_row;

    RETURN config_row;
END;
$$;


REVOKE ALL ON FUNCTION public.dashboard_get_corebank_config(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.dashboard_patch_corebank_config(text, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.dashboard_mutate_corebank_emoji(text, text, jsonb, boolean) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.dashboard_patch_ai_config(text, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.dashboard_get_ai_config(text) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.dashboard_get_corebank_config(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.dashboard_patch_corebank_config(text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.dashboard_mutate_corebank_emoji(text, text, jsonb, boolean) TO service_role;
GRANT EXECUTE ON FUNCTION public.dashboard_patch_ai_config(text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.dashboard_get_ai_config(text) TO service_role;
