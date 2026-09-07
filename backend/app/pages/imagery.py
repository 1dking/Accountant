"""Library imagery — placeholder photos for every image slot in the block
library, generated once (Higgsfield, session-driven) and pinned by a
committed manifest so re-seeds never regenerate or re-spend credits.

`seeds/imagery_manifest.json`:
    {
      "pools": { "gallery": [url, …], "team": [url, …], "hero": [url, …], … },
      "slots": { "<variant_id>": { "IMAGE_1_URL": url, "ITEMS[2].IMAGE_URL": url, … } },
      "stock_fallback": { "gallery": [url, …], … }
    }

`apply_imagery(variant_id, default_props, fields_schema)` returns a copy of
default_props with:
  1. explicit slot overrides from `slots`,
  2. otherwise, for every image field still empty / a data: placeholder /
     an unsplash hotlink, a URL from the matching pool (deterministic
     round-robin per variant so a gallery gets distinct photos),
  3. otherwise untouched.

The prompt map (`PROMPTS`) is the source of truth for what gets generated;
`plan_batch()` lists the images still missing from the pools so the cost
can be shown before any generation happens.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_MANIFEST = Path(__file__).resolve().parent / "seeds" / "imagery_manifest.json"
_manifest_cache: dict | None = None

# pool → (aspect ratio, count, prompts). Prompts are photorealistic,
# text-free, Canadian small-business flavoured.
_P = "photorealistic photograph, natural light, no text, no logos, no watermarks"

# 72 images total, recycled across every block and template (Nate,
# 2026-09-07: "use the same images over and over"). Pools are keyed so
# a hero gets a scene, a team grid gets portraits, a gallery gets work
# photos, and the 17 industry templates each find at least one scene.
PROMPTS: dict[str, dict[str, Any]] = {
    # 18 wide scenes — one per industry label in the template library + generic
    "hero": {
        "aspect_ratio": "16:9", "prompts": [
            f"Bright modern accounting office, two advisors reviewing documents at a wooden table, Ottawa skyline through the window, {_P}",
            f"Friendly plumber in a clean uniform kneeling by a modern kitchen sink, tools laid out neatly, {_P}",
            f"Electrician installing a smart panel in a bright new home, safety gear, {_P}",
            f"Landscaping crew finishing a lush suburban front yard at golden hour, {_P}",
            f"Modern dental clinic reception, white and light-wood interior, plants, {_P}",
            f"Physiotherapist guiding a patient through a stretch in a sunlit clinic, {_P}",
            f"Welcoming boutique storefront on a tree-lined Canadian main street in autumn, {_P}",
            f"Cozy neighbourhood café counter with a barista pouring latte art, warm light, {_P}",
            f"Real estate agent handing keys to a smiling couple outside a craftsman house, {_P}",
            f"Fitness coach spotting a client in a bright gym with big windows, {_P}",
            f"Hair salon interior, stylist working, mirrors and greenery, soft daylight, {_P}",
            f"Small law office, lawyer at a desk with bookshelves, calm and professional, {_P}",
            f"Cleaning professional in a spotless modern living room, sunlight, {_P}",
            f"Auto mechanic in a tidy garage bay with a car on a lift, {_P}",
            f"Creative agency studio, team around a table with laptops and mood boards, {_P}",
            f"Restaurant dining room at dusk, warm pendant lights, set tables, {_P}",
            f"Photographer at a wedding reception adjusting a camera, golden hour, {_P}",
            f"Consultant presenting a chart on a screen to a small team in a glass meeting room, {_P}",
        ],
    },
    # 12 supporting 4:3 details for feature / about / process blocks
    "feature": {
        "aspect_ratio": "4:3", "prompts": [
            f"Craftsman measuring hardwood in a bright workshop, shallow depth of field, {_P}",
            f"Laptop and notebook on a café table with a latte, morning light, {_P}",
            f"Team meeting around a whiteboard in a sunlit studio, {_P}",
            f"Spotless residential living room after a cleaning service, plants, {_P}",
            f"Close-up of hands signing a document at a desk with a pen and coffee, {_P}",
            f"Delivery van parked outside a small shop, driver loading boxes, {_P}",
            f"Tablet showing a calendar on a reception desk with flowers, {_P}",
            f"Close-up of a handshake in a bright office, {_P}",
            f"Mechanic's hands tightening a bolt, clean tools, {_P}",
            f"Nutritionist arranging fresh vegetables on a kitchen counter, {_P}",
            f"Architect's desk with blueprints, ruler and a model house, {_P}",
            f"Customer support agent with a headset smiling at a monitor, {_P}",
        ],
    },
    # 20 gallery / portfolio shots
    "gallery": {
        "aspect_ratio": "4:3", "prompts": [
            f"Finished modern kitchen renovation, white cabinets, oak floor, {_P}",
            f"Freshly landscaped backyard with stone patio and cedar fence, {_P}",
            f"Elegant bathroom remodel with marble tile and brass fixtures, {_P}",
            f"Exterior of a renovated craftsman house with new siding and porch, {_P}",
            f"Bright yoga studio with wooden floor and large windows, empty, {_P}",
            f"Modern coworking space with plants and natural light, {_P}",
            f"Artisan bakery display case with pastries and bread, {_P}",
            f"Finished basement home theatre with sectional sofa, {_P}",
            f"New asphalt driveway and interlock walkway in front of a suburban home, {_P}",
            f"Cozy bedroom staging with linen bedding and warm lamp light, {_P}",
            f"Restored vintage motorcycle in a clean garage, {_P}",
            f"Wedding table setting with flowers and candles, {_P}",
            f"Fresh manicured lawn with garden beds and mulch, {_P}",
            f"Newly painted living room in soft sage green, {_P}",
            f"Commercial storefront with new signage area and clean glass, {_P}",
            f"Deck build with composite boards overlooking a lake, {_P}",
            f"Flat-lay of a brand identity: business cards, envelope, notebook, {_P}",
            f"Pet groomer with a fluffy golden doodle on a table, {_P}",
            f"Roofers installing shingles on a house on a clear day, {_P}",
            f"Modern office lobby with reception desk and greenery, {_P}",
        ],
    },
    # 12 portraits for team grids and testimonial avatars
    "team": {
        "aspect_ratio": "1:1", "prompts": [
            f"Professional headshot of a smiling woman in her 30s, business casual, soft studio light, neutral background, {_P}",
            f"Professional headshot of a smiling man in his 40s with glasses, business casual, neutral background, {_P}",
            f"Professional headshot of a young South Asian man, friendly smile, navy sweater, neutral background, {_P}",
            f"Professional headshot of a Black woman in her 30s, confident smile, blazer, neutral background, {_P}",
            f"Professional headshot of an East Asian woman in her 40s, warm smile, neutral background, {_P}",
            f"Professional headshot of a man in his 50s with grey beard, friendly, denim shirt, neutral background, {_P}",
            f"Professional headshot of a Latina woman in her 20s, bright smile, white shirt, neutral background, {_P}",
            f"Professional headshot of an Indigenous man in his 30s, warm expression, dark sweater, neutral background, {_P}",
            f"Professional headshot of a Middle Eastern woman in her 40s, hijab, confident smile, neutral background, {_P}",
            f"Professional headshot of a white man in his 30s, beard, plaid shirt, tradesperson, neutral background, {_P}",
            f"Professional headshot of a Black man in his 50s, suit, warm smile, neutral background, {_P}",
            f"Professional headshot of an older white woman with silver hair, cardigan, kind smile, neutral background, {_P}",
        ],
    },
    # 4 = two before/after pairs
    "before_after": {
        "aspect_ratio": "16:9", "prompts": [
            f"Dated, cluttered kitchen before renovation, beige cabinets, harsh light, {_P}",
            f"The same kitchen after a modern renovation, white cabinets, quartz counter, bright daylight, {_P}",
            f"Overgrown neglected backyard with patchy grass and old fence, overcast, {_P}",
            f"The same backyard after landscaping, fresh sod, stone path, new cedar fence, sunny, {_P}",
        ],
    },
    # 6 storefront / location shots
    "location": {
        "aspect_ratio": "4:3", "prompts": [
            f"Street-level view of a small independent shop with a welcoming entrance and planters, Canadian city, {_P}",
            f"Corner medical clinic entrance with glass doors and accessible ramp, {_P}",
            f"Brick office building entrance with a wooden door and brass plaque, downtown Ottawa, {_P}",
            f"Small auto shop exterior with two open bays, clean forecourt, {_P}",
            f"Restaurant patio with string lights on a summer evening, {_P}",
            f"Strip-mall storefront with large windows and a sidewalk sign area, winter, snow cleared, {_P}",
        ],
    },
}

_UNSPLASH = re.compile(r"^https?://images\.unsplash\.com/")


def load_manifest() -> dict:
    global _manifest_cache  # noqa: PLW0603
    if _manifest_cache is None:
        if _MANIFEST.exists():
            _manifest_cache = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        else:
            _manifest_cache = {"pools": {}, "slots": {}, "stock_fallback": {}}
    return _manifest_cache


def reset_cache() -> None:
    global _manifest_cache  # noqa: PLW0603
    _manifest_cache = None


def pool_for(variant_id: str, category: str, key: str) -> str:
    k = key.upper()
    if "BEFORE" in k or "AFTER" in k:
        return "before_after"
    if category == "team" or "AVATAR" in k or "PORTRAIT" in k:
        return "team"
    if category == "gallery":
        return "gallery"
    if category == "location":
        return "location"
    if category in ("hero", "cta", "testimonials"):
        return "hero"
    return "feature"


def _needs_image(val: Any) -> bool:
    return (not val) or (isinstance(val, str) and (val.startswith("data:image/") or _UNSPLASH.match(val) is not None))


def apply_imagery(variant_id: str, category: str, default_props: dict, fields_schema: list[dict] | None) -> dict:
    m = load_manifest()
    pools: dict[str, list[str]] = {**(m.get("stock_fallback") or {}), **{k: v for k, v in (m.get("pools") or {}).items() if v}}
    slots: dict[str, str] = (m.get("slots") or {}).get(variant_id, {})
    if not pools and not slots:
        return default_props
    props = json.loads(json.dumps(default_props))
    counters: dict[str, int] = {}

    def pick(pool: str, path: str) -> str | None:
        if path in slots:
            return slots[path]
        urls = pools.get(pool) or []
        if not urls:
            return None
        i = counters.get(pool, 0)
        counters[pool] = i + 1
        return urls[i % len(urls)]

    def walk(schema: list[dict] | None, node: dict, prefix: str) -> None:
        for f in schema or []:
            key = f.get("key")
            if not key:
                continue
            path = f"{prefix}{key}"
            if f.get("type") == "image":
                if path in slots or _needs_image(node.get(key)):
                    if key == "BEFORE_URL":
                        url = slots.get(path) or (pools.get("before_after") or [None])[0]
                    elif key == "AFTER_URL":
                        url = slots.get(path) or (pools.get("before_after") or [None, None])[1] if len(pools.get("before_after") or []) > 1 else slots.get(path)
                    else:
                        url = pick(pool_for(variant_id, category, key), path)
                    if url:
                        node[key] = url
            elif f.get("type") == "list":
                for i, item in enumerate(node.get(key) or []):
                    if isinstance(item, dict):
                        walk(f.get("item_fields"), item, f"{path}[{i}].")

    walk(fields_schema, props, "")
    return props


def plan_batch() -> list[dict]:
    """Images still missing from the pools, with model/aspect per pool —
    what a generation run would produce. Nothing is generated here."""
    m = load_manifest()
    pools = m.get("pools") or {}
    out = []
    for pool, spec in PROMPTS.items():
        have = len(pools.get(pool) or [])
        for i, prompt in enumerate(spec["prompts"]):
            if i < have:
                continue
            out.append({"pool": pool, "index": i, "aspect_ratio": spec["aspect_ratio"], "prompt": prompt})
    return out


def record_result(pool: str, index: int, url: str) -> None:
    """Append a generated image URL to the manifest (keeps index order)."""
    m = load_manifest()
    lst = m.setdefault("pools", {}).setdefault(pool, [])
    while len(lst) <= index:
        lst.append(None)
    lst[index] = url
    _MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    reset_cache()
