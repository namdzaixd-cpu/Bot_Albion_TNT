"""
albion_item.py — Truy cập dữ liệu item trang bị Albion (blob tnc_albion_item_v1.json).

Dùng chung cho /iteminfo (cog) và chat_ai hook. Tránh load blob nặng mỗi tin nhắn:
lazy-load + TTL cache 6h. Không crash khi Supabase lỗi → trả []/"".

Schema blob (v2, từ scripts/build_albion_item_db.py):
  {meta, items: {
    "T4_2H_AXE": {unique_name, name, name_vi, slottype, tier, branch, subcat,
                  ref_base, stats, enchant, spells:{active:[{id,slot,tag,name_en,
                  name_vi,desc_en,desc_vi}], passive:[...], passive_count}}
  }}
"""
from __future__ import annotations

import logging
import time
import unicodedata

from ..storage import load_json

logger = logging.getLogger("bot.albion_item")

INDEX_KEY = "tnc_albion_item_v1.json"
CACHE_TTL = 6 * 3600  # 6h: làm mới khi game update / force

_SLOT_LABELS = {
    "mainhand": "Vũ khí (tay chính)",
    "offhand": "Tay phụ",
    "head": "Mũ",
    "armor": "Giáp",
    "shoes": "Giày",
    "cape": "Áo choàng",
    "bag": "Túi",
}
_SLOT_LETTERS = {"1": "Q", "2": "W", "3": "E", "": "R"}

_index: dict | None = None
_index_ts: float = 0.0


def load_items(force: bool = False) -> dict | None:
    """Load + cache blob. Trả {"items", "by_name"} hoặc None nếu lỗi."""
    global _index, _index_ts
    now = time.time()
    if force or _index is None or now - _index_ts > CACHE_TTL:
        try:
            data = load_json(INDEX_KEY, {}) or {}
            items = data.get("items", {}) if isinstance(data, dict) else {}
            _index = {
                "items": items,
                "by_name": {k.lower(): uid for uid, it in items.items() for k in (it.get("name", ""), it.get("name_vi", "")) if k},
            }
            _index_ts = now
            logger.info("Đã load %d items Albion vào cache.", len(items))
        except Exception as exc:  # noqa: BLE001
            logger.warning("load_items thất bại: %s", exc)
            _index = None
    return _index


def _norm(s: str) -> str:
    """Bỏ dấu + lowercase (NFKD), giống chat_ai._norm_text."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def search_items(query: str, limit: int = 3) -> list[tuple[str, dict]]:
    """Tìm item theo tên EN/VI/id.

    Scoring (giảm dần ưu tiên):
      100+ = tên norm trùng chính xác
      50   = query 1 từ, tên có chứa nguyên từ đó (substring per token)
      10/ từ = mỗi token query đều substring trong tên (từ ghép kiểu 'greataxe')
      1/ từ = token-overlap
    Trả list [(uid, item)] giảm dần theo độ khớp, tối đa limit.
    """
    idx = load_items()
    if not idx:
        return []
    q_raw = (query or "").strip().lower()
    q = _norm(query).strip()
    if not q:
        return []
    q_nospace = q.replace(" ", "")
    q_words = [w for w in q.split() if w]
    scored: list[tuple[int, str, dict]] = []
    for uid, it in idx["items"].items():
        name_n = _norm(it.get("name", ""))
        namevi_n = _norm(it.get("name_vi", ""))
        name_raw = (it.get("name", "") or "").lower()
        hay = f"{name_n} {namevi_n} {uid}"
        hay_nospace = hay.replace(" ", "")
        if name_n == q or namevi_n == q or uid.lower() == q_nospace:
            score = 100
        elif len(q_words) == 1:
            # query 1 từ: substring trong tên (bắt 'axe'→'greataxe')
            score = 50 if q_words[0] in hay_nospace else 0
            # tiếng Việt: ưu tiên tên thật có chứa từ gốc (giữ dấu)
            if score and q_raw in name_raw:
                score = 60
        else:
            # multi-word: đếm token nào substring trong tên
            score = 10 * sum(1 for w in q_words if w in hay_nospace)
        if score:
            scored.append((score, uid, it))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [(uid, it) for _, uid, it in scored[:limit]]


def _vi(it, s, key):
    """name_vi nếu có, fallback name_en."""
    v = (s or {}).get(f"{key}_vi") or ""
    return v or (s or {}).get(f"{key}_en") or ""


def format_item_full(uid: str, item: dict, max_desc: int = 1200) -> str:
    """Render block text tiếng Việt đầy đủ (tên/tier/slot/branch/enchant/skills)."""
    if not item:
        return f"⚠ Không có dữ liệu item `{uid}`."
    name = item.get("name_vi") or item.get("name") or uid
    name_en = item.get("name") or ""
    lines = [f"**{name}**"]
    if name_en and name_en != name:
        lines.append(f"*{name_en}*")
    lines.append(f"`{uid}`")

    slot = _SLOT_LABELS.get(item.get("slottype", ""), item.get("slottype", ""))
    tier = item.get("tier", "")
    lines.append(f"🛡️ {slot} | Cấp {tier}" + (f" | Nhánh: {item.get('branch','')}" if item.get("branch") else ""))

    stats = item.get("stats", {}) or {}
    parts = []
    for label, k in (("IP", "itempower"), ("ATK", "attackdamage"), ("HP", "hitpointsmax"),
                     ("Def", "physicalarmor"), ("Mag", "magicresistance"),
                     ("Năng", "energymax"), ("Move", "movespeed")):
        if stats.get(k):
            parts.append(f"{label} {stats[k]}")
    if parts:
        lines.append("📊 " + " | ".join(parts))

    # Enchant diff
    ench = item.get("enchant", {}) or {}
    if ench:
        ip0 = stats.get("itempower", "")
        ench_strs = []
        for lvl in ("1", "2", "3"):
            k = f"{uid}@{lvl}"
            e = ench.get(k) or ench.get(k.split('@')[0] + '@' + lvl)
            if not e:
                continue
            ip = e.get("itempower", "")
            if ip and ip != ip0:
                ench_strs.append(f"@lv{lvl}: IP {ip}")
        if ench_strs:
            lines.append("✨ " + " | ".join(ench_strs))

    spells = item.get("spells", {}) or {}
    active = spells.get("active", []) or []
    passive = spells.get("passive", []) or []

    # Gom theo slot Q/W/E/R
    grouped: dict[str, list] = {"Q": [], "W": [], "E": [], "R": []}
    for s in active:
        if s.get("remove"):
            continue
        letter = _SLOT_LETTERS.get(str(s.get("slot", "")), "R")
        grouped.setdefault(letter, []).append(s)

    lines.append("")  # separator
    for letter in ("Q", "W", "E", "R"):
        sl = grouped.get(letter) or []
        if not sl:
            continue
        lines.append(f"**{letter}**")
        for s in sl:
            nm = _vi(item, s, "name")
            desc = _vi(item, s, "desc")
            tag = f" ({s.get('tag','')})" if s.get("tag") else ""
            lines.append(f"• {nm}{tag}")
            if desc:
                d = desc if len(desc) <= max_desc else desc[:max_desc] + "…"
                lines.append(f"   *{d}*")

    if passive:
        lines.append(f"**Passive ({len(passive)})**")
        for s in passive:
            nm = _vi(item, s, "name")
            desc = _vi(item, s, "desc")
            lines.append(f"• {nm}")
            if desc:
                d = desc if len(desc) <= max_desc else desc[:max_desc] + "…"
                lines.append(f"   *{d}*")

    # Kiểm soát kích thước tin (Discord 2000 chars)
    text = "\n".join(lines)
    if len(text) > 1800:
        text = text[:1800] + "\n…"
    return text


def format_item_compact(uid: str, item: dict) -> str:
    """Bản gọn cho chat hook (ít dòng, tiết kiệm prompt token)."""
    if not item:
        return ""
    name = item.get("name_vi") or item.get("name") or uid
    line = f"- {name} (`{uid}`) | {_SLOT_LABELS.get(item.get('slottype',''), '')} Cấp {item.get('tier','')}"
    spells = item.get("spells", {}) or {}
    act = [s for s in spells.get("active", []) if not s.get("remove")]
    pas = spells.get("passive", []) or []
    skill_parts = []
    for s in act:
        nm = _vi(item, s, "name")
        skill_parts.append(nm)
    for s in pas:
        skill_parts.append(_vi(item, s, "name"))
    if skill_parts:
        line += " | " + ", ".join(skill_parts)
    return line
