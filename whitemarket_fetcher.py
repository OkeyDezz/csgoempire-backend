#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gzip
import io
import typing as t
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
import ijson

WHITEMARKET_URL = "https://s3.white.market/export/v1/products/730.json"
# Desabilita HTTP/2 no httpx/postgrest para evitar RemoteProtocolError em lotes grandes
os.environ.setdefault("HTTPX_DISABLE_HTTP2", "1")
# Carrega .env do diretório deste arquivo (robusto contra cwd diferente)
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_PATH)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE") or os.environ.get("SUPABASE_ANON_KEY")

MARKET_TABLE = os.environ.get("SUPABASE_MARKET_TABLE", "market_data")
UPSERT_BATCH = int(os.environ.get("SUPABASE_UPSERT_BATCH", "500"))

CONDITION_NAMES = [
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred",
]


def parse_market_hash_name(name: str) -> t.Tuple[str, bool, bool, t.Optional[str]]:
    if not name:
        return "", False, False, None
    s = name
    stattrak = "StatTrak" in s or "StatTrak™" in s
    souvenir = "Souvenir" in s
    condition = None
    for cond in CONDITION_NAMES:
        if s.endswith(f"({cond})"):
            condition = cond
            s = s[: -(len(cond) + 2)].strip()
            break
    base = s.replace("StatTrak™ ", "").replace("StatTrak ", "").replace("Souvenir ", "").strip()
    return base, stattrak, souvenir, condition


def build_item_key(name_base: str, stattrak: bool, souvenir: bool, condition: t.Optional[str], phase: t.Optional[str]) -> str:
    parts = [
        name_base or "",
        ("StatTrak" if stattrak else ""),
        ("Souvenir" if souvenir else ""),
        condition or "",
        phase or "",
    ]
    # keep a technical key without special symbols; join with pipe and collapse empties
    return "|".join([p for p in parts if p != ""]).strip()


def build_display_name(name_base: str, stattrak: bool, souvenir: bool, condition: t.Optional[str], phase: t.Optional[str]) -> str:
    name = name_base
    if stattrak:
        # Insert StatTrak™ after the star or before base
        if name.startswith("★ "):
            name = name.replace("★ ", "★ StatTrak™ ", 1)
        else:
            name = f"StatTrak™ {name}"
    if souvenir and not stattrak:
        # Souvenir prefix only if not StatTrak
        name = f"Souvenir {name}"
    if condition:
        name = f"{name} ({condition})"
    if phase:
        name = f"{name} – {phase}"
    return name


class PrependStream:
    def __init__(self, head: bytes, base):
        self.buf = io.BytesIO(head)
        self.base = base

    def read(self, n: int = -1):
        b = self.buf.read(n)
        if n == -1 or len(b) == n:
            return b
        rest = self.base.read(n - len(b))
        return b + rest


def open_source_stream(url: str):
    headers = {"Accept": "application/json"}
    api_token = os.environ.get("WHITEMARKET_API_TOKEN")
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    resp = requests.get(url, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()
    resp.raw.decode_content = True
    head = resp.raw.read(4)
    base = PrependStream(head, resp.raw)
    if head.startswith(b"\x1f\x8b"):
        return gzip.GzipFile(fileobj=base, mode="rb")
    return base


def get_supabase_client():
    from supabase import create_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL/SUPABASE_SERVICE_ROLE não configurados no ambiente")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def chunked(iterable, size: int):
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def upsert_market_rows(sb, rows: list[dict]):
    for batch in chunked(rows, UPSERT_BATCH):
        sb.table(MARKET_TABLE).upsert(batch, on_conflict="item_key").execute()


def insert_price_snapshot(*args, **kwargs):
    # no-op kept for compatibility if referenced elsewhere
    return None


def iter_json_items(stream) -> t.Iterable[dict]:
    """Yield items from common root layouts: array root (item), products.item, data.item.
    Falls back to NDJSON (one JSON object per line)."""
    tried = False
    # 1) Root array
    try:
        for obj in ijson.items(stream, "item"):
            tried = True
            if isinstance(obj, dict):
                yield obj
        if tried:
            return
    except Exception:
        pass

    # If we got here, reopen and try alternative roots
    
def fetch_whitemarket(url: str = WHITEMARKET_URL) -> t.Iterable[dict]:
    # Try multiple root paths; reopen stream per attempt
    root_paths = [
        "item",             # root is an array
        "products.item",    # {"products": [ ... ]}
        "data.item",        # {"data": [ ... ]}
    ]

    for root in root_paths:
        stream = open_source_stream(url)
        got_any = False
        try:
            for obj in ijson.items(stream, root):
                got_any = True
                if isinstance(obj, dict):
                    yield obj
            if got_any:
                return
        except Exception:
            continue

    # Fallback: NDJSON (one JSON object per line)
    stream = open_source_stream(url)
    text_stream = io.TextIOWrapper(stream, encoding='utf-8', errors='ignore')
    for line in text_stream:
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                yield obj
        except Exception:
            continue


def aggregate_whitemarket(products: t.Iterable[dict]) -> t.Dict[str, dict]:
    buckets: t.Dict[str, dict] = {}
    for p in products:
        class_id = str(
            p.get("product_class_id")
            or p.get("class_id")
            or p.get("classid")
            or p.get("productClassId")
            or ""
        )
        if not class_id:
            class_id = str(
                p.get("name_hash")
                or p.get("hash_name")
                or p.get("market_hash_name")
                or p.get("name")
                or ""
            )
        if not class_id:
            continue
        entry = buckets.get(class_id)
        if not entry:
            entry = {"items": []}
            buckets[class_id] = entry
        entry["items"].append(p)

    results: t.Dict[str, dict] = {}
    now = datetime.now(timezone.utc)
    for class_id, entry in buckets.items():
        items = entry["items"]
        sample = items[0]
        name = (
            sample.get("name_hash")
            or sample.get("market_hash_name")
            or sample.get("hash_name")
            or sample.get("name")
            or ""
        )
        # detect price fields and cents
        raw_price = None
        for f in ("price", "price_usd", "price_cents", "amount", "value"):
            if f in sample and sample[f] is not None:
                raw_price = sample[f]
                if isinstance(raw_price, str):
                    try:
                        raw_price = float(raw_price.replace(",", ".").strip())
                    except Exception:
                        raw_price = None
                if f.endswith("_cents") and isinstance(raw_price, (int, float)):
                    raw_price = float(raw_price) / 100.0
                break
        try:
            price = float(raw_price) if raw_price is not None else None
        except Exception:
            price = None
        phase = sample.get("product_phase") or sample.get("phase")
        name_base, stattrak, souvenir, condition = parse_market_hash_name(str(name))
        phase_str = str(phase) if phase else None
        item_key = build_item_key(name_base, stattrak, souvenir, condition, phase_str)
        display_name = build_display_name(name_base, stattrak, souvenir, condition, phase_str)
        qty = len(items)
        results[item_key] = {
            "item_key": item_key,
            "name_base": name_base,
            "stattrak": stattrak,
            "souvenir": souvenir,
            "condition": condition,
            "price_whitemarket": price,
            "qty_whitemarket": qty,
            "fetched_at": now,
        }
    return results


def run_whitemarket_ingest(url: str = WHITEMARKET_URL) -> int:
    sb = get_supabase_client()
    products = fetch_whitemarket(url)
    aggregated = aggregate_whitemarket(products)
    rows = []
    for _, rec in aggregated.items():
        rows.append({
            "item_key": rec["item_key"],
            "name_base": rec["name_base"],
            "stattrak": bool(rec["stattrak"]),
            "souvenir": bool(rec["souvenir"]),
            "condition": rec["condition"],
            "price_whitemarket": rec["price_whitemarket"] if "price_whitemarket" in rec else rec["price"],
            "qty_whitemarket": int(rec["qty_whitemarket"]) if "qty_whitemarket" in rec else int(rec["qty"]),
            "fetched_at": rec["fetched_at"].isoformat(),
        })
    if rows:
        upsert_market_rows(sb, rows)
    return len(rows)


if __name__ == "__main__":
    count = run_whitemarket_ingest()
    print(f"[whitemarket] itens agregados: {count}")


