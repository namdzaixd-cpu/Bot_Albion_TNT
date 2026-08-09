"""
build_albion_item_db.py — Build database item trang bị Albion Online (stat/skill/passive).

Nguồn: file game cài local, đã giải mã bằng albiondata-bin-dumper (ao-data) thành XML:
  scripts/albion-item/scan/out/items.xml           item + stat + enchant + skills
  scripts/albion-item/scan/out/spells.xml          định nghĩa skill (active/passive) + mô tả
  scripts/albion-item/scan/out/localization.xml    map @TAG -> tên (EN-US, VI-VN)

Luồng:
  1. Parse 3 XML (iterparse stream, bộ nhớ thấp).
  2. Lọc ITEM TRANG BỊ theo slottype (mainhand/offhand/head/armor/shoes/cape/bag).
  3. Gom mỗi item: stats, enchant (@0..@N), full skill pool (active + passive).
     - Resolve `craftingspelllist reference=` (item nhánh thừa hưởng Q/W/passive từ gốc;
       giữ E riêng + removespell dùng để bỏ skill của base).
  4. Merge tên/mô tả skill từ spells.xml + localization. Schema v2.
  5. (tùy chọn) --with-translations: đọc map VI (tnc_albion_translations_v1.json) và
     gắn name_vi/desc_vi vào blob.
  6. Lưu lên Supabase qua save_json (key tnc_albion_item_v1.json).

Chạy độc lập (không chạy bot). Lệnh:
  python scripts/build_albion_item_db.py [--with-translations]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_here)
sys.path.append(_REPO_ROOT)
sys.path.append(os.path.join(_REPO_ROOT, "bot"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:
    pass

from core.storage import load_json, save_json  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("albion_item_db")

# ── Dump sẵn đang nằm ở scan/out (thư mục gitignored) ─────────────────────
DUMP_DIR = os.path.join(_here, "albion-item", "scan", "out")
ITEMS_XML = os.path.join(DUMP_DIR, "items.xml")
SPELLS_XML = os.path.join(DUMP_DIR, "spells.xml")
LOCALIZATION_XML = os.path.join(DUMP_DIR, "localization.xml")

STORAGE_KEY = "tnc_albion_item_v1.json"            # blob trên Supabase json_storage
TRANSLATION_KEY = "tnc_albion_translations_v1.json"  # map VI từ translate script

EQUIP_SLOTS = {"mainhand", "offhand", "head", "armor", "shoes", "cape", "bag"}

STAT_ATTRS = (
    "tier", "slottype", "itempower", "weight", "durability",
    "physicalarmor", "magicresistance", "hitpointsmax", "hitpointsregenerationbonus",
    "energymax", "energyregenerationbonus", "crowdcontrolresistance",
    "attackdamage", "attackspeed", "attackrange", "attacktype", "twohanded",
    "activespellslots", "passivespellslots",
    "movespeed", "movespeedbonus", "maxload", "abilitypower",
    "physicalattackdamagebonus", "magicattackdamagebonus",
    "physicalspelldamagebonus", "magicspelldamagebonus", "healbonus",
    "magiccooldownreduction", "magiccasttimereduction", "threatbonus", "healmodifier",
)

SPELL_ATTRS = (
    "target", "category", "castingtime", "castrange", "energyusage",
    "standtime", "recastdelay", "disruptionfactor", "channel_time",
    "hitdelay", "stacks", "minrange", "maxrange",
)

_TAG_PREFIXES = ("@ITEMS_", "@SPELLS_")


# ── Localization ───────────────────────────────────────────────────────────
def load_localizations(path: str) -> dict:
    """localization.xml -> {tag: {"EN-US": str, "VI-VN": str}}."""
    loc: dict = {}
    if not os.path.exists(path):
        logger.warning("thiếu %s", path)
        return loc
    ns = "{http://www.w3.org/XML/1998/namespace}"
    for _, tag in ET.iterparse(path, events=("end",)):
        if tag.tag == "tu":
            tuid = tag.get("tuid", "")
            if tuid.startswith("@") and tuid.startswith(_TAG_PREFIXES):
                entry = {}
                for tuv in tag.findall("tuv"):
                    lang = tuv.get(ns + "lang")
                    if lang in ("EN-US", "VI-VN"):
                        seg = tuv.find("seg")
                        entry[lang] = (seg.text or "").strip() if seg is not None else ""
                if entry.get("EN-US"):
                    loc[tuid] = entry
            tag.clear()
    logger.info("localizations: %d tags", len(loc))
    return loc


def _name(loc: dict, tag: str, fallback: str) -> tuple[str, str]:
    """Trả (EN, VI) từ tag. VI rỗng nếu chưa dịch."""
    entry = loc.get(tag, {})
    return entry.get("EN-US") or fallback, entry.get("VI-VN") or ""


# ── Spells ────────────────────────────────────────────────────────────────
def load_spells(spell_xml: str, loc: dict) -> dict:
    """spells.xml -> {uid: {kind, name_en, name_vi, desc_en, desc_vi, attrs}}."""
    spells: dict = {}
    if not os.path.exists(spell_xml):
        return spells
    for _, elem in ET.iterparse(spell_xml, events=("end",)):
        if elem.tag not in ("activespell", "passivespell"):
            continue
        uid = elem.get("uniquename")
        if not uid:
            continue
        name_tag = elem.get("namelocatag", "")
        if not name_tag.startswith("@"):
            name_tag = f"@SPELLS_{uid}"
        name_en, name_vi = _name(loc, name_tag, uid)

        desc_tag = elem.get("descriptionlocatag", "")
        if not desc_tag.startswith("@"):
            desc_tag = next(
                (c for c in (f"@SPELLS_{uid}_V2_DESC", f"@SPELLS_{uid}_DESC") if c in loc), ""
            )
        desc_en, desc_vi = _name(loc, desc_tag, "") if desc_tag else ("", "")

        attrs = {k: v for k, v in elem.attrib.items() if k in SPELL_ATTRS}
        spells[uid] = {
            "kind": elem.tag,
            "name_en": name_en, "name_vi": name_vi,
            "desc_en": desc_en, "desc_vi": desc_vi,
            "attrs": attrs,
        }
        elem.clear()
    logger.info("spells: %d", len(spells))
    return spells


# ── Items ─────────────────────────────────────────────────────────────────
def _tier_of(uid: str) -> int:
    m = re.match(r"T(\d)", uid)
    return int(m.group(1)) if m else 0


def parse_items(items_xml: str, spells: dict, raw_map: dict) -> tuple[dict, dict]:
    """items.xml -> (items {uid: item dict v2}, skipped stats).

    - Thu thập mọi item trang bị theo slottype.
    - Resolve `craftingspelllist reference=` đệ quy (cycle-guard) để item nhánh
      thừa hưởng Q/W/passive pool từ item gốc; `removespell` trên item nhánh sẽ
      bỏ skill tương ứng của base; craftspell riêng (vd E unique) ghi đè.
    - Passive (PASSIVE_* trong pool) tách thành spells.passive.
    """
    data: dict = {}
    skipped = {"non_equip": 0, "dup": 0}
    if not os.path.exists(items_xml):
        return {}, skipped

    for _, elem in ET.iterparse(items_xml, events=("end",)):
        if elem.tag not in ("equipmentitem", "weapon", "armor", "capeitem"):
            continue
        uid = elem.get("uniquename", "")
        if not uid:
            continue
        slot = elem.get("slottype", "").lower()
        if slot not in EQUIP_SLOTS:
            skipped["non_equip"] += 1
            continue

        base_key = uid.split("@")[0]

        stats = {a: elem.get(a) for a in STAT_ATTRS if a in elem.attrib}
        ench = {}
        for ens in elem.findall("enchantments"):
            for en in ens.findall("enchantment"):
                lvl = en.get("enchantmentlevel", "0")
                key = base_key if lvl == "0" else f"{base_key}@{lvl}"
                ench[key] = {a: en.get(a) for a in STAT_ATTRS if a in en.attrib}
        if not ench:
            ench[base_key] = stats

        # own spell entries (kể cả PASSIVE_) + reference
        own_spells: list = []
        ref: str | None = None
        for csl in elem.findall("craftingspelllist"):
            if ref is None:
                ref = csl.get("reference") or None
            for sp in csl:
                if sp.tag not in ("craftspell", "removespell"):
                    continue
                sid = sp.get("uniquename")
                if sid:
                    own_spells.append({
                        "id": sid,
                        "slot": sp.get("slots", ""),
                        "tag": sp.get("tag", ""),
                        "remove": sp.tag == "removespell",
                    })

        branch = (elem.get("craftingcategory") or "").upper()
        subcat = (elem.get("shopsubcategory1") or "").upper()
        en, vi = _name(raw_map, f"@ITEMS_{base_key}", base_key)

        data[base_key] = {
            "name_en": en, "name_vi": vi,
            "slottype": slot, "tier": _tier_of(base_key),
            "branch": branch, "subcat": subcat,
            "stats": stats,
            "enchant": {k: v for k, v in ench.items() if k != base_key},
            "own_spells": own_spells,
            "ref": ref,
        }
        elem.clear()
    logger.info("raw items: %d (skip non-equip %d)", len(data), skipped["non_equip"])

    # ── Resolve reference (DFS transitive, cycle-guard) ─────────────────
    memo = {}
    def _resolve(key: str, seen: frozenset) -> tuple[dict, dict]:
        if key in memo:
            return memo[key]
        if key not in data or key in seen:
            return {}, {}
        node = data[key]
        seen2 = seen | {key}
        active: dict = {}
        passive: dict = {}
        if node["ref"] and node["ref"] in data and node["ref"] not in seen2:
            base_a, base_p = _resolve(node["ref"], seen2)
            active = dict(base_a)
            passive = dict(base_p)
        # Removespell: gỡ skill id khỏi pool (base skills bị thay)
        for sid in (s["id"] for s in node["own_spells"] if s["remove"]):
            active.pop(sid, None)
            passive.pop(sid, None)
        # Craftspell: thêm (unique) / ghi đè nếu trùng id
        for s in node["own_spells"]:
            if s["remove"]:
                continue
            bucket = passive if s["id"].startswith("PASSIVE_") else active
            bucket[s["id"]] = {"id": s["id"], "slot": s["slot"], "tag": s["tag"]}
        memo[key] = (active, passive)
        return memo[key]

    def _root(key: str) -> str:
        seen = set()
        cur = key
        while cur in data and data[cur]["ref"] and data[cur]["ref"] in data and cur not in seen:
            seen.add(cur)
            cur = data[cur]["ref"]
        return cur

    items: dict = {}
    for key in data:
        active, passive = _resolve(key, frozenset())

        def _to_dict(s: dict) -> dict:
            info = spells.get(s["id"], {})
            return {
                "id": s["id"],
                "slot": s["slot"],
                "tag": s["tag"],
                "name_en": info.get("name_en", s["id"]),
                "name_vi": info.get("name_vi", ""),
                "desc_en": info.get("desc_en", ""),
                "desc_vi": info.get("desc_vi", ""),
            }

        act_list = [_to_dict(s) for s in active.values()]
        pas_list = [_to_dict(s) for s in passive.values()]
        root = _root(key)
        items[key] = {
            "unique_name": key,
            "name": data[key]["name_en"],
            "name_vi": data[key]["name_vi"],
            "slottype": data[key]["slottype"],
            "tier": data[key]["tier"],
            "branch": data[key]["branch"],
            "subcat": data[key]["subcat"],
            "ref_base": root if root != key else None,
            "stats": data[key]["stats"],
            "enchant": data[key]["enchant"],
            "spells": {
                "active": act_list,
                "passive": pas_list,
                "passive_count": len(pas_list),
            },
        }
    logger.info("items resolved: %d", len(items))
    return items, skipped


def apply_translations(items: dict, tr: dict) -> None:
    """Gắn name_vi/desc_vi (từ map translate) vào item + spell trong blob."""
    tr_spells = tr.get("spells", {})
    tr_items = tr.get("items", {})
    for key, item in items.items():
        try:
            nv = tr_items.get(key, {}).get("name_vi")
        except AttributeError:
            nv = None
        if nv:
            item["name_vi"] = nv
        for grp in ("active", "passive"):
            for s in item["spells"].get(grp, []):
                m = tr_spells.get(s["id"], {})
                if m.get("name_vi"):
                    s["name_vi"] = m["name_vi"]
                if m.get("desc_vi"):
                    s["desc_vi"] = m["desc_vi"]


# ── main ─────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Build item DB Albion (scheme v2).")
    parser.add_argument("--with-translations", action="store_true",
                        help="merge map VI (tnc_albion_translations_v1.json) vào blob")
    parser.add_argument("--dry-run", action="store_true",
                        help="parse + in mẫu nhưng KHÔNG ghi lên Supabase")
    args = parser.parse_args()

    if not os.path.isdir(DUMP_DIR):
        logger.error("Chưa có thư mục XML (%s). Chạy albiondata-bin-dumper DumpAllXML trước.", DUMP_DIR)
        sys.exit(1)

    loc = load_localizations(LOCALIZATION_XML)
    spells = load_spells(SPELLS_XML, loc)
    items, skipped = parse_items(ITEMS_XML, spells, loc)

    if args.with_translations:
        tr = load_json(TRANSLATION_KEY, {}) or {}
        apply_translations(items, tr)
        logger.info("Đã merge translations từ %s (%d spells, %d items)",
                    TRANSLATION_KEY, len(tr.get("spells", {})), len(tr.get("items", {})))

    payload = {
        "meta": {
            "schema_version": 2,
            "ref_resolved": True,
            "source": "GameData items.bin/spells.bin/localization.bin (local)",
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count_items": len(items),
        },
        "items": items,
    }

    size_mb = len(json.dumps(payload).encode("utf-8")) / 1024 / 1024

    # Mẫu kiểm chứng cho biết resolve ref đã thành công
    for sample in ("T4_2H_AXE", "T4_MAIN_AXE", "T4_MAIN_SWORD"):
        it = items.get(sample)
        if it:
            act = it["spells"]["active"]
            pas = it["spells"]["passive"]
            logger.info(
                "MẪU %s: active=%d passive=%d ref_base=%s | Q: %s",
                sample, len(act), len(pas), it["ref_base"],
                ", ".join(x["id"] for x in act if x["slot"] == "1") or "—",
            )

    if args.dry_run:
        logger.info("[dry-run] %d items (%.2f MB) — không ghi lên Supabase.", len(items), size_mb)
        return

    try:
        save_json(payload, STORAGE_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.error("Lưu Supabase thất bại: %s", exc)
        sys.exit(1)

    logger.info("Đã lưu %d items (%.2f MB) → %s", len(items), size_mb, STORAGE_KEY)

    # Verify đọc lại
    back = load_json(STORAGE_KEY, {})
    n = len(back.get("items", {})) if isinstance(back, dict) else 0
    logger.info("Verify load lại: %d items từ Supabase.", n)


if __name__ == "__main__":
    main()