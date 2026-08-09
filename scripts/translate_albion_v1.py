"""
translate_albion_v1.py — Dịch tên/mô tả skill Albion sang tiếng Việt (Gemini free).

Đọc spells.xml (skill đã parse) + blob tnc_albion_item_v1.json (để biết skill nào
thuộc item trang bị) → gọi Gemini (free) dịch name/desc EN → VI, lưu map riêng
`tnc_albion_translations_v1.json` (-> Supabase qua save_json).

Resume: skip key đã có name_vi/desc_vi. `--dry-run` in số pending.

`--redo-broken`: dịch lại những skill ĐÃ CÓ bản dịch nhưng bị "bỏ rơi câu" (cụt ý)
hoặc để trống desc_vi — theo heuristic:
  - desc_vi rỗng hoàn toàn; HOẶC
  - desc_vi thiếu tham chiếu số so với desc_en (vd giữ "{0}" mất "{1}"); HOẶC
  - desc_en ≥ 2 dòng && desc_vi 1 dòng && len(desc_vi)/len(desc_en) < 0.6
    (dấu hiệu mô tả bị cô còn 1 câu).
Sau khi parse, script tự verify: ref-set(desc_vi) phải đủ bằng ref-set(desc_en),
thiếu thì gọi lại tối đa 2 vòng; vẫn thiếu thì warning kèm id (không im lặng).

Usage (từ repo root):
  python scripts/translate_albion_v1.py [--batch-size 30] [--max-calls 300] [--dry-run] [--redo-broken]
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
    load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=False)
    # Ưu tiên key MỚI nhất do user thêm bằng dòng ĐẦU TIÊN trong .env
    # (dotenv đọc cuối thắng nên có thể chọn nhầm key cũ hết quota)
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

GEMINI_MODEL = "gemini-3.5-flash"             # model mới 2026 (2.x-flash hết hạn cho user mới)
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + GEMINI_MODEL
    + ":generateContent"
)

# Batch mỗi lần gọi: số skill (name + desc) đưa vào 1 lời dịch.
DEFAULT_BATCH = 30
DEFAULT_MAX_CALLS = 300   # an toàn quota free (~1.500 req/ngày)

# Tham chiếu số giữ nguyên khi dịch: {0}, {1}, $$path.field$, $field$
_REF_RE = re.compile(r"\{\d+\}|\$\$[\w.\[\]]+|\$[\w.\[\]]+")


def _refs(t: str) -> set[str]:
    """Tập placeholder số/refs cần GIỮ NGUYÊN khi dịch (đối chiếu EN vs VI)."""
    return set(_REF_RE.findall(t or ""))


SYSTEM_PROMPT = """\
Bạn là dịch giả tiếng Việt chuyên thuật ngữ game Albion Online. Dịch "sát nghĩa nhất":
giữ nguyên ý kỹ thuật, không thêm giải thích, không diễn giải.

Quy tắc:
- Tên skill: ngắn gọn, đúng thuật ngữ game (vd "Whirlwind" -> "Lốc Xoáy", "Dash" -> "Lướt").
- Mô tả: dịch ĐẦY ĐỦ TỪNG CÂU của bản gốc, không bỏ sót câu nào, không tóm tắt.
  Giữ nguyên: số câu/đoạn (mỗi câu gốc là 1 dòng riêng), thẻ [dmg]...[/dmg], [cc]...[/cc],
  [other]...[/other], [debuff]...[/debuff], [mobility]...[/mobility], [buff]...[/buff],
  và TUYỆT ĐỐI giữ nguyên các chỗ trống số/placeholder như {0}, {1}, $$field$$, $field$.
- Chỉ trả về kết quả dịch, không viết thêm lời dẫn hay ghi chú.

Cấu trúc trả về — mỗi skill là 1 block, theo đúng mẫu (quan trọng: dòng `##<STT>` đứng một mình):
##1
Tên: <tên_dịch>
<dòng 1 mô tả đã dịch>
<dòng 2 mô tả đã dịch (nếu có)>
##2
Tên: <tên_dịch>
<dòng 1 mô tả đã dịch>
...

- Mô tả nhiều câu thì giữ NHIỀU DÒNG như bản gốc (mỗi câu 1 dòng), KHÔNG gộp thành 1 dòng.
- Nếu bản gốc Không có mô tả, để trống block mô tả (chỉ mỗi dòng `Tên: ...`).
"""


def _call_gemini_sync(system: str, parts: list[dict], api_key: str, timeout: int = 120) -> str:
    """Gọi Gemini generateContent đồng bộ. Raise RuntimeError khi lỗi (kể cả lỗi mạng). Trả (text, retry_after)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": parts}],
    }
    headers = {"x-goog-api-key": api_key}   # key AQ (auth key 2026): truyền qua header, KHÔNG ?key=
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Gọi Gemini lỗi: {exc}") from exc
    if resp.status_code == 429:
        # Đang vượt quota free (20 rpm) — Google gửi Retry-After; chờ đúng thời gian đó.
        retry = resp.headers.get("Retry-After")
        wait = min(float(retry) if retry else 60.0, 300.0)
        raise RuntimeError(f"429 quota — chờ {wait:.0f}s rồi thử lại.", wait)
    if resp.status_code != 200:
        raise RuntimeError(resp.text[:400])
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini trả về format thiếu candidates.")


def _parse_reply(text: str, batch: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """Parse reply Gemini (block `##STT` + Tên + các dòng mô tả) → (done_dict, issues).

    issues = list id chưa dịch được (thiếu STT / thiếu Tên).
    """
    items_by_stt = {i + 1: item for i, item in enumerate(batch)}
    out: dict[str, dict] = {}
    missing: list[str] = []

    blocks = re.split(r"(?m)^##\s*(\d+)\s*$", text)
    i = 1
    while i + 1 < len(blocks):
        stt = blocks[i]
        if stt.isdigit():
            body = blocks[i + 1] if i + 1 < len(blocks) else ""
            body = body.strip("\n")
            item = items_by_stt.get(int(stt))
            if item:
                lines = [ln for ln in (body or "").splitlines()]
                # dòng Tên: ... lấy name_vi, phần còn lại là mô tả (nối \n)
                name = ""
                desc_parts: list[str] = []
                for ln in lines:
                    m = re.match(r"^\s*Tên\s*[:：]\s*(.*?)\s*$", ln)
                    if m:
                        name = m.group(1).strip()
                    else:
                        desc_parts.append(ln.rstrip())
                desc = "\n".join(d for d in desc_parts if d.strip())
                if name:
                    out[item["id"]] = {"name_vi": name, "desc_vi": desc}
                else:
                    missing.append(item["id"])
            i += 2
        else:
            i += 1
    return out, missing


def _is_broken(desc_en: str, desc_vi: str) -> bool:
    """Heuristic skill bị dịch hỏng cần dịch lại (--redo-broken).

    So với desc_vi ĐANG CÓ: khóa chặt theo content — MỌI skill đang có bản dịch
    ("single-French-line" legacy) đều bị gắn cờ để dịch lại theo format đầy đủ mới.
    """
    de = desc_en or ""
    dv = desc_vi or ""
    if not dv.strip():
        return True
    # desc_vi thiếu tham chiếu số so với desc_en → chắc chắn mất câu chứa nó
    if _refs(de) and not _refs(de) <= _refs(dv):
        return True
    # desc_en nhiều câu, desc_vi cô còn 1 dòng ngắn hơn hẳn → nghi cụt câu
    def _nlines(t: str) -> int:
        return len([x for x in (t or "").splitlines() if x.strip()])
    if _nlines(de) >= 2 and _nlines(dv) == 1 and len(dv) < 0.6 * len(de):
        return True
    return False


def _refs_missing(done: dict[str, dict], batch: list[dict]) -> list[dict]:
    """Trả list skill trong batch CÒN thiếu refs/desc_vi (để gọi dịch lại vòng 2/3)."""
    need = []
    for it in batch:
        val = done.get(it["id"]) or {}
        de = it.get("desc_en") or ""
        dv = val.get("desc_vi") or ""
        if not dv.strip():
            need.append(it)
        elif _refs(de) and not _refs(de) <= _refs(dv):
            need.append(it)
    return need


def _run_batch(batch, api_key, out, attempts=3):
    """Gọi Gemini cho 1 batch; dịch lại tối đa 2 vòng nếu còn thiếu refs/câu; cập nhật out."""
    def _call(items: list[dict]) -> dict:
        if not items:
            return {}
        parts = [
            {"text": f"{i} | name_en: {it['name_en']} | desc_en: {it['desc_en'] or '-'}"}
            for i, it in enumerate(items, 1)
        ]
        last_err = None
        for retry in range(1, attempts + 1):
            try:
                reply = _call_gemini_sync(SYSTEM_PROMPT, parts, api_key)
            except RuntimeError as exc:
                last_err = exc
                wait = exc.args[1] if len(exc.args) > 1 else 4 * retry
                logger.warning("  [%d/%d] lỗi %s — chờ %ds", retry, attempts, exc, wait)
                time.sleep(wait)
                continue
            parsed, missing = _parse_reply(reply, items)

            # Vòng 2: gom skill còn thiếu (desc rỗng/thiếu refs/không có Tên) để dịch lại
            redo = _refs_missing(parsed, items) + [it for it in items if it["id"] in missing]
            if redo:
                logger.info("  %d/%d skill còn thiếu câu/ref — dịch lại lần 2", len(redo), len(items))
                retry_items = [it for it in items if it["id"] in {r["id"] for r in redo}]
                for attempt2 in range(1, 3):
                    try:
                        reply2 = _call_gemini_sync(
                            SYSTEM_PROMPT,
                            [{"text": f"{i} | name_en: {it['name_en']} | desc_en: {it['desc_en'] or '-'}"}
                             for i, it in enumerate(retry_items, 1)],
                            api_key,
                        )
                    except RuntimeError as exc2:
                        wait2 = exc2.args[1] if len(exc2.args) > 1 else 6
                        logger.warning("  [redo %d/2] lỗi %s — chờ %ds", attempt2, exc2, wait2)
                        time.sleep(wait2)
                        continue
                    parsed2, missing2 = _parse_reply(reply2, retry_items)
                    for k, v in parsed2.items():
                        parsed[k] = v
                    retry_items = [it for it in retry_items if it["id"] in missing2] + \
                        _refs_missing(parsed, retry_items)
                    if not retry_items:
                        break
                still = [it["id"] for it in retry_items]
                if still:
                    logger.warning("  VẪN thiếu câu/ref: %s", ", ".join(sorted(still)))
            for key, val in parsed.items():
                out[key] = val
            logger.info("  batch đã dịch %d/%d", len(parsed), len(items))
            return parsed
        raise RuntimeError(f"Gọi Gemini thất bại hoàn toàn: {last_err}")
    _call(batch)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dịch skill item Albion EN→VI bằng Gemini free.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--redo-broken", action="store_true",
                        help="Dịch LẠI những skill đã có bản dịch nhưng bị cụt câu/bỏ trống desc_vi.")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("Thiếu GEMINI_API_KEY trong .env — cần để dịch thật (dry-run vẫn chạy).")
        if not args.dry_run:
            sys.exit(1)
    # Nếu .env có NHIỀU dòng GEMINI_API_KEY (key dự phòng do user giữ lại):
    # chọn dòng ĐẦU TIÊN (key mới nhất user thêm) — dòng cuối chỉ dùng khi thiếu.
    env_path = os.path.join(_REPO_ROOT, ".env")
    if os.path.exists(env_path):
        key_first = ""
        for line in open(env_path, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                key_first = line.split("=", 1)[1].strip()
                break
        if key_first:
            api_key = key_first

    if not args.redo_broken and not api_key:
        if args.dry_run:
            logger.info("[dry-run] thiếu key — chỉ đếm pending, không gọi API.")
        else:
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

    skill_samples: dict[str, dict] = {}
    for it in items.values():
        for grp in ("active", "passive"):
            for s in it.get("spells", {}).get(grp, []):
                if s.get("id") not in skill_samples and s.get("name_en"):
                    skill_samples[s["id"]] = s

    tr = load_json(TRANSLATION_KEY, {}) or {}
    tr_spells = tr.get("spells", {}) if isinstance(tr, dict) else {}

    # entries = skill cần dịch: default chỉ skill CHƯA có name_vi; --redo-broken dịch kèm skill hỏng
    entries: list[dict] = []
    for sid in sorted(skill_samples):
        sample = skill_samples[sid]
        existing = tr_spells.get(sid, {}) or {}
        has_trans = bool(existing.get("name_vi"))
        if not has_trans:
            entries.append({
                "id": sid,
                "name_en": sample.get("name_en", ""),
                "desc_en": sample.get("desc_en", ""),
            })
        elif args.redo_broken and _is_broken(sample.get("desc_en", ""), existing.get("desc_vi", "")):
            entries.append({
                "id": sid,
                "name_en": sample.get("name_en", ""),
                "desc_en": sample.get("desc_en", ""),
            })

    logger.info("pending dịch: %d skill (%s)", len(entries),
                "redo-broken" if args.redo_broken else "chưa có bản dịch")
    if args.dry_run:
        logger.info("[dry-run] sẽ gọi ~%d lần (batch %d). Không gọi API.",
                    -(-len(entries) // args.batch_size) if entries else 0, args.batch_size)
        return

    def _checkpoint() -> None:
        """Lưu map tạm sau mỗi batch — khi crash giữa chừng, lần sau resume không mất công dịch lại."""
        for sid, val in out.items():
            tr_spells.setdefault(sid, {}).update(val)
        final = {"meta": {"model": GEMINI_MODEL, "generated_n": len(tr_spells)}, "spells": tr_spells}
        try:
            save_json(final, TRANSLATION_KEY)
        except Exception as exc:  # noqa: BLE001
            logger.error("Checkpoint lưu Supabase thất bại (tiếp tục dịch): %s", exc)

    out: dict[str, dict] = {}
    start = 0
    calls = 0
    while start < len(entries) and calls < args.max_calls:
        batch = _build_batch(entries, start, args.batch_size)
        _run_batch(batch, api_key, out, attempts=2)
        start += len(batch)
        calls += 1
        if start < len(entries):
            time.sleep(3)   # rate-limit: 3s/batch (quota free ~20 rpm)
    logger.info("Đã dịch %d skill trong %d calls.", len(out), calls)
    _checkpoint()

    logger.info("Đã lưu %d skills map → %s", len(tr_spells), TRANSLATION_KEY)


def _build_batch(entries: list[dict], start: int, size: int) -> list[dict]:
    """Cắt batch từ entries (mỗi entry có id/name_en/desc_en)."""
    return entries[start:start + size]


if __name__ == "__main__":
    main()