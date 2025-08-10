-- RUN THIS in Supabase SQL Editor to replace multiple tables/views with one unified table

-- 1) Drop old views/tables
DROP VIEW IF EXISTS public.latest_prices_readable CASCADE;
DROP VIEW IF EXISTS public.latest_prices CASCADE;
DROP TABLE IF EXISTS public.prices CASCADE;
DROP TABLE IF EXISTS public.items CASCADE;

-- 2) Create unified table
DROP TABLE IF EXISTS public.market_data CASCADE;
CREATE TABLE public.market_data (
  item_key      TEXT NOT NULL,
  display_name  TEXT,
  name_base     TEXT,
  stattrak      BOOLEAN NOT NULL DEFAULT FALSE,
  souvenir      BOOLEAN NOT NULL DEFAULT FALSE,
  condition     TEXT,
  phase         TEXT,
  source        TEXT NOT NULL,
  price         NUMERIC(18,6),
  qty           INTEGER NOT NULL DEFAULT 0,
  highest_offer NUMERIC(18,6),
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_market_data PRIMARY KEY (item_key, source)
);

CREATE INDEX IF NOT EXISTS idx_market_data_fetched_at ON public.market_data (fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_name ON public.market_data (name_base);
CREATE INDEX IF NOT EXISTS idx_market_data_phase ON public.market_data (phase);

-- (Optional) normalize condition values
ALTER TABLE public.market_data
  ADD CONSTRAINT market_condition_chk
  CHECK (condition IS NULL OR condition IN ('Factory New','Minimal Wear','Field-Tested','Well-Worn','Battle-Scarred'))
  NOT VALID;

-- (Optional) restrict known sources
ALTER TABLE public.market_data
  ADD CONSTRAINT market_source_chk
  CHECK (source IN ('whitemarket','csfloat','buff163'))
  NOT VALID;


