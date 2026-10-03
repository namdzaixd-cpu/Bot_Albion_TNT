import io
from datetime import datetime, timezone, timedelta

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from core.permissions import is_officer
from core.db import DBError, async_execute


def _rpc_data(response):
    data = getattr(response, "data", None) if response is not None else None
    return data


def parse_sp_log(text: str) -> tuple[list[dict], int]:
    """Return valid rows in file order and the number of invalid non-header rows."""
    rows = []
    invalid = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [part.strip().strip('"') for part in line.split("\t")]
        if len(parts) < 4:
            invalid += 1
            continue
        if parts[0].lower() in {"date", "timestamp", "player"}:
            continue
        try:
            timestamp = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
            amount = int(parts[3])
        except (ValueError, IndexError):
            invalid += 1
            continue
        player = parts[1].strip()
        if not player:
            invalid += 1
            continue
        rows.append({
            "player_name": player,
            "amount": amount,
            "log_timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return rows, invalid


async def load_sp():
    data = {"history": {}, "last_update": "Chưa có dữ liệu"}
    meta_resp, error = await async_execute(
        lambda client: client.table("sp_metadata").select("last_update").eq("id", 1),
        retries=1,
    )
    if error:
        raise DBError(error)
    if meta_resp and meta_resp.data:
        data["last_update"] = meta_resp.data[0]["last_update"]

    history_resp, error = await async_execute(
        lambda client: client.table("user_economy").select("user_id, silver_pieces"),
        retries=1,
    )
    if error:
        raise DBError(error)
    for row in history_resp.data if history_resp and history_resp.data else []:
        data["history"][row["user_id"]] = row["silver_pieces"]
    return data


async def apply_sp_import(rows: list[dict]):
    response, error = await async_execute(
        lambda client: client.rpc("apply_siphoned_import", {"p_rows": rows}),
        retries=1,
    )
    if error:
        raise DBError(error)
    result = _rpc_data(response)
    if not isinstance(result, dict):
        raise DBError("SP import RPC returned no result")
    return result


async def adjust_sp(adjustments: list[dict], *, only_existing: bool = False):
    response, error = await async_execute(
        lambda client: client.rpc(
            "adjust_siphoned_points",
            {"p_adjustments": adjustments, "p_only_existing": only_existing},
        ),
        retries=1,
    )
    if error:
        raise DBError(error)
    return _rpc_data(response) or []


async def delete_sp_users(user_ids: list[str]):
    response, error = await async_execute(
        lambda client: client.rpc("delete_siphoned_users", {"p_user_ids": user_ids}),
        retries=1,
    )
    if error:
        raise DBError(error)
    return _rpc_data(response) or []


async def reset_sp_history():
    response, error = await async_execute(
        lambda client: client.rpc("reset_siphoned_points", {}),
        retries=1,
    )
    if error:
        raise DBError(error)
    result = _rpc_data(response)
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    return result is True

# ==============================================================================
# PAGINATOR — dùng chung cho spcheck và sptop
# ==============================================================================

class SiphonedPaginator(discord.ui.View):
    def __init__(self, data, last_update, title="💎 TNC SIPHONED LEADERBOARD", label="Mốc Log Đã Cập Nhật:"):
        super().__init__(timeout=86400)
        self.data = data
        self.last_update = last_update
        self.title = title
        self.label = label
        self.current_page = 0
        self.per_page = 15

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]
        total_pages = (len(self.data) - 1) // self.per_page + 1 if self.data else 1
        embed = discord.Embed(title=self.title, color=0x9b59b6)
        embed.add_field(name=f"📅 {self.label}", value=f"`{self.last_update}`", inline=False)
        desc = ""
        for i, (player, value) in enumerate(page_data, start + 1):
            desc += f"**#{i}** `{player}` ➜ **{value:,}**\n"
        embed.description = desc if desc else "Không có dữ liệu đóng góp."
        embed.set_footer(text=f"Trang {self.current_page + 1}/{total_pages} • Tổng số: {len(self.data)} người")
        return embed

    @discord.ui.button(label="⬅️ Trước", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Sau ➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (self.current_page + 1) * self.per_page < len(self.data):
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()


# ==============================================================================
# CONFIRM VIEW — dùng cho /resetsp
# ==============================================================================

class ResetConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=15)
        self.confirmed = False

    @discord.ui.button(label="✅ Xác nhận Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            if not await reset_sp_history():
                raise DBError("reset RPC returned no confirmation")
        except Exception as exc:
            return await interaction.edit_original_response(
                content=f"❌ Không thể reset dữ liệu Siphoned: {exc}",
                view=self,
            )
        self.confirmed = True
        self.stop()
        await interaction.edit_original_response(
            content="🧹 Toàn bộ bảng xếp hạng điểm Siphoned đã được reset!",
            view=None,
        )
    @discord.ui.button(label="❌ Huỷ", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="↩️ Đã huỷ thao tác reset.", view=None)


# ==============================================================================
# COG
# ==============================================================================

class SiphonedCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /spupdate ──────────────────────────────────────────────────────────────
    @app_commands.command(name="spupdate", description="Cập nhật file log Siphoned (tự kiểm tra ngày tháng)")
    async def spupdate(self, interaction: discord.Interaction, file_log: discord.Attachment):
        await interaction.response.defer()
        if not file_log.filename.lower().endswith(".txt"):
            return await interaction.followup.send("❌ Vui lòng đính kèm tệp văn bản định dạng `.txt`!")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_log.url) as response:
                    response.raise_for_status()
                    text = await response.text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            return await interaction.followup.send(f"❌ Không thể tải file log: {exc}")

        rows, invalid = parse_sp_log(text)
        if not rows:
            return await interaction.followup.send("❌ Không đọc được dòng log hợp lệ từ file!")
        try:
            result = await apply_sp_import(rows)
        except Exception as exc:
            return await interaction.followup.send(f"❌ Không thể lưu dữ liệu SP; giao dịch đã thất bại: {exc}")

        count = int(result.get("applied", 0))
        skipped = invalid + int(result.get("skipped", 0))
        overlap_note = f"\n⏩ Bỏ qua **{skipped}** dòng cũ/không hợp lệ." if skipped else ""
        if count == 0:
            return await interaction.followup.send(
                f"ℹ️ Không có dòng mới hơn watermark được cộng.{overlap_note}\n"
                f"Mốc hiện tại: `{result.get('last_update', 'N/A')}`"
            )
        await interaction.followup.send(
            f"✅ Xử lý thành công **{count}** dòng dữ liệu mới.{overlap_note}\n"
            f"Mốc log: `{result['last_update']}` (đã lưu điểm, lịch sử và watermark cùng giao dịch)"
        )

    # ── /spcheck ───────────────────────────────────────────────────────────────
    @app_commands.command(name="spcheck", description="Xem bảng xếp hạng tích lũy điểm Siphoned")
    async def spcheck(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            data = await load_sp()
        except Exception as exc:
            return await interaction.followup.send(f"❌ Không thể tải dữ liệu Siphoned: {exc}")
        history = data.get("history", {})
        if not history:
            return await interaction.followup.send("📊 Hiện tại hệ thống Siphoned chưa có dữ liệu.")
        sorted_sp = sorted(history.items(), key=lambda x: x[1], reverse=True)
        view = SiphonedPaginator(sorted_sp, data.get("last_update", "N/A"))
        await interaction.followup.send(embed=view.create_embed(), view=view)

    # ── /sphistory ─────────────────────────────────────────────────────────────
    @app_commands.command(name="sphistory", description="Xem lịch sử đóng góp SP của một thành viên")
    @app_commands.describe(player="Tên player trong game (phân biệt hoa/thường)")
    async def sphistory(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        response, error = await async_execute(
            lambda client: client.table("sp_transactions")
            .select("amount, log_timestamp")
            .eq("player_name", player)
            .order("log_timestamp", desc=True)
            .limit(20),
            retries=1,
        )
        if error:
            return await interaction.followup.send(f"❌ Lỗi khi truy vấn dữ liệu: {error}")
        rows = response.data if response and response.data else []
        if not rows:
            return await interaction.followup.send(
                f"❓ Không tìm thấy lịch sử đóng góp nào của `{player}`.\n"
                f"*(Lịch sử chỉ có từ khi tính năng này được bật)*"
            )
        total = sum(row["amount"] for row in rows)
        desc = ""
        for index, row in enumerate(rows, 1):
            timestamp = row["log_timestamp"][:16] if row["log_timestamp"] else "N/A"
            desc += f"**#{index}** `{timestamp}` ➜ **+{row['amount']:,}** SP\n"
        embed = discord.Embed(title=f"📋 Lịch sử SP — {player}", description=desc, color=0x9b59b6)
        embed.set_footer(text=f"Tổng {len(rows)} lần đóng góp gần nhất • Tổng cộng: {total:,} SP")
        await interaction.followup.send(embed=embed)
    # ── /sptop ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="sptop", description="Xem bảng xếp hạng SP theo khoảng thời gian")
    @app_commands.describe(period="Khoảng thời gian muốn xem")
    @app_commands.choices(period=[
        app_commands.Choice(name="30 ngày gần nhất", value="30d"),
        app_commands.Choice(name="3 tháng gần nhất", value="90d"),
        app_commands.Choice(name="6 tháng gần nhất", value="6m"),
        app_commands.Choice(name="Tất cả (từ khi bật tính năng)", value="all"),
    ])
    async def sptop(self, interaction: discord.Interaction, period: str):
        await interaction.response.defer()
        period_map = {"30d": 30, "90d": 90, "6m": 180}
        period_label = {"30d": "30 ngày", "90d": "3 tháng", "6m": "6 tháng", "all": "Toàn bộ lịch sử"}

        def build(client):
            query = client.table("sp_transactions").select("player_name, amount")
            if period != "all":
                cutoff = (datetime.now(timezone.utc) - timedelta(days=period_map[period])).isoformat()
                query = query.gte("inserted_at", cutoff)
            return query

        response, error = await async_execute(build, retries=1)
        if error:
            return await interaction.followup.send(f"❌ Lỗi khi truy vấn dữ liệu: {error}")
        rows = response.data if response and response.data else []
        if not rows:
            return await interaction.followup.send(
                f"📊 Không có dữ liệu trong **{period_label[period]}**.\n"
                f"*(Lịch sử chỉ có từ khi tính năng này được bật)*"
            )

        totals: dict[str, int] = {}
        for row in rows:
            totals[row["player_name"]] = totals.get(row["player_name"], 0) + row["amount"]
        sorted_data = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        view = SiphonedPaginator(
            sorted_data,
            period_label[period],
            title=f"💎 TOP SP — {period_label[period].upper()}",
            label="Khoảng thời gian:",
        )
        await interaction.followup.send(embed=view.create_embed(), view=view)
    # ── /splog ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="splog", description="Xem audit log các lần upload log gần nhất (Officer)")
    async def splog(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này!", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        response, error = await async_execute(
            lambda client: client.table("sp_transactions")
            .select("log_timestamp, inserted_at")
            .order("inserted_at", desc=True)
            .limit(200),
            retries=1,
        )
        if error:
            return await interaction.followup.send(f"❌ Lỗi khi truy vấn: {error}")

        rows = response.data if response and response.data else []
        if not rows:
            return await interaction.followup.send("📋 Chưa có audit log nào.")

        # Nhóm theo mốc log_timestamp (mỗi lần upload 1 mốc)
        batches: dict[str, int] = {}
        for r in rows:
            key = r["log_timestamp"][:16]
            batches[key] = batches.get(key, 0) + 1

        sorted_batches = sorted(batches.items(), key=lambda x: x[0], reverse=True)[:10]
        desc = ""
        for i, (ts, cnt) in enumerate(sorted_batches, 1):
            desc += f"**#{i}** `{ts}` — **{cnt}** dòng dữ liệu\n"

        embed = discord.Embed(title="📋 Audit Log — SP Transactions", description=desc, color=0xe67e22)
        embed.set_footer(text="Hiển thị tối đa 10 lần upload gần nhất")
        await interaction.followup.send(embed=embed)

    # ── /spexport ──────────────────────────────────────────────────────────────
    @app_commands.command(name="spexport", description="Xuất toàn bộ dữ liệu SP hiện tại ra file .txt (Officer)")
    async def spexport(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
        await interaction.response.defer()
        try:
            data = await load_sp()
        except Exception as exc:
            return await interaction.followup.send(f"❌ Không thể tải dữ liệu SP: {exc}")
        history = data.get("history", {})
        last_update = data.get("last_update", "N/A")
        if not history:
            return await interaction.followup.send("📊 Chưa có dữ liệu SP để xuất.")
        sorted_sp = sorted(history.items(), key=lambda item: item[1], reverse=True)
        lines = ['"Date"\t"Player"\t"Reason"\t"Amount"']
        for player, points in sorted_sp:
            reason = "Withdrawal" if points < 0 else "Deposit"
            lines.append(f'"{last_update}"\t"{player}"\t"{reason}"\t"{points}"')
        file = discord.File(
            io.BytesIO("\n".join(lines).encode("utf-8")),
            filename="tnc_sp_exportdata.txt",
        )
        await interaction.followup.send(
            f"📤 Xuất thành công **{len(sorted_sp)}** thành viên.\nMốc log: `{last_update}`",
            file=file,
        )

    # ── /addsp ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="addsp", description="Cộng tay SP cho một hoặc nhiều thành viên (Officer)")
    @app_commands.describe(name="Tên player(s), cách nhau bằng dấu phẩy", amt="Số SP muốn cộng")
    async def addsp(self, interaction: discord.Interaction, name: str, amt: int):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
        if amt <= 0:
            return await interaction.response.send_message("⚠️ Số điểm phải lớn hơn 0!", ephemeral=True)
        targets = [target.strip() for target in name.split(",") if target.strip()]
        if not targets:
            return await interaction.response.send_message("⚠️ Hãy nhập ít nhất một tên player.", ephemeral=True)
        await interaction.response.defer()
        adjustments = [{"player_name": target, "amount": amt} for target in targets]
        try:
            await adjust_sp(adjustments)
        except Exception as exc:
            return await interaction.followup.send(f"❌ Không thể cộng SP: {exc}")
        if len(targets) == 1:
            return await interaction.followup.send(
                f"💎 **[SIPHONED]** Đã cộng tay **+{amt:,}** SP cho **{targets[0]}**."
            )
        lines = "\n".join(f"✅ `{target}` → +{amt:,} SP" for target in targets)
        await interaction.followup.send(
            f"💎 **[SIPHONED]** Đã cộng **+{amt:,}** SP cho **{len(targets)}** thành viên:\n{lines}"
        )
    @app_commands.command(name="removesp", description="Trừ SP của một hoặc nhiều thành viên (Officer)")
    @app_commands.describe(name="Tên player(s), cách nhau bằng dấu phẩy", amt="Số SP muốn trừ")
    async def removesp(self, interaction: discord.Interaction, name: str, amt: int):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này!", ephemeral=True)
        if amt <= 0:
            return await interaction.response.send_message("⚠️ Số điểm trừ phải lớn hơn 0!", ephemeral=True)
        targets = [target.strip() for target in name.split(",") if target.strip()]
        if not targets:
            return await interaction.response.send_message("⚠️ Hãy nhập ít nhất một tên player.", ephemeral=True)
        await interaction.response.defer()
        adjustments = [{"player_name": target, "amount": -amt} for target in targets]
        try:
            records = await adjust_sp(adjustments, only_existing=True)
        except Exception as exc:
            return await interaction.followup.send(f"❌ Không thể trừ SP: {exc}")
        balances = {row["user_id"]: row for row in records}
        results = []
        for target in targets:
            row = balances.get(target)
            if not row or not row.get("applied"):
                results.append(f"❌ `{target}` → không tìm thấy")
            else:
                results.append(f"✅ `{target}` → -{amt:,} SP (còn lại: {row['silver_pieces']:,})")
        if len(targets) == 1 and results[0].startswith("✅"):
            current = balances[targets[0]]["silver_pieces"]
            await interaction.followup.send(
                f"📉 **[SIPHONED]** Đã trừ bớt **-{amt:,}** SP của thành viên **{targets[0]}**.\n"
                f"📊 Điểm hiện tại: **{current:,}** SP."
            )
        else:
            await interaction.followup.send(
                f"📉 **[SIPHONED]** Kết quả trừ SP ({amt:,}) cho **{len(targets)}** thành viên:\n"
                + "\n".join(results)
            )

    # ── /removesprole ──────────────────────────────────────────────────────────
    @app_commands.command(name="removesprole", description="Xóa hoàn toàn một hoặc nhiều thành viên khỏi bảng Siphoned (Officer)")
    @app_commands.describe(name="Tên player(s), cách nhau bằng dấu phẩy")
    async def removesprole(self, interaction: discord.Interaction, name: str):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
        targets = [target.strip() for target in name.split(",") if target.strip()]
        if not targets:
            return await interaction.response.send_message("⚠️ Hãy nhập ít nhất một tên player.", ephemeral=True)
        await interaction.response.defer()
        try:
            removed = set(await delete_sp_users(targets))
        except Exception as exc:
            return await interaction.followup.send(f"❌ Không thể xóa người chơi khỏi bảng SP: {exc}")
        results = [
            f"✅ `{target}` → đã xóa" if target in removed else f"❌ `{target}` → không tìm thấy"
            for target in targets
        ]
        if len(targets) == 1:
            return await interaction.followup.send(
                results[0].replace("✅ ", "🧹 ").replace(
                    " → đã xóa", " đã bị xóa khỏi bảng xếp hạng Siphoned."
                )
            )
        ok = sum(result.startswith("✅") for result in results)
        await interaction.followup.send(
            f"🧹 **Kết quả xóa** {ok}/{len(targets)} thành viên:\n" + "\n".join(results)
        )
    # ── /resetsp ───────────────────────────────────────────────────────────────
    @app_commands.command(name="resetsp", description="Reset toàn bộ bảng điểm Siphoned về 0 (Officer)")
    async def resetsp(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
        view = ResetConfirmView()
        await interaction.response.send_message(
            "⚠️ Bạn có chắc muốn **reset toàn bộ bảng điểm Siphoned**?\n"
            "Hành động này **không thể hoàn tác**!",
            view=view,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SiphonedCog(bot))
