import os

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.config import STORAGE_DIR
from core.permissions import is_officer
from core.storage import load_json, save_json, save_json_async

# ==============================================================================
# HỆ THỐNG MASSING
# ==============================================================================
MASSING_FILE = os.path.join(STORAGE_DIR, "tnc_massing_v1.json")
TEMPLATES_FILE = os.path.join(STORAGE_DIR, "tnc_templates_v1.json")

active_parties = {}
role_icons = {"Tank": "🛡️", "Heal": "💚", "SP": "💜", "DPS": "⚔️"}


def load_massing():
    return load_json(MASSING_FILE, dict)


async def save_massing():
    await save_json_async(active_parties, MASSING_FILE)


def load_templates():
    return load_json(TEMPLATES_FILE, dict)


async def save_templates(data):
    await save_json_async(data, TEMPLATES_FILE)


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
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ Không còn slot trống nào!", ephemeral=True)
        role, weapon = self.values[0].split("|", 1)
        limit = dict(party["weapon_slots"][role])[weapon]
        current = party["slots"][role].setdefault(weapon, [])
        if len(current) >= limit:
            return await interaction.response.send_message("❌ Slot vừa đầy, thử lại!", ephemeral=True)
        if self.mode == "move":
            self.parent_view._remove_member_everywhere(party, self.target_uid)
        current.append(self.target_uid)
        await save_massing()
        self.parent_view.rebuild_buttons()
        await interaction.response.edit_message(
            content=f"✅ Đã {'thêm' if self.mode=='add' else 'chuyển'} <@{self.target_uid}> vào **{role}-{weapon}**.",
            embed=None, view=None
        )
        try:
            await self.parent_view.refresh_original(interaction, party)
        except Exception as e:
            print(f"[Error] {e}")
            pass


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
            self.parent_view._remove_member_everywhere(party, target_uid)
            await save_massing()
            self.parent_view.rebuild_buttons()
            await interaction.response.edit_message(content=f"✅ Đã kick <@{target_uid}> khỏi party.", view=None)
            try:
                await self.parent_view.refresh_original(interaction, party)
            except Exception as e:
                print(f"[Error] {e}")
                pass
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

        if party["roles"]:
            fill_btn = discord.ui.Button(
                label=f"🔄 Fill ({len(party.get('fills', []))})",
                style=discord.ButtonStyle.secondary,
                custom_id=f"fill_{self.party_id}",
                disabled=not is_party_full
            )
            fill_btn.callback = self.fill_callback
            self.add_item(fill_btn)

        leave_btn = discord.ui.Button(label="❌ Leave", style=discord.ButtonStyle.red, custom_id=f"leave_{self.party_id}")
        leave_btn.callback = self.leave_callback
        self.add_item(leave_btn)

        add_btn = discord.ui.Button(label="➕ Add", style=discord.ButtonStyle.success, custom_id=f"add_{self.party_id}")
        add_btn.callback = self.add_callback
        self.add_item(add_btn)

        move_btn = discord.ui.Button(label="🔀 Move", style=discord.ButtonStyle.primary, custom_id=f"move_{self.party_id}")
        move_btn.callback = self.move_callback
        self.add_item(move_btn)

        kick_btn = discord.ui.Button(label="👋 Kick", style=discord.ButtonStyle.danger, custom_id=f"kick_{self.party_id}")
        kick_btn.callback = self.kick_callback
        self.add_item(kick_btn)

        note_btn = discord.ui.Button(label="📝 Note", style=discord.ButtonStyle.secondary, custom_id=f"note_{self.party_id}")
        note_btn.callback = self.note_callback
        self.add_item(note_btn)

        del_btn = discord.ui.Button(label="🗑️ Delete", style=discord.ButtonStyle.danger, custom_id=f"delete_{self.party_id}")
        del_btn.callback = self.delete_callback
        self.add_item(del_btn)

        copy_btn = discord.ui.Button(label="📋 Copy", style=discord.ButtonStyle.secondary, custom_id=f"copy_{self.party_id}")
        copy_btn.callback = self.copy_callback
        self.add_item(copy_btn)

        savetpl_btn = discord.ui.Button(label="💾 Save Template", style=discord.ButtonStyle.secondary, custom_id=f"savetpl_{self.party_id}")
        savetpl_btn.callback = self.save_template_callback
        self.add_item(savetpl_btn)

        ping_btn = discord.ui.Button(label="📢 Ping All", style=discord.ButtonStyle.secondary, custom_id=f"ping_{self.party_id}")
        ping_btn.callback = self.ping_callback
        self.add_item(ping_btn)

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
            party = active_parties.get(self.party_id)
            if not party:
                return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
            uid = interaction.user.id
            self._remove_member_everywhere(party, uid)
            limit = dict(party["weapon_slots"][role])[weapon]
            current = party["slots"][role].setdefault(weapon, [])
            if len(current) >= limit:
                return await interaction.response.send_message(f"❌ Slot **{role}-{weapon}** vừa đầy!", ephemeral=True)
            current.append(uid)
            await save_massing()
            self.rebuild_buttons()
            await interaction.response.edit_message(embed=build_party_embed(party), view=self)
        return callback

    async def fill_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        if not self._is_full(party):
            return await interaction.response.send_message("⚠️ Party chưa full!", ephemeral=True)
        uid = interaction.user.id
        for role in party["roles"]:
            for weapon in party["slots"][role]:
                if uid in party["slots"][role][weapon]:
                    return await interaction.response.send_message("⚠️ Bạn đã có slot chính thức rồi!", ephemeral=True)
        if uid in party.get("fills", []):
            return await interaction.response.send_message("⚠️ Bạn đã trong danh sách Fill rồi!", ephemeral=True)
        party.setdefault("fills", []).append(uid)
        await save_massing()
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=build_party_embed(party), view=self)

    async def leave_callback(self, interaction: discord.Interaction):
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        uid = interaction.user.id
        if not self._remove_member_everywhere(party, uid):
            return await interaction.response.send_message("⚠️ Bạn chưa đăng ký party này.", ephemeral=True)
        await save_massing()
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=build_party_embed(party), view=self)

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
        del active_parties[self.party_id]
        await save_massing()
        await interaction.response.edit_message(content="🗑️ **Party đã bị xóa.**", embed=None, view=None)

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

    def __init__(self, prefill_roles=None, prefill_note=None):
        super().__init__()
        if prefill_roles:
            self.party_roles.default = prefill_roles
        if prefill_note:
            self.party_note.default = prefill_note

    async def on_submit(self, interaction: discord.Interaction):
        time_str = self.party_time.value.strip() if self.party_time.value else ""
        note = self.party_note.value.strip() if self.party_note.value else ""
        roles, weapon_slots = parse_role_block(self.party_roles.value or "")
        party_id = str(interaction.id)
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
        active_parties[party_id] = party_data
        view = PartyView(party_id)
        await interaction.response.send_message(embed=build_party_embed(party_data), view=view)
        msg = await interaction.original_response()
        active_parties[str(msg.id)] = active_parties.pop(party_id)
        active_parties[str(msg.id)]["id"] = str(msg.id)
        view.party_id = str(msg.id)
        view.rebuild_buttons()  # FIX: đồng bộ custom_id nút bấm với msg.id mới
        await save_massing()
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
        party = active_parties.get(self.party_id)
        if not party:
            return await interaction.response.send_message("❌ Party hết hạn do bot restart.", ephemeral=True)
        party["note"] = self.note_text.value.strip() if self.note_text.value else ""
        await save_massing()
        await interaction.response.edit_message(embed=build_party_embed(party), view=self.parent_view)


class ConfirmOverwriteTemplateView(discord.ui.View):
    def __init__(self, name, key, party):
        super().__init__(timeout=30)
        self.name = name
        self.key = key
        self.party = party

    @discord.ui.button(label="✅ Ghi đè", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        templates = load_templates()
        templates[self.key] = {
            "display_name": self.name,
            "roles": self.party["roles"],
            "weapon_slots": self.party["weapon_slots"],
            "note": self.party.get("note", "")
        }
        await save_templates(templates)
        await interaction.response.edit_message(content=f"✅ Đã ghi đè template **{self.name}**!", view=None)

    @discord.ui.button(label="❌ Hủy", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🚫 Đã hủy, không ghi đè template.", view=None)


class SaveTemplateModal(discord.ui.Modal, title="💾 Lưu Template"):
    template_name = discord.ui.TextInput(
        label="Tên Template", placeholder="Ví dụ: PVP Standard, ZvZ 20...", max_length=50
    )

    def __init__(self, party):
        super().__init__()
        self.party = party

    async def on_submit(self, interaction: discord.Interaction):
        name = self.template_name.value.strip()
        key = name.lower()
        templates = load_templates()
        if key in templates:
            view = ConfirmOverwriteTemplateView(name, key, self.party)
            return await interaction.response.send_message(
                f"⚠️ Template **{name}** đã tồn tại. Bạn có muốn ghi đè không?", view=view, ephemeral=True
            )
        templates[key] = {
            "display_name": name,
            "roles": self.party["roles"],
            "weapon_slots": self.party["weapon_slots"],
            "note": self.party.get("note", "")
        }
        await save_templates(templates)
        await interaction.response.send_message(f"✅ Đã lưu template **{name}**!", ephemeral=True)


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
        """Khôi phục các party Massing sau khi bot restart (đăng ký lại nút với Discord)."""
        loaded = load_massing()
        if not loaded:
            return
        active_parties.update(loaded)
        restored = 0
        for pid in list(active_parties.keys()):
            try:
                self.bot.add_view(PartyView(pid))
                restored += 1
            except Exception as e:
                print(f"⚠️ Không khôi phục được party {pid}: {e}")
        print(f"🔄 Đã khôi phục {restored} party Massing sau restart!")
        self.weekly_clear_parties.start()  # Bắt đầu task tự dọn party hàng tuần

    async def cog_unload(self):
        self.weekly_clear_parties.cancel()

    @tasks.loop(hours=168)  # 7 ngày = 168 giờ
    async def weekly_clear_parties(self):
        """Tự động xóa toàn bộ party Massing đang active mỗi 7 ngày.
        Templates không bị đụng — chỉ xóa được bằng /masstemplatedelete."""
        count = len(active_parties)
        active_parties.clear()
        await save_massing()
        print(f"🧹 [Auto-Clean] Đã xóa {count} party Massing cũ sau 7 ngày.")

    @weekly_clear_parties.before_loop
    async def before_weekly_clear(self):
        await self.bot.wait_until_ready()

    async def template_autocomplete(self, interaction: discord.Interaction, current: str):
        templates = load_templates()
        choices = []
        for key, t in templates.items():
            name = t.get("display_name", key)
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        return choices[:25]

    @app_commands.command(name="massing", description="Tạo party Massing (PVP/PVE/...) cho Guild TNC")
    @app_commands.describe(template="Dùng template đã lưu (không bắt buộc, để trống nếu tạo mới hoàn toàn)")
    @app_commands.autocomplete(template=template_autocomplete)
    async def massing_slash(self, interaction: discord.Interaction, template: str = None):
        try:
            if template:
                templates = load_templates()
                t = templates.get(template.lower())
                if not t:
                    return await interaction.response.send_message(f"❌ Không tìm thấy template `{template}`!", ephemeral=True)
                roles_text = format_role_block(t.get("roles", []), t.get("weapon_slots", {}))
                modal = MassingModal(prefill_roles=roles_text, prefill_note=t.get("note", ""))
            else:
                modal = MassingModal()
            await interaction.response.send_modal(modal)
        except discord.HTTPException:
            pass

    @app_commands.command(name="masstemplatelist", description="Xem danh sách template Massing hiện có")
    async def masstemplatelist_cmd(self, interaction: discord.Interaction):
        templates = load_templates()
        if not templates:
            return await interaction.response.send_message("📋 Chưa có template nào được lưu.", ephemeral=True)
        lines = []
        for key, t in templates.items():
            name = t.get("display_name", key)
            role_count = len(t.get("roles", []))
            slot_count = sum(limit for wlist in t.get("weapon_slots", {}).values() for _, limit in wlist)
            lines.append(f"• **{name}** — {role_count} role, {slot_count} slot")
        embed = discord.Embed(title=f"📋 Template Massing ({len(templates)})", description="\n".join(lines), color=0x3498db)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="masstemplatedelete", description="Xóa template Massing (Officer only)")
    @app_commands.describe(template="Tên template cần xóa")
    @app_commands.autocomplete(template=template_autocomplete)
    async def masstemplatedelete_cmd(self, interaction: discord.Interaction, template: str):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được lệnh này!", ephemeral=True)
        templates = load_templates()
        key = template.lower()
        if key not in templates:
            return await interaction.response.send_message(f"❓ Không tìm thấy template `{template}`.", ephemeral=True)
        name = templates[key].get("display_name", template)
        del templates[key]
        await save_templates(templates)
        await interaction.response.send_message(f"🧹 Đã xóa template **{name}**.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MassingCog(bot))
