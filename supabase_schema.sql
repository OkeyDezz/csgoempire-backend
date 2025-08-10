-- Supabase/Postgres schema for market aggregation
-- Run this file in Supabase SQL Editor

-- Optional: create schema
-- CREATE SCHEMA IF NOT EXISTS public;

-- ==========================
-- Table: items (canonical key)
-- ==========================
CREATE TABLE IF NOT EXISTS public.items (
  item_key TEXT PRIMARY KEY,
  name_base TEXT NOT NULL,
  stattrak BOOLEAN NOT NULL DEFAULT FALSE,
  souvenir BOOLEAN NOT NULL DEFAULT FALSE,
  condition TEXT NULL,
  phase TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional constraint for known conditions
ALTER TABLE public.items
  ADD CONSTRAINT items_condition_chk
  CHECK (
    condition IS NULL OR condition IN (
      'Factory New','Minimal Wear','Field-Tested','Well-Worn','Battle-Scarred'
    )
  )
  NOT VALID;

-- Trigger to keep updated_at fresh
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;$$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_items_updated_at'
  ) THEN
    CREATE TRIGGER trg_items_updated_at
    BEFORE UPDATE ON public.items
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_items_name_base ON public.items (name_base);

-- ==========================
-- Table: prices (snapshots per source)
-- ==========================
CREATE TABLE IF NOT EXISTS public.prices (
  id BIGSERIAL PRIMARY KEY,
  item_key TEXT NOT NULL REFERENCES public.items(item_key) ON DELETE CASCADE,
  source TEXT NOT NULL,
  price NUMERIC(18,6) NULL,
  qty INTEGER NOT NULL DEFAULT 0,
  highest_offer NUMERIC(18,6) NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional: restrict known sources (extend as needed)
ALTER TABLE public.prices
  ADD CONSTRAINT prices_source_chk
  CHECK (source IN ('whitemarket','csfloat','buff163'))
  NOT VALID;

CREATE INDEX IF NOT EXISTS idx_prices_item_key ON public.prices (item_key);
CREATE INDEX IF NOT EXISTS idx_prices_fetched_at ON public.prices (fetched_at);
CREATE INDEX IF NOT EXISTS idx_prices_item_source_time ON public.prices (item_key, source, fetched_at DESC);

-- ==========================
-- View: latest price per item per source
-- ==========================
CREATE OR REPLACE VIEW public.latest_prices AS
SELECT DISTINCT ON (p.item_key, p.source)
  p.item_key,
  p.source,
  p.price,
  p.qty,
  p.highest_offer,
  p.fetched_at
FROM public.prices p
ORDER BY p.item_key, p.source, p.fetched_at DESC;

-- ==========================
-- (Optional) RLS setup - enable and add policies as needed
-- ==========================
-- ALTER TABLE public.items ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.prices ENABLE ROW LEVEL SECURITY;
--
-- Example permissive policies for service role integrations (adjust for your auth model):
-- CREATE POLICY items_service_all ON public.items FOR ALL TO authenticated USING (true) WITH CHECK (true);
-- CREATE POLICY prices_service_all ON public.prices FOR ALL TO authenticated USING (true) WITH CHECK (true);


