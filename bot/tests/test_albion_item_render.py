"""Test render item Albion: budget Discord 2000 + Passive luôn hiện + không vỡ markdown.

Không cần mạng/DB: fixture item synthetic (9 active + 4 passive, desc dài ~8800 ký tự).
"""
import pytest

from core.data.albion_item import DISCORD_MSG_LIMIT, format_item_full


def _mk_desc(core: str, n: int = 3) -> str:
    """Mô tả nhiều câu (có [dmg]...[/dmg] + placeholder)."""
    return "\n".join(
        f"{core} câu {i}: gây [dmg]{{0}} sát thương[/dmg], làm chậm $slow$ trong {i * 10} giây. "
        "Tiếp tục ảnh hưởng sau khi kết thúc và có hiệu ứng phụ kèm theo."
        for i in range(n)
    )


def _mk_item() -> dict:
    spells = {
        "active": [],
        "passive": [],
    }
    # 5 active trên Q, 2 trên W, 2 trên E (như NatureStaff 9 active)
    for slot, count in (("1", 5), ("2", 2), ("3", 2)):
        for i in range(count):
            spells["active"].append({
                "id": f"ACT_{slot}_{i}", "slot": slot, "tag": "DAMAGE",
                "name_en": f"Active S{slot}.{i}",
                "name_vi": f"Kỹ Năng {slot}.{i}",
                "desc_en": _mk_desc("EN"),
                "desc_vi": _mk_desc("VI"),
            })
    # 4 passive
    for i in range(4):
        spells["passive"].append({
            "id": f"PASSIVE_{i}", "name_en": f"Passive EN {i}",
            "name_vi": f"Thụ Động {i}",
            "desc_en": _mk_desc("ENP"),
            "desc_vi": _mk_desc("VIP"),
        })
    spells["passive_count"] = 4
    return {
        "unique_name": "T8_2H_TEST",
        "name": "Test Staff", "name_vi": "Gậy Thử",
        "slottype": "mainhand", "tier": "8", "branch": "TEST",
        "stats": {"itempower": 1200, "attackdamage": 70, "hitpointsmax": 300},
        "enchant": {},
        "spells": spells,
    }


ITEM = _mk_item()
LONG_ITEM = _mk_item()  # tổng desc đủ lớn (~8800) để ép budget


def test_length_within_budget():
    """len(out) <= budget với mọi budget."""
    for budget in (1200, 1500, 1800, 2000, 2200):
        out = format_item_full("T8_2H_TEST", LONG_ITEM, max_chars=budget)
        assert len(out) <= budget, f"budget {budget}: got {len(out)}"


def test_passive_header_and_names_always_present():
    """Khối Passive + tên cả 4 passive luôn xuất hiện, với mọi budget vừa đủ (>= floor)."""
    for budget in (1500, 2000, 2200):
        out = format_item_full("T8_2H_TEST", LONG_ITEM, max_chars=budget)
        assert "**Passive (4)**" in out, f"budget {budget}"
        for i in range(4):
            assert f"Thụ Động {i}" in out, f"passive {i} budget {budget}"


def test_active_names_always_present():
    """Tên mọi active luôn xuất hiện."""
    out = format_item_full("T8_2H_TEST", LONG_ITEM, max_chars=1500)
    for i in range(5):
        assert f"Kỹ Năng 1.{i}" in out
    for i in range(2):
        assert f"Kỹ Năng 2.{i}" in out
        assert f"Kỹ Năng 3.{i}" in out


def test_no_desc_line_over_max_desc():
    """Không dòng mô tả nào vượt max_desc + chút chênh do "…"."""
    for budget in (1500, 2000, 2200):
        out = format_item_full("T8_2H_TEST", LONG_ITEM, max_desc=500, max_chars=budget)
        for line in out.splitlines():
            li = line.strip()
            if li.startswith("*") and li.endswith("*"):
                assert len(li) <= 500 + 2, f"desc quá max_desc: len {len(li)}"


def test_no_unbalanced_markdown():
    """Mọi cặp ** / * trong dòng phải cân bằng (SỐ dấu * từng dòng luôn chẵn)."""
    for budget in (1200, 1500, 2000, 2200):
        out = format_item_full("T8_2H_TEST", LONG_ITEM, max_chars=budget)
        for line in out.splitlines():
            assert line.count("*") % 2 == 0, f"số dấu * lẻ (markdown hở): {line!r}"


def test_monotonic_length():
    """len(out) tăng theo budget (2000 >= 1800)."""
    o1800 = format_item_full("T8_2H_TEST", LONG_ITEM, max_chars=1800)
    o2000 = format_item_full("T8_2H_TEST", LONG_ITEM, max_chars=2000)
    assert len(o2000) >= len(o1800)


def test_short_item_not_truncated():
    """Item ngắn (desc < budget) ACQUIRE full, KHÔNG bị cắt (không "…"), len <= budget."""
    short = dict(LONG_ITEM)
    # giảm desc rất ngắn
    short["spells"] = {
        "active": [{"id": "A1", "slot": "1", "name_vi": "Kỹ Năng A",
                    "desc_vi": "Đòn ngắn gọn làm x."}],
        "passive": [{"id": "P1", "name_vi": "Thụ Động A",
                     "desc_vi": "Hiệu ứng nhỏ."}],
    }
    out = format_item_full("T8_2H_TEST", short, max_chars=2000)
    assert "…" not in out, "item ngắn bị cắt vô cớ"
    assert len(out) <= 2000


def test_default_max_chars_is_discord_limit():
    """Mặc định max_chars = 2000 (Discord)."""
    out = format_item_full("T8_2H_TEST", LONG_ITEM)
    assert len(out) <= DISCORD_MSG_LIMIT