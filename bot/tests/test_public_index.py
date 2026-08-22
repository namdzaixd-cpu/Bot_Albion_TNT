import asyncio
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

import main as bot_main
from core import config_store, storage
from core.webserver import app
from discord import app_commands
from discord.ext import tasks


ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "bot" / "core" / "templates" / "index.html"

EXPECTED_SECTIONS = {
    "overview",
    "problems",
    "modules",
    "architecture",
    "workflows",
    "commands",
    "data",
    "stack",
}

EXPECTED_COMMANDS = {
    "/aboutme",
    "/recuibot toggle",
    "/recuibot set_apply_channel",
    "/recuibot setup_channels",
    "/recuibot setup_roles",
    "/recuibot list",
    "/spupdate",
    "/spcheck",
    "/sphistory",
    "/sptop",
    "/splog",
    "/spexport",
    "/addsp",
    "/removesp",
    "/removesprole",
    "/resetsp",
    "/massing",
    "/masstemplatelist",
    "/masstemplatedelete",
    "/guildconfig",
    "/guildcheck",
    "/newmembers",
    "/alojoin",
    "/aloleave",
    "/alonametoggle",
    "/alo",
    "/aloconfig",
    "/alomute",
    "/alounmute",
    "/coresetup",
    "/coreadd",
    "/coreremove",
    "/coreautoreact",
    "/corelist",
}

EXPECTED_LINKS = {
    "github": "https://github.com/namdzaixd-cpu/Bot_Albion_TNT",
    "discord": "https://discord.gg/PhMqCskBJ",
    "chatbot": "https://github.com/kudominer/TNC-Chatbot",
    "albion": "https://albiononline.com",
}


class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.commands = []
        self.links = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("data-command"):
            self.commands.append(values["data-command"])
        if tag == "a" and values.get("data-link"):
            self.links.setdefault(values["data-link"], []).append(values.get("href"))


def render_index():
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    parser = IndexParser()
    parser.feed(html)
    return html, parser


def load_production_commands():
    async def _load():
        bot = bot_main.TNCBot()
        try:
            bot.loop = asyncio.get_running_loop()

            async def _fake_sync(*args, **kwargs):
                return []

            bot.tree.sync = _fake_sync
            with (
                mock.patch.object(
                    bot_main.SystemLogger,
                    "start",
                    lambda *args, **kwargs: None,
                ),
                mock.patch.object(bot_main, "start_heartbeat", lambda *args, **kwargs: None),
                mock.patch.object(tasks.Loop, "start", lambda self, *args, **kwargs: None),
                mock.patch.object(storage, "safe_select", return_value=(None, None)),
                mock.patch.object(config_store, "safe_select", return_value=(None, None)),
            ):
                await bot.setup_hook()

            return {
                f"/{command.qualified_name}"
                for command in bot.tree.walk_commands()
                if isinstance(command, app_commands.Command)
            }
        finally:
            config_store.invalidate()
            await bot.close()

    return asyncio.run(_load())


def test_public_index_matches_project_contract():
    template = INDEX_PATH.read_text(encoding="utf-8")
    html, parser = render_index()

    assert '<html lang="vi">' in html
    assert "{{ session_id }}" in template
    assert "{{ session_id }}" not in html
    assert "Web service đang phản hồi" in html
    assert EXPECTED_SECTIONS <= parser.ids
    assert set(parser.commands) == EXPECTED_COMMANDS == load_production_commands()
    assert len(parser.commands) == len(EXPECTED_COMMANDS) == 34
    assert parser.links == {key: [href] for key, href in EXPECTED_LINKS.items()}


def test_public_index_has_no_stale_or_placeholder_claims():
    html, _ = render_index()
    forbidden = {
        "YOUR_CLIENT_ID",
        "BOT ONLINE",
        "GitHub Sync",
        "JSON DB",
        "Auto Backup",
        "/blacklist add",
        "/registertnc",
    }
    assert all(term not in html for term in forbidden)


def test_public_index_includes_accessible_progressive_enhancement():
    html, parser = render_index()

    assert 'class="skip-link"' in html
    assert 'id="command-search"' in html
    assert 'aria-live="polite"' in html
    assert "prefers-reduced-motion: reduce" in html
    assert "data-system" in html
    assert "IntersectionObserver" in html
    assert "command-search" in html
    assert len(parser.commands) == 34
