-- Migration: add display_name on items and a helper view with readable names

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS display_name TEXT;

-- Optional: composite uniqueness to reinforce identity (keeps item_key as PK intact)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ux_items_identity'
  ) THEN
    CREATE UNIQUE INDEX ux_items_identity
    ON public.items (name_base, stattrak, souvenir, condition, phase);
  END IF;
END $$;

-- View that joins latest prices with human-readable display_name
CREATE OR REPLACE VIEW public.latest_prices_readable AS
SELECT lp.item_key,
       i.display_name,
       lp.source,
       lp.price,
       lp.qty,
       lp.highest_offer,
       lp.fetched_at
FROM public.latest_prices lp
LEFT JOIN public.items i USING (item_key);


