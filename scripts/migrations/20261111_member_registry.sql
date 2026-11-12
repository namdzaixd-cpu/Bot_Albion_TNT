-- Migration: Thêm bảng member_registry cho tính năng tự động gỡ role khi out guild
-- Apply: node scripts/db-exec.js "$(cat scripts/migrations/20261111_member_registry.sql)"
-- Hoặc paste vào SQL Editor Supabase

CREATE TABLE IF NOT EXISTS public.member_registry (
    discord_id text PRIMARY KEY,
    player_id text NOT NULL UNIQUE,
    ign text NOT NULL,
    region text NOT NULL DEFAULT 'Asia',
    registered_by text,
    registered_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS member_registry_player_id_idx ON public.member_registry(player_id);
