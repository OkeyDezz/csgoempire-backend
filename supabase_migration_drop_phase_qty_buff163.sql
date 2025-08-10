-- Safe migration to remove columns `qty_buff163` and `phase` from public.market_data
-- and keep a generated display_name without phase dependency.

-- 1) Drop objects that depend on phase/display_name
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_market_data_phase'
  ) THEN
    DROP INDEX public.idx_market_data_phase;
  END IF;
END $$;

ALTER TABLE public.market_data
  DROP COLUMN IF EXISTS display_name;

DROP FUNCTION IF EXISTS public.build_display_name(text, boolean, boolean, text, text);

-- 2) Drop the target columns
ALTER TABLE public.market_data
  DROP COLUMN IF EXISTS qty_buff163,
  DROP COLUMN IF EXISTS phase;

-- 3) Recreate helper and generated column without phase
CREATE OR REPLACE FUNCTION public.build_display_name(
  name_base TEXT,
  stattrak  BOOLEAN,
  souvenir  BOOLEAN,
  condition TEXT
) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
SELECT trim(both ' ' from (
  (CASE WHEN souvenir AND NOT stattrak THEN 'Souvenir ' ELSE '' END) ||
  (CASE WHEN stattrak AND left(name_base,2)='★ ' THEN '★ StatTrak™ ' || substr(name_base,3)
        WHEN stattrak THEN 'StatTrak™ ' || name_base
        ELSE name_base END) ||
  (CASE WHEN condition IS NOT NULL THEN ' ('||condition||')' ELSE '' END)
));
$$;

ALTER TABLE public.market_data
  ADD COLUMN display_name TEXT GENERATED ALWAYS AS (
    public.build_display_name(name_base, stattrak, souvenir, condition)
  ) STORED;


