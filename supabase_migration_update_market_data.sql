-- Migration to adapt market_data to per-item unified row
-- 1) Keys & structure
ALTER TABLE public.market_data
  DROP CONSTRAINT IF EXISTS pk_market_data;

-- remove source-driven PK and move to single-row per item
ALTER TABLE public.market_data
  ADD CONSTRAINT pk_market_data PRIMARY KEY (item_key);

-- 2) Columns for sources & quantities
ALTER TABLE public.market_data
  DROP COLUMN IF EXISTS source,
  RENAME COLUMN price TO price_whitemarket,
  RENAME COLUMN qty   TO qty_whitemarket;

ALTER TABLE public.market_data
  ADD COLUMN IF NOT EXISTS price_csfloat NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS price_buff163 NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS highest_offer_buff163 NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS qty_csfloat INT,
  ADD COLUMN IF NOT EXISTS qty_buff163 INT;

-- 3) Compact name handling: compute display_name instead of storing
-- drop stored display_name if exists
ALTER TABLE public.market_data
  DROP COLUMN IF EXISTS display_name;

-- helper function to build display name
CREATE OR REPLACE FUNCTION public.build_display_name(
  name_base TEXT,
  stattrak  BOOLEAN,
  souvenir  BOOLEAN,
  condition TEXT,
  phase     TEXT
) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
SELECT trim(both ' ' from (
  (CASE WHEN souvenir AND NOT stattrak THEN 'Souvenir ' ELSE '' END) ||
  (CASE WHEN stattrak AND left(name_base,2)='★ ' THEN '★ StatTrak™ ' || substr(name_base,3)
        WHEN stattrak THEN 'StatTrak™ ' || name_base
        ELSE name_base END) ||
  (CASE WHEN condition IS NOT NULL THEN ' ('||condition||')' ELSE '' END) ||
  (CASE WHEN phase IS NOT NULL THEN ' – '||phase ELSE '' END)
));
$$;

-- generated display_name (not stored twice)
ALTER TABLE public.market_data
  ADD COLUMN display_name TEXT GENERATED ALWAYS AS (
    public.build_display_name(name_base, stattrak, souvenir, condition, phase)
  ) STORED;

-- 4) Useful indexes after changes
CREATE INDEX IF NOT EXISTS idx_market_data_name ON public.market_data (name_base);
CREATE INDEX IF NOT EXISTS idx_market_data_fetched_at ON public.market_data (fetched_at DESC);


