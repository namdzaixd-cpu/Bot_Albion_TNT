"""
build_albion_item_db.py — Build database item trang bị Albion Online (stat/skill/passive).

Nguồn: file game cài local, đã giải mã bằng albiondata-bin-dumper (ao-data) thành XML:
  scripts/albion-item/out/items.xml           item + stat + enchant + active skills
  scripts/albion-item/out/spells.xml          định nghĩa skill (active/passive) + mô tả
  scripts/albion-item/out/localization.xml    map @TAG -> tên (EN-US, VI-VN)

Luồng:
  1. Parse 3 XML (iterparse stream, bộ nhớ thấp).
  2. Lọc ITEM TRANG BỊ theo slottype (mainhand/offhand/head/armor/shoes/cape/bag).
  3. Gom mỗi item: stats, enchant table (@0..@4), active skills (craftingspelllist),
     passive count, tên EN/VI (từ localization tag @ITEMS_<name>).
  4. Merge skill tên/mô tả EN (spells.xml + localization @SPELLS_<name>).
  5. Ghi dict chuẩn hóa lên Supabase qua save_json (khóa tnc_albion_item_v1.json).

Chạy độc lập (không chạy bot). Lệnh: python scripts/build_albion_item_db.py
Chi tiết + schema: docs/features/2026-08-09_Albion_Item_Database/01_plan.md
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# Cho phép import core.config khi chạy từ repo root / scripts/
_here = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_here)
sys.path.append(_REPO_ROOT)  # repo root
sys.path.append(os.path.join(_REPO_ROOT, "bot"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:
    pass

from core.storage import load_json, save_json  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("albion_item_db")

# ── Cấu hình ──────────────────────────────────────────────────────────────
DUMP_DIR = os.path.join(_here, "albion-item", "out")
ITEMS_XML = os.path.join(DUMP_DIR, "items.xml")
SPELLS_XML = os.path.join(DUMP_DIR, "spells.xml")
LOCALIZATION_XML = os.path.join(DUMP_DIR, "localization.xml")

STORAGE_KEY = "tnc_albion_item_v1.json"  # key trên Supabase json_storage

# Slottype là trang bị thật (equipment). Loại bỏ consumable (food/potion),
# và các slot không thuộc trang bị.
EQUIP_SLOTS = {
    "mainhand", "offhand", "head", "armor", "shoes", "cape", "bag",
}

# Attribute stat cần giữ (mask — tránh giữ quá nhiều attr rác của game)
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


# ── Localization loader ────────────────────────────────────────────────────
def load_localizations(path: str) -> dict:
    """Đọc localization.bin XML -> {tag: {"EN-US": str, "VI-VN": str}}."""
    loc: dict = {}
    if not os.path.exists(path):
        logger.warning("thiếu %s", path)
        return loc
    ns = "{http://www.w3.org/XML/1998/namespace}"
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "tu":
            tag = elem.get("tuid", "")
            if tag.startswith("@") and (tag.startswith("@ITEMS_") or tag.startswith("@SPELLS_")):
                entry = {}
                for tuv in elem.findall("tuv"):
                    lang = tuv.get(ns + "lang")
                    if lang in ("EN-US", "VI-VN"):
                        seg = tuv.find("seg")
                        txt = (seg.text or "").strip() if seg is not None else ""
                        entry[lang] = txt
                if entry.get("EN-US"):
                    loc[tag] = entry
            # Clear chính xác: chỉ clear tu (top-level), không clear tuv/seg
            # để các tuv vẫn còn attribute xml:lang khi tu về end.
            elem.clear()
    logger.info("localizations: %d tags (items + spells)", len(loc))
    return loc


def _name(loc: dict, tag: str, fallback: str) -> tuple[str, str]:
    """Trả (EN, VI) từ tag. VI rỗng nếu chưa dịch → fallback EN."""
    entry = loc.get(tag, {})
    en = entry.get("EN-US") or fallback
    vi = entry.get("VI-VN") or ""
    return en, vi


# ── Spells ────────────────────────────────────────────────────────────────
def load_spells(spell_xml: str, loc: dict) -> dict:
    """Đọc spells.xml → {uniquename: {name_en, name_vi, category, statblock, attrs}}."""
    spells: dict = {}
    if not os.path.exists(spell_xml):
        return spells
    for _, elem in ET.iterparse(spell_xml, events=("end",)):
        if elem.tag in ("activespell", "passivespell"):
            uid = elem.get("uniquename")
            if not uid:
                continue
            name_loc = elem.get("namelocatag", "")
            desc_loc = elem.get("descriptionlocatag", "")
            name_tag = name_loc if name_loc.startswith("@") else f"@SPELLS_{uid}"
            desc_en, desc_vi = _name(loc, desc_loc, "") if desc_loc.startswith("@") else ("", "")
            en, vi = _name(loc, name_tag, uid)
            attrs = {
                k: v for k, v in elem.attrib.items()
                if k in ("target", "category", "castingtime", "castrange", "energyusage",
                         "standtime", "recastdelay", "disruptionfactor", "channel_time",
                         "hitdelay", "stacks", "minrange", "maxrange")
            }
            spells[uid] = {
                "kind": elem.tag,
                "name_en": en,
                "name_vi": vi,
                "desc_en": desc_en,
                "desc_vi": desc_vi,
                "attrs": attrs,
            }
        elem.clear()
    logger.info("spells: %d", len(spells))
    return spells


def _tier_of(uid: str) -> int:
    m = re.match(r"T(\d)", uid)
    return int(m.group(1)) if m else 0


# ── Items ────────────────────────────────────────────────────────────────
def parse_items(items_xml: str, spells: dict, loc: dict) -> tuple[dict, dict]:
    """Đọc items.xml, lọc trang bị theo slottype, gom tree → dict {uid: item}."""
    items: dict = {}
    skipped = {"no_slot": 0, "non_equip": 0, "dup": 0}
    if not os.path.exists(items_xml):
        return items, skipped

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

        # parse main base key (bỏ @N già có của enchant riêng)
        base_key = uid.split("@")[0]

        # stat
        stats = {a: elem.get(a) for a in STAT_ATTRS if a in elem.attrib}
        # enchant table
        ench = {}
        for ens in elem.findall("enchantments"):
            for en in ens.findall("enchantment"):
                lvl = en.get("enchantmentlevel", "0")
                key = base_key if lvl == "0" else f"{base_key}@{lvl}"
                ench[key] = {a: en.get(a) for a in STAT_ATTRS if a in en.attrib}
        if not ench:  # mặc định: @0 với stat gốc
            ench[base_key] = stats

        # Skills trên item từ craftingspelllist: <craftspell> (active W/E/R) +
        # <removespell> (active Q thay thế skill mặc định). ID passive không nằm
        # ở items.xml — chỉ biết count qua attribute passivespellslots.
        active = []
        for csl in elem.findall("craftingspelllist"):
            for sp in csl:
                if sp.tag not in ("craftspell", "removespell"):
                    continue
                sid = sp.get("uniquename")
                if sid:
                    info = spells.get(sid, {})
                    active.append({
                        "id": sid,
                        "slot": sp.get("slots", ""),
                        "tag": sp.get("tag", ""),
                        "name_en": info.get("name_en", sid),
                        "name_vi": info.get("name_vi", ""),
                        "desc_en": info.get("desc_en", ""),
                        "remove": sp.tag == "removespell",
                    })
        passive_count = int(elem.get("passivespellslots", 0) or 0)

        # tên từ localization @ITEMS_<base>
        en, vi = _name(loc, f"@ITEMS_{base_key}", base_key)

        items[base_key] = {
            "unique_name": base_key,
            "name": en,
            "name_vi": vi or en,
            "slottype": slot,
            "tier": _tier_of(base_key),
            "stats": stats,
            "enchant": {k: v for k, v in ench.items() if k != base_key},
            "spells": {
                "active": active,
                "passive_count": passive_count,
            },
        }
        elem.clear()
    logger.info("items: %d equipment (skip non-equip %d)", len(items), skipped.get("non_equip", 0))
    return items, skipped


# ── main ─────────────────────────────────────────────────────────────────
def main() -> None:
    if not os.path.isdir(DUMP_DIR):
        logger.error("Chưa có output XML. Chạy albiondata-bin-dumper DumpAllXML trước (xem docs). Dir: %s", DUMP_DIR)
        sys.exit(1)

    loc = load_localizations(LOCALIZATION_XML)
    spells = load_spells(SPELLS_XML, loc)
    items, skipped = parse_items(ITEMS_XML, spells, loc)

    payload = {
        "meta": {
            "schema_version": 1,
            "source": "GameData items.bin/spells.bin/localization.bin (local machine)",
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count_items": len(items),
        },
        "items": items,
    }
    try:
        save_json(payload, STORAGE_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.error("Lưu Supabase thất bại: %s", exc)
        sys.exit(1)

    size_mb = len(json.dumps(payload).encode("utf-8")) / 1024 / 1024
    logger.info("Đã lưu %d items (%.2f MB) → %s", len(items), size_mb, STORAGE_KEY)

    # Verify đọc lại
    back = load_json(STORAGE_KEY, {})
    n = len(back.get("items", {})) if isinstance(back, dict) else 0
    logger.info("Verify load lại: %d items từ Supabase.", n)


if __name__ == "__main__":
    main()