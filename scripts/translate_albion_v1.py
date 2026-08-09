"""
translate_albion_v1.py — Dịch tên/mô tả skill Albion sang tiếng Việt (Gemini free).

Đọc spells.xml (skill đã parse) + blob tnc_albion_item_v1.json (để biết skill nào
thuộc item trang bị) → gọi Gemini (free) dịch name/desc EN → VI, lưu map riêng
`tnc_albion_translations_v1.json` (-> Supabase qua save_json).

Resume: skip key đã có name_vi/desc_vi. `--dry-run` in số pending.
Không cần GEMINI key để ghi map: chỉ cần khi thực hiện dịch thật.

Usage (từ repo root):
  python scripts/translate_albion_v1.py [--batch-size 30] [--max-calls 300] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time

import requests

_here = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_here)
sys.path.append(_REPO_ROOT)
sys.path.append(_here)  # chứa build_albion_item_db.py
sys.path.append(os.path.join(_REPO_ROOT, "bot"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:
    pass

from core.storage import load_json, save_json  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("translate_albion")

TRANSLATION_KEY = "tnc_albion_translations_v1.json"

DUMP_DIR = os.path.join(_here, "albion-item", "scan", "out")
ITEMS_XML = os.path.join(DUMP_DIR, "items.xml")
SPELLS_XML = os.path.join(DUMP_DIR, "spells.xml")
LOCALIZATION_XML = os.path.join(DUMP_DIR, "localization.xml")

GEMINI_MODEL = "gemini-2.0-flash-exp"          # gần chuẩn nhất mặc định
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + GEMINI_MODEL
    + ":generateContent"
)

# Batch mỗi lần gọi: số skill (name + desc) đưa vào 1 lời dịch.
DEFAULT_BATCH = 30
DEFAULT_MAX_CALLS = 300   # an toàn quota free (~1.500 req/ngày)

SYSTEM_PROMPT = """\
Bạn là dịch giả tiếng Việt chuyên thuật ngữ game Albion Online. Dịch "sát nghĩa nhất":
giữ nguyên ý kỹ thuật, không thêm giải thích, không diễn giải.

Quy tắc:
- Tên skill: ngắn gọn, đúng thuật ngữ game (vd "Whirlwind" -> "Lốc Xoáy", "Dash" -> "Lướt").
- Mô tả: giữ nguyên trọn ý kỹ thuật (sát thương, hồi chiêu, hiệu ứng, buff/debuff),
  giữ nguyên: số, đơn vị (%, giây, mét, T/S/M nếu là đơn vị), tên riêng không dịch,
  và các thẻ [dmg]...[/dmg] cũng loại giữ nguyên dạng.
- Chỉ trả về các dòng dịch, mỗi dòng định dạng:
  <STT> | <tên_dịch> | <mô_tả_dịch>
- Nếu mô tả nguồn rỗng, để "-" ở cột mô tả mà vẫn giữ STT và tên.
- Không viết thêm gì khác, không ghi chú.
"""

def _call_gemini_sync(system: str, parts: list[dict], api_key: str, timeout: int = 60) -> str:
    """Gọi Gemini generateContent đồng bộ. Raise RuntimeError khi lỗi."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": parts}],
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(resp.text[:400])
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini trả về format thiếu candidates.")


def _parse_reply(text: str, batch: list[dict]) -> dict[str, dict]:
    """Parse reply Gemini (STT | name | desc) → {item_key: done_dict}."""
    out: dict[str, dict] = {}
    items_by_stt = {i + 1: item for i, item in enumerate(batch)}
    for line in text.splitlines():
        m = re.match(r"^\s*(\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$", line)
        if not m:
            continue
        stt = int(m.group(1)); name = m.group(2).strip(); desc = m.group(3).strip()
        item = items_by_stt.get(stt)
        if not item:
            continue
        if name == "-":
            continue
        out[item["id"]] = {"name_vi": name, "desc_vi": ""}
        if desc and desc != "-":
            out[item["id"]]["desc_vi"] = desc
    return out


def _build_batch(entries: list[dict], start: int, size: int) -> list[dict]:
    """Cắt batch từ entries (mỗi entry có id/name_en/desc_en)."""
    return entries[start:start + size]


def _run_batch(batch, api_key, out, attempts=2):
    """Gọi Gemini cho 1 batch; retry 1-2 lần nếu lỗi; cập nhật out."""
    parts = []
    for i, it in enumerate(batch, 1):
        parts.append({"text": (
            f"{i} | name_en: {it['name_en']} | desc_en: {it['desc_en'] or '-'}"
        )})
    if not parts:
        return
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            reply = _call_gemini_sync(SYSTEM_PROMPT, parts, api_key)
        except RuntimeError as exc:
            last_err = exc
            logger.warning("  [%d/%d] lỗi %s — thử lại sau %ds", attempt, attempts, exc, 4 * attempt)
            time.sleep(4 * attempt)
            continue
        parsed = _parse_reply(reply, batch)
        for key, val in parsed.items():
            out[key] = val
        logger.info("  batch đã dịch %d/%d", len(parsed), len(batch))
        return
    logger.warning("  batch thất bại hoàn toàn: %s", last_err)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dịch skill item Albion EN→VI bằng Gemini free.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("Thiếu GEMINI_API_KEY trong .env — cần để dịch thật (dry-run vẫn chạy).")
        if not args.dry_run:
            sys.exit(1)

    # Xây set skill id thuộc item trang bị bằng chính parser build (XML trực tiếp,
    # không cần Supabase) → chỉ dịch những skill thật sự dùng trên item.
    try:
        from build_albion_item_db import load_localizations, load_spells, parse_items
    except ImportError:
        logger.error("Cần chạy từ repo root để import build script. Abort.")
        sys.exit(1)
    loc = load_localizations(LOCALIZATION_XML)
    spells = load_spells(SPELLS_XML, loc)
    items, _ = parse_items(ITEMS_XML, spells, loc)

    skill_ids: set[str] = set()
    for it in items.values():
        for grp in ("active", "passive"):
            for s in it.get("spells", {}).get(grp, []):
                skill_ids.add(s.get("id", ""))

    tr = load_json(TRANSLATION_KEY, {}) or {}
    tr_spells = tr.get("spells", {}) if isinstance(tr, dict) else {}

    # entries = skill CHƯA dịch (resume): cần ít nhất 1 trong name/desc
    entries: list[dict] = []
    for sid in sorted(skill_ids):
        sample = None
        for it in items.values():
            for grp in ("active", "passive"):
                for s in it.get("spells", {}).get(grp, []):
                    if s.get("id") == sid:
                        sample = s
                        break
                if sample:
                    break
            if sample:
                break
        if not sample:
            continue
        if not sample.get("name_en"):
            continue
        existing = tr_spells.get(sid, {})
        if existing.get("name_vi"):
            continue
        entries.append({
            "id": sid,
            "name_en": sample.get("name_en", ""),
            "desc_en": sample.get("desc_en", ""),
        })

    logger.info("pending dịch: %d skill",
                len(entries))
    if args.dry_run:
        logger.info("[dry-run] sẽ gọi ~%d lần (batch %d). Không gọi API.",
                    -(-len(entries) // args.batch_size), args.batch_size)
        return

    out: dict[str, dict] = {}
    start = 0
    calls = 0
    while start < len(entries) and calls < args.max_calls:
        batch = _build_batch(entries, start, args.batch_size)
        _run_batch(batch, api_key, out, attempts=2)
        start += len(batch)
        calls += 1
        if start < len(entries):
            time.sleep(1)   # rate-limit: 1 req/s ("free" an toàn)
    logger.info("Đã dịch %d skill trong %d calls.", len(out), calls)

    # merge với map cũ (giữ key chưa đụng)
    for sid, val in out.items():
        tr_spells.setdefault(sid, {}).update(val)
    final = {"meta": {"model": GEMINI_MODEL, "generated_n": len(tr_spells)}, "spells": tr_spells}
    try:
        save_json(final, TRANSLATION_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.error("Lưu map translation lên Supabase thất bại: %s", exc)
        sys.exit(1)
    logger.info("Đã lưu %d skills map → %s", len(tr_spells), TRANSLATION_KEY)


if __name__ == "__main__":
    main()