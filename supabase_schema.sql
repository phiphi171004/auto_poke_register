-- ============================================================================
-- Pokemon Auto Register Web - Supabase (PostgreSQL) Schema
-- Paste and execute this entire script in: Supabase Dashboard -> SQL Editor
-- ============================================================================

-- 1. Registered Accounts
CREATE TABLE IF NOT EXISTS public.accounts (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    token TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    zone_id TEXT DEFAULT '',
    character_name TEXT DEFAULT '',
    pets TEXT DEFAULT '',
    raw TEXT DEFAULT '',
    status TEXT DEFAULT 'completed',
    lucky_sigh TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accounts_username ON public.accounts (username);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON public.accounts (status);
CREATE INDEX IF NOT EXISTS idx_accounts_created_at ON public.accounts (created_at DESC);

-- 2. Game Servers Cache
CREATE TABLE IF NOT EXISTS public.servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tcp TEXT NOT NULL,
    status TEXT DEFAULT 'online',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Pokedex Reference Table (optional: backend also bundles 898 entries offline)
CREATE TABLE IF NOT EXISTS public.pokedex (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    tier TEXT NOT NULL,
    type TEXT NOT NULL
);

-- 4. App Settings Key-Value Store
CREATE TABLE IF NOT EXISTS public.app_settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);

-- 5. Saved Proxies Table (persists proxy list + latest check status/latency)
CREATE TABLE IF NOT EXISTS public.proxies (
    proxy TEXT PRIMARY KEY,
    proxy_type TEXT DEFAULT 'http',
    status TEXT DEFAULT 'unchecked',
    latency_ms INTEGER,
    error TEXT DEFAULT '',
    last_checked TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proxies_status ON public.proxies (status);

-- Note:
-- Use your Supabase `service_role` key in the server-side SUPABASE_KEY env var
-- (NEVER expose service_role key to browsers/frontend).
-- Keeping RLS enabled on these tables blocks anonymous public access while
-- allowing the FastAPI backend (using service_role) full read/write access.
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pokedex ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.proxies ENABLE ROW LEVEL SECURITY;
