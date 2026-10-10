import os
import asyncio
from copy import deepcopy

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.config import STORAGE_DIR
from core.permissions import is_officer
from core.storage import load_json_async, save_json_async

# ==============================================================================
# HỆ THỐNG MASSING
# ==============================================================================
MASSING_FILE = os.path.join(STORAGE_DIR, "tnc_massing_v1.json")
TEMPLATES_FILE = os.path.join(STORAGE_DIR, "tnc_templates_v1.json")

active_parties = {}
active_templates = {}
_massing_loaded = False
_templates_loaded = False
# Shared across party and template whole-blob transactions, including failed-save rollback.
_massing_state_lock = asyncio.Lock()
role_icons = {"Tank": "🛡️", "Heal": "💚", "Healer": "💚", "SP": "💜", "Support": "💜", "DPS": "⚔️"}

CTA_BUILD_GUIDES = {
    # Tank
    "great arcane": {
        "weapon": "Great Arcane",
        "armor": "Knight Armor",
        "hood": "Assassin hood",
        "shoes": "Royal shoes/Cleric sandals",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Avalonian Omelette",
        "potion": "Gigan"
    },
    "heavy mace": {
        "weapon": "Heavy Mace",
        "armor": "Guardian Armor",
        "hood": "Hellion hood",
        "shoes": "Royal shoes/Cleric sandals",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Avalonian Omelette",
        "potion": "Gigan"
    },
    "carving": {
        "weapon": "Carving",
        "armor": "Knight Armor",
        "hood": "Assassin hood",
        "shoes": "Royal shoes/Cleric sandals",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Sandwich",
        "potion": "Gigan"
    },
    "halbert": {
        "weapon": "Halbert",
        "armor": "Royal Armor",
        "hood": "Hellion hood",
        "shoes": "Royal shoes/Cleric sandals",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Sandwich",
        "potion": "Gigan"
    },
    # Support
    "locus": {
        "weapon": "Locus",
        "armor": "Judicator Armor",
        "hood": "Assassin hood",
        "shoes": "Royal shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Sandwich",
        "potion": "Gigan"
    },
    "rootbound": {
        "weapon": "Rootbound",
        "armor": "Judicator Armor",
        "hood": "Assassin hood",
        "shoes": "Royal shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Sandwich",
        "potion": "Gigan"
    },
    "lifecurse": {
        "weapon": "Lifecurse",
        "armor": "Demon",
        "hood": "Assassin hood",
        "shoes": "Guardian Boots",
        "offhand": "Taproot",
        "cape": "Smuggle",
        "food": "Beef Sandwich",
        "potion": "Gigan"
    },
    "evensong": {
        "weapon": "Evensong",
        "armor": "Judicator Armor",
        "hood": "Assassin hood",
        "shoes": "Royal shoes/Cleric sandals",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Sandwich",
        "potion": "Gigan"
    },
    # Healer
    "hallowfall": {
        "weapon": "Hallowfall",
        "armor": "Hellion Jacket",
        "hood": "Cleric cowl",
        "shoes": "Royal shoes",
        "offhand": "Shield",
        "cape": "Smuggle",
        "food": "Avalonian Omelette",
        "potion": "Gigan"
    },
    "fallen": {
        "weapon": "Fallen",
        "armor": "Hellion Jacket",
        "hood": "Cleric cowl",
        "shoes": "Royal shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Avalonian Omelette",
        "potion": "Gigan"
    },
    "blight": {
        "weapon": "Blight",
        "armor": "Assassin/Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Royal shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Avalonian Omelette",
        "potion": "Gigan"
    },
    "rampant": {
        "weapon": "Rampant",
        "armor": "Assassin/Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Royal shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Avalonian Omelette",
        "potion": "Gigan"
    },
    # DPS
    "lightcaller": {
        "weapon": "Lightcaller",
        "armor": "Judicator Armor",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "kingmaker": {
        "weapon": "Kingmaker",
        "armor": "Soldier Armor",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "galatine": {
        "weapon": "Galatine",
        "armor": "Soldier Armor",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "infinity blade": {
        "weapon": "Infinity Blade",
        "armor": "Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "inifinity blade": {
        "weapon": "Infinity Blade",
        "armor": "Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "realm/greataxe": {
        "weapon": "Realm/Greataxe",
        "armor": "Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "greataxe": {
        "weapon": "Realm/Greataxe",
        "armor": "Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "realm": {
        "weapon": "Realm/Greataxe",
        "armor": "Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "spike gauntlet/ursine/bracer": {
        "weapon": "Spike Gauntlet/Ursine/Bracer",
        "armor": "Hellion jacket/Cultist robe",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "spike gualet/ursine/bracer": {
        "weapon": "Spike Gauntlet/Ursine/Bracer",
        "armor": "Hellion jacket/Cultist robe",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    },
    "bearpaws": {
        "weapon": "Bearpaws",
        "armor": "Hellion jacket",
        "hood": "Cleric cowl",
        "shoes": "Valor Boots/Stalker shoes",
        "offhand": None,
        "cape": "Smuggle",
        "food": "Beef Stew",
        "potion": "Gigan"
    }
}

CTA_DEFAULT_ROLES_TEXT = (
    "Tank:Great Arcane:1,Heavy Mace:1,Carving:1,Halbert:1\n"
    "Support:Locus:1,Rootbound:1,Lifecurse:1,Evensong:1\n"
    "Healer:Hallowfall:1,Fallen:1,Blight:1,Rampant:1\n"
    "DPS:Lightcaller:1,Kingmaker:1,Galatine:1,Infinity Blade:1,Realm/Greataxe:1,Spike Gauntlet/Ursine/Bracer:1,Bearpaws:1"
)
CTA_DEFAULT_NOTE = "Đội hình CTA ZvZ chuẩn TNC. Pick role và bấm 'Xem Build' để kiểm tra set đồ chuẩn!"


def get_build_guide(role: str, weapon: str):
    if not weapon:
        return None
    w_key = weapon.strip().lower()
    if w_key in CTA_BUILD_GUIDES:
        return CTA_BUILD_GUIDES[w_key]
    for key, guide in CTA_BUILD_GUIDES.items():
        if key in w_key or w_key in key:
            return guide
    return None


def build_guide_embed(role: str, weapon: str, guide: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎒 Hướng Dẫn Build Đồ: {guide.get('weapon', weapon)}",
        description=f"⚔️ **Vai trò:** {role} | **Đội hình CTA ZvZ Guild TNC**",
        color=0x2ecc71
    )
    embed.add_field(name="⚔️ Vũ khí (Weapon)", value=f"**{guide.get('weapon', weapon)}**", inline=True)
    embed.add_field(name="🛡️ Áo (Armor)", value=guide.get("armor", "_Không rõ_"), inline=True)
    embed.add_field(name="🧢 Mũ (Hood)", value=guide.get("hood", "_Không rõ_"), inline=True)
    embed.add_field(name="👞 Giày (Shoes)", value=guide.get("shoes", "_Không rõ_"), inline=True)
    offhand = guide.get("offhand")
    if offhand and offhand not in ("x", "❌"):
        embed.add_field(name="🛡️ Off-Hand", value=offhand, inline=True)
    else:
        embed.add_field(name="🛡️ Off-Hand", value="❌ _(2 Tay / Không dùng)_", inline=True)
    embed.add_field(name="🧥 Cape", value=guide.get("cape", "Smuggle"), inline=True)
    embed.add_field(name="🍲 Thức ăn (Food)", value=guide.get("food", "_Không rõ_"), inline=True)
    embed.add_field(name="🧪 Thuốc (Potion)", value=guide.get("potion", "Gigan"), inline=True)
    embed.set_footer(text="⚔️ Guild TNC • Đội hình tác chiến CTA")
    return embed


async def load_massing():
    return await load_json_async(MASSING_FILE, dict)


# Mutating callers hold the shared lock through persistence and rollback.
async def save_massing(previous_state=None):
    if not _massing_loaded:
        raise RuntimeError("Massing chưa được tải thành công; không thể ghi đè dữ liệu.")
    try:
        await save_json_async(active_parties, MASSING_FILE)
    except Exception:
        if previous_state is not None:
            active_parties.clear()
            active_parties.update(previous_state)
        raise


async def load_templates():
    return await load_json_async(TEMPLATES_FILE, dict)


# Mutating callers hold the shared lock through persistence and cache publication.
async def save_templates(data):
    if not _templates_loaded:
        raise RuntimeError("Template chưa được tải thành công; không thể ghi đè dữ liệu.")
    await save_json_async(data, TEMPLATES_FILE)
    active_templates.clear()
    active_templates.update(deepcopy(data))


def validate_party_layout(party_id, roles, weapon_slots):
    slot_count = sum(len(weapon_slots.get(role, [])) for role in roles)
    if slot_count + 10 > 25:
        return "❌ Party vượt giới hạn 25 nút Discord. Hãy gộp hoặc giảm bớt các nhóm slot."
    for role in roles:
        for weapon, limit in weapon_slots.get(role, []):
            label = role if weapon == role and len(weapon_slots[role]) == 1 else f"{role}-{weapon}"
            if (
                len(f"{label} {limit}/{limit}") > 80
                or len(f"join_{party_id}_{role}_{weapon}") > 100
                or len(f"{role}|{weapon}") > 100
            ):
                return "❌ Tên role/weapon hoặc giới hạn slot quá dài cho Discord. Hãy rút gọn."
    return None


async def _save_party_after_ack(interaction, view, mutate):
    await interaction.response.defer()
    async with _massing_state_lock:
        party = active_parties.get(view.party_id)
        if not party:
            return False, "❌ Party hết hạn do bot restart."
        previous_state = deepcopy(active_parties)
        try:
            error = mutate(party)
        except Exception as error:
            active_parties.clear()
            active_parties.update(previous_state)
            view.rebuild_buttons()
            return False, f"❌ Không thể lưu party: `{error}`"
        if error:
            view.rebuild_buttons()
            return False, error
        try:
            await save_massing(previous_state)
        except Exception as error:
            active_parties.clear()
            active_parties.update(previous_state)
            view.rebuild_buttons()
            return False, f"❌ Không thể lưu party: `{error}`"
        view.rebuild_buttons()
        return True, None
def parse_role_block(raw_text):
    roles = []
    weapon_slots = {}
    for raw_line in raw_text.strip().split('\n'):
        raw_line = raw_line.strip()
        if not raw_line or ':' not in raw_line:
            continue
        segments = [s.strip() for s in raw_line.split(':')]
        role_name = segments[0]
        if not role_name:
            continue
        rest = segments[1:]
        if len(rest) == 1 and rest[0].isdigit():
            limit = int(rest[0])
            if limit > 0:
                roles.append(role_name)
                weapon_slots[role_name] = [(role_name, limit)]
            continue
        weapon_part = ":".join(rest)
        if not weapon_part:
            continue
        wlist = []
        for chunk in weapon_part.split(','):
            chunk = chunk.strip()
            if ':' not in chunk:
                continue
            wname, _, wlimit = chunk.rpartition(':')
            wname = wname.strip()
            if wname and wlimit.strip().isdigit() and int(wlimit.strip()) > 0:
                wlist.append((wname, int(wlimit.strip())))
        if wlist:
            roles.append(role_name)
            weapon_slots[role_name] = wlist
    return roles, weapon_slots


def format_role_block(roles, weapon_slots):
    """Dựng lại text block role:weapon:limit từ dữ liệu roles/weapon_slots (dùng để pre-fill modal khi Copy/Template)."""
    lines = []
    for role in roles:
        wlist = weapon_slots.get(role, [])
        if not wlist:
            continue
        if len(wlist) == 1 and wlist[0][0] == role:
            lines.append(f"{role}:{wlist[0][1]}")
        else:
            parts = ",".join(f"{w}:{l}" for w, l in wlist)
            lines.append(f"{role}:{parts}")
    return "\n".join(lines)


def build_party_embed(party):
    total_filled = sum(len(members) for wmap in party["slots"].values() for members in wmap.values())
    total_slots = sum(limit for wlist in party["weapon_slots"].values() for _, limit in wlist)
    is_full = total_slots > 0 and total_filled >= total_slots

    embed = discord.Embed(title=party["name"], color=0xe74c3c)
    embed.add_field(name="🕐 Time", value=party["time"] or "_Chưa rõ_", inline=False)
    embed.add_field(name="​", value="─────────────────", inline=False)

    for role in party["roles"]:
        icon = role_icons.get(role, "🔹")
        wlist = party["weapon_slots"][role]
        lines = []
        for weapon, limit in wlist:
            members = party["slots"][role].get(weapon, [])
            member_str = "\n".join(f"<@{uid}>" for uid in members) if members else "_Chưa có ai_"
            if len(wlist) == 1 and wlist[0][0] == role:
                lines.append(f"**{role}** {len(members)}/{limit}\n{member_str}")
            else:
                lines.append(f"**{weapon}** {len(members)}/{limit}\n{member_str}")
        embed.add_field(name=f"{icon} {role}", value="\n\n".join(lines) if lines else "_Trống_", inline=True)

    if total_slots > 0:
        status = "🟢 **FULL**" if is_full else f"🟡 **{total_filled}/{total_slots}**"
        embed.add_field(name="​", value=f"─────────────────\n👥 {status}", inline=False)

    fills = party.get("fills", [])
    if fills:
        embed.add_field(name=f"🔄 Fill ({len(fills)} người)", value="\n".join(f"• <@{uid}>" for uid in fills), inline=False)
    elif is_full:
        embed.add_field(name="🔄 Fill", value="_Party đã full — bấm nút Fill để vào danh sách dự bị!_", inline=False)

    if party.get("note"):
        embed.add_field(name="📝 Ghi chú", value=party["note"], inline=False)

    creator_name = party.get("creator_name") or (f"<@{party['creator']}>" if party.get("creator") else None)
    if creator_name:
        embed.set_footer(text=f"Created by {creator_name}")

    return embed


def can_manage(party, member):
    return member.id == party["creator"] or is_officer(member)


class SlotPickSelect(discord.ui.Select):
    def __init__(self, party, parent_view, target_uid, mode):
        self.party_id = party["id"]
        self.target_uid = target_uid
        self.mode = mode
        self.parent_view = parent_view
        options = []
        for role in party["roles"]:
            for weapon, limit in party["weapon_slots"][role]:
                members = party["slots"][role].get(weapon, [])
                if len(members) >= limit:
                    continue
                display = role if (len(party["weapon_slots"][role]) == 1 and party["weapon_slots"][role][0][0] == role) else f"{role} - {weapon}"
                options.append(discord.SelectOption(label=f"{display} ({len(members)}/{limit})", value=f"{role}|{weapon}"))
        if not options:
            options.append(discord.SelectOption(label="Không còn slot trống", value="none"))
        super().__init__(placeholder="Chọn slot...", options=options[:25], min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ Không còn slot trống nào!", ephemeral=True)
        role, weapon = self.values[0].split("|", 1)

        def mutate(party):
            if role not in party["weapon_slots"] or weapon not in dict(party["weapon_slots"][role]):
                return "❌ Slot không còn tồn tại trong party."
            current = party["slots"][role].get(weapon, [])
            already_in_target = self.target_uid in current
            if self.mode == "move":
                in_party = any(
                    self.target_uid in members
                    for role_slots in party["slots"].values()
                    for members in role_slots.values()
                ) or self.target_uid in party.get("fills", [])
                if not in_party:
                    return "❌ Thành viên không còn trong party."
            elif any(
                self.target_uid in members
                for role_slots in party["slots"].values()
                for members in role_slots.values()
            ) or self.target_uid in party.get("fills", []):
                return "⚠️ Thành viên đã có trong party."
            limit = dict(party["weapon_slots"][role])[weapon]
            if len(current) - int(already_in_target) >= limit:
                return "❌ Slot vừa đầy, thử lại!"
            if self.mode == "move":
                self.parent_view._remove_member_everywhere(party, self.target_uid)
            current = party["slots"][role].setdefault(weapon, [])
            if not already_in_target or self.mode == "move":
                current.append(self.target_uid)
            return None

        success, error = await _save_party_after_ack(interaction, self.parent_view, mutate)
        if not success:
            await interaction.edit_original_response(content=error, embed=None, view=None)
            restored = active_parties.get(self.party_id)
            if restored:
                await self.parent_view.refresh_original(interaction, restored)
            return
        await interaction.edit_original_response(
            content=f"✅ Đã {'thêm' if self.mode=='add' else 'chuyển'} <@{self.target_uid}> vào **{role}-{weapon}**.",
            embed=None, view=None
        )
        await self.parent_view.refresh_original(interaction, active_parties[self.party_id])


class SlotPickView(discord.ui.View):
    def __init__(self, party, parent_view, target_uid, mode):
        super().__init__(timeout=86400)
        self.add_item(SlotPickSelect(party, parent_view, target_uid, mode))


class MemberPickSelect(discord.ui.Select):
    def __init__(self, party, parent_view, mode, guild):
        self.party_id = party["id"]
        self.mode = mode
        self.parent_view = parent_view
        member_ids = set()
        for role in party["roles"]:
            for weapon in party["slots"][role]:
                member_ids.update(party["slots"][role][weapon])
        member_ids.update(party.get("fills", []))
        options = []
        for uid in member_ids:
            member = guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            options.append(discord.SelectOption(label=name, value=str(uid)))
        if not options:
            options.append(discord.SelectOption(label="Chưa có ai trong party", value="none"))
        super().__init__(placeholder="Chọn thành viên...", options=options[:25], min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ Party chưa có ai để chọn!", ephemeral=True)
        target_uid = int(self.values[0])
        if self.mode == "kick":
            def mutate(party):
                present = any(
                    target_uid in members
                    for role_slots in party["slots"].values()
                    for members in role_slots.values()
                ) or target_uid in party.get("fills", [])
                if not present:
                    return "❌ Thành viên không còn trong party."
                self.parent_view._remove_member_everywhere(party, target_uid)
                return None

            success, error = await _save_party_after_ack(interaction, self.parent_view, mutate)
            if not success:
                await interaction.edit_original_response(content=error, view=None)
                restored = active_parties.get(self.party_id)
                if restored:
                    await self.parent_view.refresh_original(interaction, restored)
                return
            await interaction.edit_original_response(content=f"✅ Đã kick <@{target_uid}> khỏi party.", view=None)
            await self.parent_view.refresh_original(interaction, active_parties[self.party_id])
        else:
            await interaction.response.edit_message(
                content=f"👉 Chọn slot mới muốn chuyển <@{target_uid}> vào:",
                view=SlotPickView(party, self.parent_view, target_uid, "move")
            )


class MemberPickView(discord.ui.View):
    def __init__(self, party, parent_view, mode, guild):
        super().__init__(timeout=86400)
        self.add_item(MemberPickSelect(party, parent_view, mode, guild))


class AddMemberSelect(discord.ui.UserSelect):
    def __init__(self, party, parent_view):
        self.party_id = party["id"]
        self.parent_view = parent_view
        super().__init__(placeholder="Tìm và chọn thành viên cần thêm...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        target = self.values[0]
        target_uid = target.id
        in_party_ids = set()
        for role in party["roles"]:
            for weapon in party["slots"][role]:
                in_party_ids.update(party["slots"][role][weapon])
        in_party_ids.update(party.get("fills", []))
        if target_uid in in_party_ids:
            return await interaction.response.send_message(
                f"⚠️ **{target.display_name}** đã có trong party rồi!", ephemeral=True
            )
        await interaction.response.edit_message(
            content=f"👉 Chọn slot muốn thêm **{target.display_name}** vào:",
            view=SlotPickView(party, self.parent_view, target_uid, "add")
        )


class AddMemberView(discord.ui.View):
    def __init__(self, party, parent_view, guild=None):
        super().__init__(timeout=86400)
        self.add_item(AddMemberSelect(party, parent_view))


class PartySlotSelect(discord.ui.Select):
    def __init__(self, party_id, party):
        self.party_id = party_id
        options = []
        for role in party["roles"]:
            icon = role_icons.get(role, "🔹")
            for weapon, limit in party["weapon_slots"].get(role, []):
                members = party["slots"][role].get(weapon, [])
                filled = len(members)
                is_full = filled >= limit
                display = role if (len(party["weapon_slots"][role]) == 1 and party["weapon_slots"][role][0][0] == role) else f"{role} - {weapon}"
                opt_label = f"{display} ({filled}/{limit})"
                if is_full:
                    opt_label += " [FULL]"
                options.append(
                    discord.SelectOption(
                        label=opt_label[:100],
                        value=f"{role}|{weapon}",
                        emoji=icon if icon and (icon.startswith("<") or len(icon) <= 2) else None,
                        description="Slot đã đầy" if is_full else "Bấm để nhận slot này"
                    )
                )
        if not options:
            options.append(discord.SelectOption(label="Không có slot nào", value="none"))
        super().__init__(
            placeholder="⚔️ Chọn Slot tham gia (Role & Vũ khí)...",
            options=options[:25],
            min_values=1,
            max_values=1,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ Party không có slot hợp lệ.", ephemeral=True)
        role, weapon = self.values[0].split("|", 1)
        uid = interaction.user.id

        def mutate(party):
            if role not in party["weapon_slots"] or weapon not in dict(party["weapon_slots"][role]):
                return "❌ Slot không còn tồn tại trong party."
            current = party["slots"][role].get(weapon, [])
            limit = dict(party["weapon_slots"][role])[weapon]
            if uid not in current and len(current) >= limit:
                return f"❌ Slot **{role} - {weapon}** vừa đầy!"
            self.view._remove_member_everywhere(party, uid)
            party["slots"][role].setdefault(weapon, []).append(uid)
            return None

        success, error = await _save_party_after_ack(interaction, self.view, mutate)
        if not success:
            await interaction.followup.send(error, ephemeral=True)
            return

        party = active_parties.get(self.party_id)
        if party:
            await interaction.edit_original_response(
                embed=build_party_embed(party), view=self.view
            )

        guide = get_build_guide(role, weapon)
        if guide:
            embed = build_guide_embed(role, weapon, guide)
            await interaction.followup.send(
                content=f"✅ Bạn đã đăng ký thành công slot **{role} - {weapon}**!",
                embed=embed,
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                content=f"✅ Bạn đã đăng ký thành công slot **{role} - {weapon}**!",
                ephemeral=True
            )


class PartyView(discord.ui.View):
    def __init__(self, party_id):
        super().__init__(timeout=None)
        self.party_id = party_id
        self.rebuild_buttons()

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        try:
            await interaction.response.send_message("❌ Party hết hạn do bot restart. Tạo party mới nhé!", ephemeral=True)
        except Exception as e:
            print(f"[Error] {e}")
            pass

    async def refresh_original(self, interaction, party):
        try:
            msg = await interaction.channel.fetch_message(int(self.party_id))
            await msg.edit(embed=build_party_embed(party), view=self)
        except Exception as e:
            print(f"⚠️ Không refresh được message gốc: {e}")

    def rebuild_buttons(self):
        self.clear_items()
        party = active_parties.get(self.party_id)
        if not party:
            return

        is_party_full = self._is_full(party)
        slot_count = sum(len(party["weapon_slots"].get(role, [])) for role in party["roles"])

        if slot_count > 12:
            # Dùng Dropdown Select Menu cho party nhiều slot (tránh chạm giới hạn 25 button)
            self.add_item(PartySlotSelect(self.party_id, party))
            row_idx = 1
        else:
            # Dùng Button truyền thống cho party <= 12 slot
            styles = [discord.ButtonStyle.blurple, discord.ButtonStyle.green, discord.ButtonStyle.gray, discord.ButtonStyle.primary]
            style_idx = 0
            for role in party["roles"]:
                wlist = party["weapon_slots"][role]
                is_single = len(wlist) == 1 and wlist[0][0] == role
                for weapon, limit in wlist:
                    members = party["slots"][role].get(weapon, [])
                    filled = len(members)
                    label = f"{role} {filled}/{limit}" if is_single else f"{role}-{weapon} {filled}/{limit}"
                    btn = discord.ui.Button(
                        label=label,
                        style=styles[style_idx % len(styles)],
                        custom_id=f"join_{self.party_id}_{role}_{weapon}",
                        disabled=filled >= limit
                    )
                    btn.callback = self.make_join_callback(role, weapon)
                    self.add_item(btn)
                style_idx += 1
            row_idx = None

        # Nút xem build trang bị
        build_btn = discord.ui.Button(
            label="🎒 Xem Build",
            style=discord.ButtonStyle.success,
            custom_id=f"build_{self.party_id}",
            row=row_idx
        )
        build_btn.callback = self.view_build_callback
        self.add_item(build_btn)

        if party["roles"]:
            fill_btn = discord.ui.Button(
                label=f"🔄 Fill ({len(party.get('fills', []))})",
                style=discord.ButtonStyle.secondary,
                custom_id=f"fill_{self.party_id}",
                disabled=not is_party_full,
                row=row_idx
            )
            fill_btn.callback = self.fill_callback
            self.add_item(fill_btn)

        leave_btn = discord.ui.Button(
            label="❌ Leave",
            style=discord.ButtonStyle.red,
            custom_id=f"leave_{self.party_id}",
            row=row_idx
        )
        leave_btn.callback = self.leave_callback
        self.add_item(leave_btn)

        admin_row = 2 if slot_count > 12 else None
        add_btn = discord.ui.Button(label="➕ Add", style=discord.ButtonStyle.success, custom_id=f"add_{self.party_id}", row=admin_row)
        add_btn.callback = self.add_callback
        self.add_item(add_btn)

        move_btn = discord.ui.Button(label="🔀 Move", style=discord.ButtonStyle.primary, custom_id=f"move_{self.party_id}", row=admin_row)
        move_btn.callback = self.move_callback
        self.add_item(move_btn)

        kick_btn = discord.ui.Button(label="👋 Kick", style=discord.ButtonStyle.danger, custom_id=f"kick_{self.party_id}", row=admin_row)
        kick_btn.callback = self.kick_callback
        self.add_item(kick_btn)

        note_btn = discord.ui.Button(label="📝 Note", style=discord.ButtonStyle.secondary, custom_id=f"note_{self.party_id}", row=admin_row)
        note_btn.callback = self.note_callback
        self.add_item(note_btn)

        ping_btn = discord.ui.Button(label="📢 Ping All", style=discord.ButtonStyle.secondary, custom_id=f"ping_{self.party_id}", row=admin_row)
        ping_btn.callback = self.ping_callback
        self.add_item(ping_btn)

        extra_row = 3 if slot_count > 12 else None
        copy_btn = discord.ui.Button(label="📋 Copy", style=discord.ButtonStyle.secondary, custom_id=f"copy_{self.party_id}", row=extra_row)
        copy_btn.callback = self.copy_callback
        self.add_item(copy_btn)

        savetpl_btn = discord.ui.Button(label="💾 Save Template", style=discord.ButtonStyle.secondary, custom_id=f"savetpl_{self.party_id}", row=extra_row)
        savetpl_btn.callback = self.save_template_callback
        self.add_item(savetpl_btn)

        del_btn = discord.ui.Button(label="🗑️ Delete", style=discord.ButtonStyle.danger, custom_id=f"delete_{self.party_id}", row=extra_row)
        del_btn.callback = self.delete_callback
        self.add_item(del_btn)

    def _is_full(self, party):
        total_filled = sum(len(m) for wmap in party["slots"].values() for m in wmap.values())
        total_slots = sum(limit for wlist in party["weapon_slots"].values() for _, limit in wlist)
        return total_slots > 0 and total_filled >= total_slots

    def _remove_member_everywhere(self, party, uid):
        removed = False
        for role in party["roles"]:
            for weapon in list(party["slots"][role].keys()):
                if uid in party["slots"][role][weapon]:
                    party["slots"][role][weapon].remove(uid)
                    removed = True
        if uid in party.get("fills", []):
            party["fills"].remove(uid)
            removed = True
        return removed

    def make_join_callback(self, role, weapon):
        async def callback(interaction: discord.Interaction):
            uid = interaction.user.id

            def mutate(party):
                if role not in party["weapon_slots"] or weapon not in dict(party["weapon_slots"][role]):
                    return "❌ Slot không còn tồn tại trong party."
                current = party["slots"][role].get(weapon, [])
                limit = dict(party["weapon_slots"][role])[weapon]
                if uid not in current and len(current) >= limit:
                    return f"❌ Slot **{role}-{weapon}** vừa đầy!"
                self._remove_member_everywhere(party, uid)
                party["slots"][role].setdefault(weapon, []).append(uid)
                return None

            success, error = await _save_party_after_ack(interaction, self, mutate)
            if not success:
                await interaction.followup.send(error, ephemeral=True)
                return
            await interaction.edit_original_response(
                embed=build_party_embed(active_parties[self.party_id]), view=self
            )
            if hasattr(interaction, "followup") and hasattr(interaction.followup, "send"):
                guide = get_build_guide(role, weapon)
                embed = build_guide_embed(role, weapon, guide) if guide else None
                try:
                    res = interaction.followup.send(
                        content=f"✅ Bạn đã đăng ký thành công slot **{role} - {weapon}**!",
                        embed=embed,
                        ephemeral=True
                    )
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
        return callback

    async def view_build_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        uid = interaction.user.id
        user_slot = None
        for role in party["roles"]:
            for weapon, members in party["slots"][role].items():
                if uid in members:
                    user_slot = (role, weapon)
                    break
            if user_slot:
                break

        if not user_slot:
            return await interaction.response.send_message(
                "⚠️ Bạn chưa nhận slot nào trong party này! Hãy chọn slot trước để xem hướng dẫn build tương ứng.",
                ephemeral=True
            )

        role, weapon = user_slot
        guide = get_build_guide(role, weapon)
        if guide:
            embed = build_guide_embed(role, weapon, guide)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"ℹ️ Slot **{role} - {weapon}** hiện chưa có hướng dẫn build mẫu.",
                ephemeral=True
            )

    async def fill_callback(self, interaction: discord.Interaction):
        uid = interaction.user.id

        def mutate(party):
            if not self._is_full(party):
                return "⚠️ Party chưa full!"
            if any(
                uid in members
                for role in party["roles"]
                for members in party["slots"][role].values()
            ):
                return "⚠️ Bạn đã có slot chính thức rồi!"
            if uid in party.get("fills", []):
                return "⚠️ Bạn đã trong danh sách Fill rồi!"
            party.setdefault("fills", []).append(uid)
            return None

        success, error = await _save_party_after_ack(interaction, self, mutate)
        if not success:
            await interaction.followup.send(error, ephemeral=True)
            return
        await interaction.edit_original_response(
            embed=build_party_embed(active_parties[self.party_id]), view=self
        )

    async def leave_callback(self, interaction: discord.Interaction):
        uid = interaction.user.id

        def mutate(party):
            if not any(
                uid in members
                for role in party["roles"]
                for members in party["slots"][role].values()
            ) and uid not in party.get("fills", []):
                return "⚠️ Bạn chưa đăng ký party này."
            self._remove_member_everywhere(party, uid)
            return None

        success, error = await _save_party_after_ack(interaction, self, mutate)
        if not success:
            await interaction.followup.send(error, ephemeral=True)
            return
        await interaction.edit_original_response(
            embed=build_party_embed(active_parties[self.party_id]), view=self
        )

    async def add_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not can_manage(party, interaction.user):
            return await interaction.response.send_message("❌ Chỉ người tạo party hoặc Officer mới dùng được!", ephemeral=True)
        if not party["roles"]:
            return await interaction.response.send_message("❌ Party này không có role nào!", ephemeral=True)
        await interaction.response.send_message("👉 Chọn thành viên cần thêm:", view=AddMemberView(party, self, interaction.guild), ephemeral=True)

    async def move_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not can_manage(party, interaction.user):
            return await interaction.response.send_message("❌ Chỉ người tạo party hoặc Officer mới dùng được!", ephemeral=True)
        await interaction.response.send_message("👉 Chọn thành viên muốn chuyển slot:", view=MemberPickView(party, self, "move", interaction.guild), ephemeral=True)

    async def kick_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not can_manage(party, interaction.user):
            return await interaction.response.send_message("❌ Chỉ người tạo party hoặc Officer mới dùng được!", ephemeral=True)
        await interaction.response.send_message("👉 Chọn thành viên muốn kick:", view=MemberPickView(party, self, "kick", interaction.guild), ephemeral=True)

    async def note_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not can_manage(party, interaction.user):
            return await interaction.response.send_message("❌ Chỉ người tạo party hoặc Officer mới sửa được!", ephemeral=True)
        await interaction.response.send_modal(NoteModal(self.party_id, self))

    async def delete_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not can_manage(party, interaction.user):
            return await interaction.response.send_message("❌ Chỉ người tạo hoặc Officer mới xóa được!", ephemeral=True)

        def mutate(party):
            if not can_manage(party, interaction.user):
                return "❌ Chỉ người tạo hoặc Officer mới xóa được!"
            del active_parties[self.party_id]
            return None

        success, error = await _save_party_after_ack(interaction, self, mutate)
        if not success:
            restored = active_parties.get(self.party_id)
            await interaction.edit_original_response(
                content=error,
                embed=build_party_embed(restored) if restored else None,
                view=self if restored else None,
            )
            return
        await interaction.edit_original_response(content="🗑️ **Party đã bị xóa.**", embed=None, view=None)

    async def copy_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        roles_text = format_role_block(party["roles"], party["weapon_slots"])
        modal = MassingModal(
            prefill_roles=roles_text,
            prefill_note=party.get("note", "")
        )
        await interaction.response.send_modal(modal)

    async def save_template_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not can_manage(party, interaction.user):
            return await interaction.response.send_message("❌ Chỉ người tạo party hoặc Officer mới dùng được!", ephemeral=True)
        if not party["roles"]:
            return await interaction.response.send_message("❌ Party này không có role nào để lưu template!", ephemeral=True)
        await interaction.response.send_modal(SaveTemplateModal(party))

    async def ping_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not can_manage(party, interaction.user):
            return await interaction.response.send_message("❌ Chỉ người tạo party hoặc Officer mới dùng được!", ephemeral=True)
        member_ids = set()
        for role in party["roles"]:
            for weapon in party["slots"][role]:
                member_ids.update(party["slots"][role][weapon])
        member_ids.update(party.get("fills", []))
        if not member_ids:
            return await interaction.response.send_message("⚠️ Party chưa có ai để ping!", ephemeral=True)
        await interaction.response.send_modal(PingAllModal(list(member_ids)))


class MassingModal(discord.ui.Modal, title="⚔️ Tạo Massing"):
    party_name = discord.ui.TextInput(label="Tên Party", placeholder="Ví dụ: PVP: SMC, Bom Squad, RZ Brawl Clap...", max_length=80)
    party_time = discord.ui.TextInput(label="Thời gian (có thể để trống)", placeholder="Ví dụ: 5/6 20:00", required=False, max_length=30)
    party_roles = discord.ui.TextInput(
        label="Role (mỗi role 1 dòng, có thể để trống)",
        placeholder="DPS:Realm:2,Iron:1\nHeal:Hallow:1,Redemption:1\nTank:2\nSP:1",
        style=discord.TextStyle.paragraph, required=False, max_length=500
    )
    party_note = discord.ui.TextInput(
        label="Ghi chú (có thể để trống)",
        placeholder="Ví dụ: Fill pt1 trước, all heal mặc giáp da...",
        style=discord.TextStyle.paragraph, required=False, max_length=300
    )

    def __init__(self, prefill_roles=None, prefill_note=None, prefill_name=None, prefill_time=None):
        super().__init__()
        if prefill_name:
            self.party_name.default = prefill_name
        if prefill_time:
            self.party_time.default = prefill_time
        if prefill_roles:
            self.party_roles.default = prefill_roles
        if prefill_note:
            self.party_note.default = prefill_note

    async def on_submit(self, interaction: discord.Interaction):
        if not _massing_loaded:
            return await interaction.response.send_message(
                "❌ Kho Massing chưa tải được; không thể tạo party an toàn.", ephemeral=True
            )
        time_str = self.party_time.value.strip() if self.party_time.value else ""
        note = self.party_note.value.strip() if self.party_note.value else ""
        roles, weapon_slots = parse_role_block(self.party_roles.value or "")
        party_id = str(interaction.id)
        layout_error = validate_party_layout(party_id, roles, weapon_slots)
        if layout_error:
            return await interaction.response.send_message(layout_error, ephemeral=True)
        party_data = {
            "id": party_id,
            "name": self.party_name.value.strip(),
            "time": time_str,
            "roles": roles, "weapon_slots": weapon_slots,
            "slots": {r: {} for r in roles},
            "fills": [], "note": note,
            "creator": interaction.user.id,
            "creator_name": interaction.user.display_name
        }
        await interaction.response.defer()
        async with _massing_state_lock:
            previous_state = deepcopy(active_parties)
            active_parties[party_id] = party_data
            view = PartyView(party_id)
            try:
                msg = await interaction.followup.send(
                    embed=build_party_embed(party_data), view=view, wait=True
                )
            except Exception as error:
                active_parties.clear()
                active_parties.update(previous_state)
                await interaction.followup.send(f"❌ Không thể gửi party: `{error}`", ephemeral=True)
                return
            active_parties[str(msg.id)] = active_parties.pop(party_id)
            active_parties[str(msg.id)]["id"] = str(msg.id)
            view.party_id = str(msg.id)
            view.rebuild_buttons()
            try:
                await save_massing(previous_state)
            except Exception as error:
                await msg.edit(content=f"❌ Không thể lưu party: `{error}`", embed=None, view=None)
                return
            await msg.edit(embed=build_party_embed(active_parties[str(msg.id)]), view=view)


class NoteModal(discord.ui.Modal, title="📝 Sửa Ghi chú"):
    note_text = discord.ui.TextInput(
        label="Ghi chú", placeholder="Ví dụ: Fill pt1 trước, all heal mặc giáp da...",
        style=discord.TextStyle.paragraph, required=False, max_length=300
    )

    def __init__(self, party_id, parent_view):
        super().__init__()
        self.party_id = party_id
        self.parent_view = parent_view
        party = active_parties.get(party_id)
        if party and party.get("note"):
            self.note_text.default = party["note"]

    async def on_submit(self, interaction: discord.Interaction):
        def mutate(party):
            party["note"] = self.note_text.value.strip() if self.note_text.value else ""
            return None

        success, error = await _save_party_after_ack(interaction, self.parent_view, mutate)
        if not success:
            restored = active_parties.get(self.party_id)
            await interaction.edit_original_response(
                embed=build_party_embed(restored) if restored else None,
                view=self.parent_view if restored else None,
            )
            await interaction.followup.send(f"❌ Không thể lưu ghi chú: `{error}`", ephemeral=True)
            return
        await interaction.edit_original_response(
            embed=build_party_embed(active_parties[self.party_id]), view=self.parent_view
        )


class ConfirmOverwriteTemplateView(discord.ui.View):
    def __init__(self, name, key, party):
        super().__init__(timeout=30)
        self.name = name
        self.key = key
        self.party = party

    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _templates_loaded:
            return await interaction.response.send_message("❌ Kho template chưa tải được.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        async with _massing_state_lock:
            templates = deepcopy(active_templates)
            templates[self.key] = {
                "display_name": self.name,
                "roles": self.party["roles"],
                "weapon_slots": self.party["weapon_slots"],
                "note": self.party.get("note", "")
            }
            try:
                await save_templates(templates)
            except Exception as error:
                return await interaction.followup.send(f"❌ Không thể lưu template: `{error}`", ephemeral=True)
            await interaction.edit_original_response(
                content=f"✅ Đã ghi đè template **{self.name}**!", view=None
            )

    @discord.ui.button(label="❌ Hủy", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🚫 Đã hủy, không ghi đè template.", view=None)


class SaveTemplateModal(discord.ui.Modal, title="💾 Lưu Template"):
    template_name = discord.ui.TextInput(
        label="Tên Template", placeholder="Ví dụ: PVP Standard, ZvZ 20...", max_length=50
    )

    def __init__(self, party):
        super().__init__()
        self.party = deepcopy(party)

    async def on_submit(self, interaction: discord.Interaction):
        if not _templates_loaded:
            return await interaction.response.send_message("❌ Kho template chưa tải được.", ephemeral=True)
        name = self.template_name.value.strip()
        key = name.lower()
        await interaction.response.defer(ephemeral=True)
        async with _massing_state_lock:
            if key in active_templates:
                view = ConfirmOverwriteTemplateView(name, key, self.party)
                return await interaction.followup.send(
                    f"⚠️ Template **{name}** đã tồn tại. Bạn có muốn ghi đè không?",
                    view=view,
                    ephemeral=True,
                )
            templates = deepcopy(active_templates)
            templates[key] = {
                "display_name": name,
                "roles": self.party["roles"],
                "weapon_slots": self.party["weapon_slots"],
                "note": self.party.get("note", "")
            }
            try:
                await save_templates(templates)
            except Exception as error:
                return await interaction.followup.send(f"❌ Không thể lưu template: `{error}`", ephemeral=True)
            await interaction.edit_original_response(content=f"✅ Đã lưu template **{name}**.")


class PingAllModal(discord.ui.Modal, title="📢 Ping All Party"):
    ping_message = discord.ui.TextInput(
        label="Nội dung nhắn",
        placeholder="Ví dụ: Chuẩn bị mass, tập hợp nhanh!",
        style=discord.TextStyle.paragraph, required=True, max_length=300
    )

    def __init__(self, member_ids):
        super().__init__()
        self.member_ids = member_ids

    async def on_submit(self, interaction: discord.Interaction):
        mentions = " ".join(f"<@{uid}>" for uid in self.member_ids)
        content = f"📢 {self.ping_message.value.strip()}\n{mentions}"
        await interaction.response.send_message(content)


class MassingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Khôi phục party/template state trước khi các event dùng tới."""
        global _massing_loaded, _templates_loaded
        _massing_loaded = False
        _templates_loaded = False
        try:
            loaded_parties = await load_massing()
            if not isinstance(loaded_parties, dict):
                raise ValueError("Dữ liệu Massing không phải object.")
            active_parties.clear()
            active_parties.update(loaded_parties)
            _massing_loaded = True
        except Exception as error:
            print(f"❌ Không tải được Massing; thao tác ghi bị khóa: {error}")
        try:
            loaded_templates = await load_templates()
            if not isinstance(loaded_templates, dict):
                raise ValueError("Dữ liệu template không phải object.")
            active_templates.clear()
            active_templates.update(loaded_templates)
            if "cta tnc" not in active_templates:
                cta_roles, cta_wslots = parse_role_block(CTA_DEFAULT_ROLES_TEXT)
                active_templates["cta tnc"] = {
                    "display_name": "CTA TNC (Comp 19 Slot)",
                    "roles": cta_roles,
                    "weapon_slots": cta_wslots,
                    "note": CTA_DEFAULT_NOTE
                }
            _templates_loaded = True
        except Exception as error:
            print(f"❌ Không tải được template; thao tác ghi bị khóa: {error}")

        restored = 0
        if _massing_loaded:
            for pid in active_parties:
                try:
                    self.bot.add_view(PartyView(pid))
                    restored += 1
                except Exception as error:
                    print(f"⚠️ Không khôi phục được party {pid}: {error}")
        print(f"🔄 Đã khôi phục {restored} party Massing sau restart!")
        if not self.weekly_clear_parties.is_running():
            self.weekly_clear_parties.start()

    async def cog_unload(self):
        self.weekly_clear_parties.cancel()

    @tasks.loop(hours=168)  # 7 ngày = 168 giờ
    async def weekly_clear_parties(self):
        """Tự động xóa toàn bộ party Massing đang active mỗi 7 ngày."""
        async with _massing_state_lock:
            if not _massing_loaded:
                return
            previous_state = deepcopy(active_parties)
            count = len(active_parties)
            active_parties.clear()
            try:
                await save_massing(previous_state)
            except Exception as error:
                print(f"❌ Không thể lưu dọn dẹp Massing; giữ nguyên party: {error}")
                return
            print(f"🧹 [Auto-Clean] Đã xóa {count} party Massing cũ sau 7 ngày.")

    @weekly_clear_parties.before_loop
    async def before_weekly_clear(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(168 * 60 * 60)

    async def template_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        for key, template in active_templates.items():
            name = template.get("display_name", key)
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        return choices[:25]

    @app_commands.command(name="massing_cta", description="Tạo ngay party CTA 19 slot kèm guide build trang bị cho Guild TNC")
    @app_commands.describe(
        time="Thời gian diễn ra CTA (Ví dụ: 20:00, 5/6 19:30)",
        note="Ghi chú thêm cho anh em (không bắt buộc)"
    )
    async def massing_cta_slash(self, interaction: discord.Interaction, time: str = "", note: str = ""):
        if not _massing_loaded:
            return await interaction.response.send_message(
                "❌ Kho Massing chưa tải được; không thể tạo party an toàn.", ephemeral=True
            )
        time_str = time.strip()
        default_note = note.strip() if note else CTA_DEFAULT_NOTE
        roles, weapon_slots = parse_role_block(CTA_DEFAULT_ROLES_TEXT)
        party_id = str(interaction.id)

        party_data = {
            "id": party_id,
            "name": "⚔️ CTA ZvZ TNC",
            "time": time_str,
            "roles": roles,
            "weapon_slots": weapon_slots,
            "slots": {r: {} for r in roles},
            "fills": [],
            "note": default_note,
            "creator": interaction.user.id,
            "creator_name": interaction.user.display_name
        }

        await interaction.response.defer()
        async with _massing_state_lock:
            previous_state = deepcopy(active_parties)
            active_parties[party_id] = party_data
            view = PartyView(party_id)
            try:
                msg = await interaction.followup.send(
                    embed=build_party_embed(party_data), view=view, wait=True
                )
            except Exception as error:
                active_parties.clear()
                active_parties.update(previous_state)
                await interaction.followup.send(f"❌ Không thể gửi party CTA: `{error}`", ephemeral=True)
                return
            active_parties[str(msg.id)] = active_parties.pop(party_id)
            active_parties[str(msg.id)]["id"] = str(msg.id)
            view.party_id = str(msg.id)
            view.rebuild_buttons()
            try:
                await save_massing(previous_state)
            except Exception as error:
                await msg.edit(content=f"❌ Không thể lưu party: `{error}`", embed=None, view=None)
                return
            await msg.edit(embed=build_party_embed(active_parties[str(msg.id)]), view=view)

    @app_commands.command(name="massing", description="Tạo party Massing (PVP/PVE/...) cho Guild TNC")
    @app_commands.describe(template="Dùng template đã lưu (không bắt buộc, để trống nếu tạo mới hoàn toàn)")
    @app_commands.autocomplete(template=template_autocomplete)
    async def massing_slash(self, interaction: discord.Interaction, template: str = None):
        if not _massing_loaded:
            return await interaction.response.send_message(
                "❌ Kho Massing chưa tải được; không thể tạo party an toàn.", ephemeral=True
            )
        if template and not _templates_loaded:
            return await interaction.response.send_message("❌ Kho template chưa tải được.", ephemeral=True)
        if template:
            selected = active_templates.get(template.lower())
            if not selected:
                return await interaction.response.send_message(
                    f"❌ Không tìm thấy template `{template}`!", ephemeral=True
                )
            roles_text = format_role_block(selected.get("roles", []), selected.get("weapon_slots", {}))
            modal = MassingModal(prefill_roles=roles_text, prefill_note=selected.get("note", ""))
        else:
            modal = MassingModal()
        try:
            await interaction.response.send_modal(modal)
        except discord.HTTPException as error:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Không thể mở form Massing: `{error}`", ephemeral=True)

    @app_commands.command(name="masstemplatelist", description="Xem danh sách template Massing hiện có")
    async def masstemplatelist_cmd(self, interaction: discord.Interaction):
        if not _templates_loaded:
            return await interaction.response.send_message("❌ Kho template chưa tải được.", ephemeral=True)
        templates = active_templates
        if not templates:
            return await interaction.response.send_message("📋 Chưa có template nào được lưu.", ephemeral=True)
        lines = []
        for key, template_data in templates.items():
            name = template_data.get("display_name", key)
            role_count = len(template_data.get("roles", []))
            slot_count = sum(
                limit for wlist in template_data.get("weapon_slots", {}).values() for _, limit in wlist
            )
            lines.append(f"• **{name}** — {role_count} role, {slot_count} slot")
        embed = discord.Embed(
            title=f"📋 Template Massing ({len(templates)})",
            description="\n".join(lines),
            color=0x3498db,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="masstemplatedelete", description="Xóa template Massing (Officer only)")
    @app_commands.describe(template="Tên template cần xóa")
    @app_commands.autocomplete(template=template_autocomplete)
    async def masstemplatedelete_cmd(self, interaction: discord.Interaction, template: str):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được lệnh này!", ephemeral=True)
        if not _templates_loaded:
            return await interaction.response.send_message("❌ Kho template chưa tải được.", ephemeral=True)
        key = template.lower()
        await interaction.response.defer(ephemeral=True)
        async with _massing_state_lock:
            existing = active_templates.get(key)
            if not existing:
                return await interaction.followup.send(
                    f"❓ Không tìm thấy template `{template}`.", ephemeral=True
                )
            name = existing.get("display_name", template)
            updated = deepcopy(active_templates)
            del updated[key]
            try:
                await save_templates(updated)
            except Exception as error:
                return await interaction.followup.send(f"❌ Không thể xóa template: `{error}`", ephemeral=True)
            await interaction.edit_original_response(content=f"🧹 Đã xóa template **{name}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(MassingCog(bot))
