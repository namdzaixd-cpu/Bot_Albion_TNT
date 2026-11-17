"""Consumer-visible regressions for translation, TTS cleanup and blacklist output."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from cogs import alo_tts, blacklist, update_translator


def test_failed_translation_can_be_requested_again():
    async def exercise():
        message = SimpleNamespace(id=101, content="Guild update")
        sent = []
        thread = SimpleNamespace(send=mock.AsyncMock(side_effect=sent.append))
        cog = update_translator.UpdateTranslatorCog(mock.Mock())
        cog._translate = mock.AsyncMock(side_effect=[None, "Bản dịch thành công"])
        cog._get_or_create_thread = mock.AsyncMock(return_value=thread)
        await cog._ensure_translation(message)
        await cog._ensure_translation(message)
        assert "Bản dịch thành công" in sent
        assert message.id not in cog.in_progress
    asyncio.run(exercise())


def test_translation_exception_does_not_permanently_lock_message():
    async def exercise():
        cog = update_translator.UpdateTranslatorCog(mock.Mock())
        message = SimpleNamespace(id=102, content="Guild update")
        cog._translate = mock.AsyncMock(side_effect=RuntimeError("synthetic failure"))
        with pytest.raises(RuntimeError):
            await cog._ensure_translation(message)
        assert message.id not in cog.in_progress
    asyncio.run(exercise())


def test_reply_request_reports_translation_failure_instead_of_success():
    async def exercise():
        replies = []
        target = SimpleNamespace(id=103, content="Guild update")
        request = SimpleNamespace(reference=SimpleNamespace(resolved=target),
                                  guild=SimpleNamespace(id=1),
                                  reply=mock.AsyncMock(side_effect=replies.append))
        cog = update_translator.UpdateTranslatorCog(mock.Mock())
        cog._translate = mock.AsyncMock(return_value=None)
        cog._get_or_create_thread = mock.AsyncMock(return_value=SimpleNamespace(id=104, name="Update"))
        await cog._handle_translate_request(request)
        assert replies and not replies[0].startswith("✅")
        assert "dịch" in replies[0].lower()
    asyncio.run(exercise())


def test_tts_generation_failure_removes_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(alo_tts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(alo_tts, "gTTS", mock.Mock(side_effect=RuntimeError("generation failed")))
    with pytest.raises(RuntimeError, match="generation failed"):
        alo_tts.generate_tts_file("hello")
    assert list(tmp_path.iterdir()) == []


def test_tts_success_has_finite_provider_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(alo_tts, "DATA_DIR", tmp_path)
    def create_audio(*, text, lang, timeout=None):
        assert timeout is not None and 0 < timeout <= 30
        return SimpleNamespace(save=lambda path: Path(path).write_bytes(b"synthetic audio"))
    monkeypatch.setattr(alo_tts, "gTTS", create_audio)
    path = Path(alo_tts.generate_tts_file("hello"))
    assert path.read_bytes() == b"synthetic audio"
    path.unlink()


def test_tts_playback_failure_cleans_audio(tmp_path, monkeypatch):
    async def exercise():
        path = tmp_path / "voice.mp3"
        path.write_bytes(b"synthetic audio")
        vc = SimpleNamespace(channel=SimpleNamespace(id=10), is_connected=lambda: True,
                             is_playing=lambda: False,
                             play=mock.Mock(side_effect=RuntimeError("playback failed")))
        bot = SimpleNamespace(loop=asyncio.get_running_loop(), get_guild=lambda _: SimpleNamespace(voice_client=vc))
        cog = alo_tts.AloTtsCog(bot)
        cog.voice_sessions[1] = {"channel_id": 10}
        cog.tts_queues[1] = asyncio.Queue()
        cog.tts_queues[1].put_nowait((10, "hello"))
        monkeypatch.setattr(alo_tts, "generate_tts_file", lambda _: str(path))
        monkeypatch.setattr(alo_tts.discord, "FFmpegPCMAudio", lambda *a, **k: SimpleNamespace(cleanup=lambda: None))
        await cog._tts_worker(1)
        assert not path.exists()
    asyncio.run(exercise())


def test_blacklist_large_legacy_reasons_render_without_losing_entries(monkeypatch):
    async def exercise():
        entries = [{"discord_id": str(100000000000000000 + n), "ingame_name": f"Player{n}",
                    "reason": ("legacy reason " * 200) + f" END{n}"} for n in range(30)]
        pages = []
        async def send(**kwargs):
            pages.extend(kwargs.get("embeds", [kwargs["embed"]] if "embed" in kwargs else []))
        interaction = SimpleNamespace(user=object(), response=SimpleNamespace(defer=mock.AsyncMock()),
                                      followup=SimpleNamespace(send=send))
        cog = blacklist.BlacklistCog(mock.Mock())
        cog.blacklist_db.get_all = mock.AsyncMock(return_value=entries)
        monkeypatch.setattr(blacklist, "is_officer", lambda _: True)
        await cog.blacklist_view.callback(cog, interaction)
        rendered = "\n".join((page.description or "") + "\n" + "\n".join(field.value for field in page.fields) for page in pages)
        for page in pages:
            assert len(page) <= 6000
            assert len(page.fields) <= 25
            assert all(len(field.value) <= 1024 for field in page.fields)
            assert len(page.description or "") <= 4096
        for n in range(30):
            assert f"Player{n}" in rendered and f"END{n}" in rendered
    asyncio.run(exercise())


def test_cancelled_tts_generation_cleans_late_executor_result(tmp_path):
    async def exercise():
        loop = asyncio.get_running_loop()
        generated = loop.create_future()
        started = asyncio.Event()
        def run_in_executor(*_):
            started.set()
            return generated
        vc = SimpleNamespace(channel=SimpleNamespace(id=10), is_connected=lambda: True)
        bot = SimpleNamespace(loop=SimpleNamespace(run_in_executor=run_in_executor),
                              get_guild=lambda _: SimpleNamespace(voice_client=vc))
        cog = alo_tts.AloTtsCog(bot)
        cog.voice_sessions[1] = {"channel_id": 10}
        cog.tts_queues[1] = asyncio.Queue()
        cog.tts_queues[1].put_nowait((10, "hello"))
        worker = asyncio.create_task(cog._tts_worker(1))
        await started.wait()
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker
        path = tmp_path / "late.mp3"
        path.write_bytes(b"late audio")
        generated.set_result(str(path))
        await asyncio.sleep(0)
        assert not path.exists()
    asyncio.run(exercise())


def test_blacklist_paginates_even_when_server_caps_below_requested_page(monkeypatch):
    rows = [{"discord_id": str(n)} for n in range(5)]
    class Query:
        def select(self, *_): return self
        def order(self, *_): return self
        def range(self, start, end):
            self.start = start
            return self
    class Client:
        def table(self, _): return Query()
    async def execute(builder):
        query = builder(Client())
        return SimpleNamespace(data=rows[query.start:query.start + 2]), None
    monkeypatch.setattr(blacklist, "async_execute", execute)
    assert asyncio.run(blacklist.GlobalBlacklist().get_all()) == rows


def test_blacklist_database_failure_is_not_reported_as_empty(monkeypatch):
    async def exercise():
        messages = []
        interaction = SimpleNamespace(user=object(), response=SimpleNamespace(defer=mock.AsyncMock()),
                                      followup=SimpleNamespace(send=mock.AsyncMock(
                                          side_effect=lambda content, **_: messages.append(content))))
        monkeypatch.setattr(blacklist, "is_officer", lambda _: True)
        monkeypatch.setattr(blacklist, "async_execute", mock.AsyncMock(return_value=(None, "synthetic outage")))
        cog = blacklist.BlacklistCog(mock.Mock())
        await cog.blacklist_view.callback(cog, interaction)
        assert messages and "Không đọc được" in messages[0]
        assert "trống" not in messages[0]
    asyncio.run(exercise())


def test_tts_real_provider_constructor_supports_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(alo_tts, "DATA_DIR", tmp_path)
    monkeypatch.setattr(alo_tts.gTTS, "save", lambda self, path: Path(path).write_bytes(b"audio"))
    path = Path(alo_tts.generate_tts_file("xin chào"))
    assert path.read_bytes() == b"audio"
    path.unlink()
