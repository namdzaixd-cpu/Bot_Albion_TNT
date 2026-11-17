"""Round-2 finance regressions against a real, disposable PostgreSQL (Unix socket only).

The full approved chain (schema.sql, migrations/*.sql, migration_security.sql) is applied with
scripts/apply_schema.py to a throwaway cluster; the cogs then run against the real RPCs with
fake Discord objects and a fake provider. No network, no dotenv credentials.
"""
import asyncio
import importlib.util
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.types.json import Jsonb  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
pytestmark = pytest.mark.skipif(
    shutil.which("initdb") is None or shutil.which("pg_ctl") is None,
    reason="PostgreSQL server binaries (initdb/pg_ctl) are required for the SQL regressions",
)


def _load_apply_schema():
    spec = importlib.util.spec_from_file_location("apply_schema_under_test", SCRIPTS / "apply_schema.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dsn():
    root = tempfile.mkdtemp(prefix="pgfin", dir="/tmp")
    data = f"{root}/data"
    subprocess.run(["initdb", "-D", data, "-A", "trust", "-U", "postgres", "-E", "UTF8"],
                   check=True, capture_output=True)
    subprocess.run(
        ["pg_ctl", "-D", data, "-w", "-o",
         f"-c listen_addresses='' -c unix_socket_directories='{root}' -c fsync=off",
         "-l", f"{root}/log", "start"],
        check=True, capture_output=True)
    url = f"host={root} dbname=postgres user=postgres"
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            for role in ("anon", "authenticated", "service_role"):
                conn.execute(f"CREATE ROLE {role} NOLOGIN")
        _load_apply_schema().apply_migrations(url)
        yield url
    finally:
        subprocess.run(["pg_ctl", "-D", data, "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def db(dsn):
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE public.sp_transactions, public.user_economy, public.sp_metadata, "
            "public.core_credited, public.member_registry")
        conn.execute("INSERT INTO public.guild_config (guild_id) VALUES ('g'), ('123') ON CONFLICT DO NOTHING")
    return dsn


def test_chain_is_idempotent_and_sql_regression_script_passes(dsn):
    _load_apply_schema().apply_migrations(dsn)  # second application of the whole chain
    with psycopg.connect(dsn, autocommit=True) as conn:
        cursor = conn.execute((SCRIPTS / "finance_integrity_regression.sql").read_text(encoding="utf-8"))
        while cursor.nextset():  # the script is many statements; the last one reports success
            pass
        assert cursor.fetchone()[0].endswith("all scenarios passed")


class PgClient:
    """Minimal supabase-py stand-in that runs the cog's real calls against PostgreSQL as service_role."""

    def __init__(self, dsn):
        self.conn = psycopg.connect(dsn, autocommit=True, row_factory=psycopg.rows.dict_row)
        self.conn.execute("SET ROLE service_role")

    def rpc(self, name, params):
        def run():
            args = ", ".join(f"{key} => %s" for key in params)
            values = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in params.values()]
            cast = {"p_rows": "::jsonb", "p_totals": "::jsonb", "p_adjustments": "::jsonb"}
            args = ", ".join(f"{k} => %s{cast.get(k, '')}" for k in params)
            row = self.conn.execute(f"SELECT public.{name}({args}) AS value", values).fetchone()
            return SimpleNamespace(data=row["value"])
        return SimpleNamespace(execute=run)

    def table(self, name):
        client = self
        class Select:
            def __init__(self):
                self.filters = []
            def select(self, columns):
                return self
            def eq(self, column, value):
                self.filters.append((column, value))
                return self
            def execute(self):
                where = " AND ".join(f"{c} = %s" for c, _ in self.filters)
                rows = client.conn.execute(
                    f"SELECT * FROM public.{name} WHERE {where}", [v for _, v in self.filters]).fetchall()
                return SimpleNamespace(data=rows)
        return Select()

    def close(self):
        self.conn.close()


@pytest.fixture
def pg(db):
    client = PgClient(db)
    yield client
    client.close()


async def _fake_async_execute(client, builder, retries=1):
    return builder(client).execute(), None


# ── SP: parser, permission, import through the real RPC ─────────────────────────────

def test_parser_carries_reason_and_keeps_identical_lines():
    from cogs.siphoned import parse_sp_log

    line = '"2026-01-01 10:00:00"\t"A"\t"Deposit"\t"10"\n'
    rows, invalid = parse_sp_log(line * 2)
    assert invalid == 0
    assert rows == [{"player_name": "A", "amount": 10, "log_timestamp": "2026-01-01 10:00:00",
                     "reason": "Deposit"}] * 2


def test_spupdate_rejects_non_officer_before_any_download(monkeypatch):
    from cogs import siphoned

    monkeypatch.setattr(siphoned, "is_officer", lambda member: False)
    monkeypatch.setattr(siphoned.aiohttp, "ClientSession", mock.Mock(side_effect=AssertionError("downloaded")))
    apply = mock.AsyncMock()
    monkeypatch.setattr(siphoned, "apply_sp_import", apply)
    interaction = SimpleNamespace(
        user=object(),
        response=SimpleNamespace(defer=mock.AsyncMock(), send_message=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
    )
    cog = siphoned.SiphonedCog(mock.Mock())
    asyncio.run(cog.spupdate.callback(cog, interaction, SimpleNamespace(filename="a.txt", url="x")))
    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True
    apply.assert_not_awaited()


def test_cog_import_and_sptop_use_real_rpcs(pg, monkeypatch):
    from cogs import siphoned

    monkeypatch.setattr(siphoned, "async_execute", lambda builder, retries=1: _fake_async_execute(pg, builder))
    text = (
        '"2026-01-01 10:00:00"\t"A"\t"Deposit"\t"10"\n'
        '"2026-01-01 10:00:00"\t"A"\t"Deposit"\t"10"\n'
        '"2999-01-01 10:00:00"\t"A"\t"Deposit"\t"500"\n'
    )

    async def run():
        rows, _ = siphoned.parse_sp_log(text)
        first = await siphoned.apply_sp_import(rows)
        replay = await siphoned.apply_sp_import(rows)
        assert first["applied"] == 2 and first["future"] == 1
        assert replay["applied"] == 0
        assert await siphoned.reset_sp_history() is True
        assert (await siphoned.apply_sp_import(rows))["applied"] == 0
        # sptop reads an aggregate over the whole history, not a truncated first page
        response, error = await siphoned.async_execute(
            lambda client: client.rpc("sp_period_totals", {"p_days": None}))
        assert error is None
        return response.data

    assert asyncio.run(run()) == [{"player_name": "A", "total": 20}]
    assert pg.conn.execute("SELECT count(*) AS n FROM user_economy").fetchone()["n"] == 0


def test_concurrent_imports_of_the_same_export_apply_once(db):
    rows = [{"player_name": "A", "amount": 10, "log_timestamp": "2026-01-01 10:00:00", "reason": "Deposit"}]
    results, errors = [], []

    def worker():
        client = PgClient(db)
        try:
            results.append(client.rpc("apply_siphoned_import", {"p_rows": rows}).execute().data["applied"])
        except Exception as exc:  # pragma: no cover - surfaced by the assertion below
            errors.append(exc)
        finally:
            client.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert sorted(results) == [0] * 7 + [1]
    with psycopg.connect(db) as conn:
        assert conn.execute("SELECT silver_pieces FROM user_economy WHERE user_id='A'").fetchone()[0] == 10


def test_concurrent_reverted_reclaim_is_compare_and_swap(db):
    with psycopg.connect(db, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO core_credited (message_id, user_id, amount, guild_id, recipient_id, emoji_key,"
            " core_name, core_display, status) VALUES ('1:g','o',100,'g','r','g','G','G','reverted')")
    claimed = []

    def worker():
        client = PgClient(db)
        try:
            params = {"p_message_id": "1:g", "p_guild_id": "g", "p_officer_id": "o", "p_recipient_id": "r",
                      "p_amount": 100, "p_emoji_key": "g", "p_core_name": "G", "p_core_display": "G"}
            claimed.append(client.rpc("claim_core_credit", params).execute().data["claimed"])
        finally:
            client.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert claimed.count(True) == 1


# ── CoreBank: cog + real ledger, fake Discord and provider, explicit interleavings ───

class Harness:
    def __init__(self, pg, monkeypatch):
        from cogs import corebank

        self.corebank = corebank
        self.provider_calls = []
        self.gate = None          # asyncio.Event the next provider call waits on
        self.started = asyncio.Event()
        self.provider_status = 200
        self.reactors = set()     # officer ids currently reacting
        harness = self

        class Response:
            async def __aenter__(self_inner):
                harness.started.set()
                if harness.gate is not None:
                    await harness.gate.wait()
                return SimpleNamespace(status=harness.provider_status)

            async def __aexit__(self_inner, *args):
                return False

        class Session:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *args):
                return False

            def patch(self_inner, url, *, headers, json):
                harness.provider_calls.append(json["bank"])
                return Response()

        monkeypatch.setattr(corebank.aiohttp, "ClientSession", Session)
        monkeypatch.setattr(corebank, "async_execute", lambda builder, retries=1: _fake_async_execute(pg, builder))
        self.cog = corebank.CoreBankCog(mock.Mock())
        self.cog.config = {"core_channel_id": "100", "bank_channel_id": "200", "unbelievaboat_token": "t",
                           "emoji_map": {"green": {"name": "Green", "value": 100, "display": "G"}}}
        self.officer = SimpleNamespace(id=789, mention="<@789>")
        recipient = SimpleNamespace(id=456, bot=False, mention="<@456>")

        class Reaction:
            emoji = "green"

            async def users(self_inner):
                for user_id in sorted(harness.reactors):
                    yield SimpleNamespace(id=user_id)

        async def fetch_message(message_id):
            reactions = [Reaction()] if harness.reactors else []
            return SimpleNamespace(author=recipient, content="proof", id=message_id, reactions=reactions)

        channel = mock.Mock()
        channel.fetch_message = fetch_message
        channel.send = mock.AsyncMock()
        guild = mock.Mock()
        guild.get_member.return_value = recipient
        self.cog._reaction_context = mock.AsyncMock(return_value=(guild, channel, self.officer))
        self.payload = SimpleNamespace(user_id=789, guild_id=123, channel_id=100, message_id=300,
                                       emoji=SimpleNamespace(id=None, name="green"))
        self.pg = pg

    def ledger(self):
        row = self.pg.conn.execute("SELECT * FROM core_credited WHERE message_id = '300:green'").fetchone()
        return row

    def react(self):
        self.reactors.add(789)

    def unreact(self):
        self.reactors.discard(789)


def _run(coro):
    return asyncio.run(coro)


def test_core_remove_during_pending_waits_in_order_then_refunds(pg, monkeypatch):
    async def scenario():
        h = Harness(pg, monkeypatch)
        h.react()
        h.gate = asyncio.Event()
        credit = asyncio.create_task(h.cog.on_raw_reaction_add(h.payload))
        await h.started.wait()
        assert h.ledger()["status"] == "pending"
        h.unreact()
        remove = asyncio.create_task(h.cog.on_raw_reaction_remove(h.payload))
        await asyncio.sleep(0.05)
        assert h.provider_calls == [100]  # the remove event is queued behind the in-flight credit
        h.gate.set()
        await asyncio.gather(credit, remove)
        return h

    h = _run(scenario())
    assert h.provider_calls == [100, -100]
    assert h.ledger()["status"] == "reverted"


def test_core_remove_event_before_claim_never_pays_and_later_readd_pays(pg, monkeypatch):
    async def scenario():
        h = Harness(pg, monkeypatch)
        # remove already happened (nothing to refund) but the delayed add event is processed now
        await h.cog.on_raw_reaction_remove(h.payload)
        await h.cog.on_raw_reaction_add(h.payload)
        assert h.provider_calls == []
        assert h.ledger() is None  # no reaction at claim time: no ledger row at all
        h.react()
        await h.cog.on_raw_reaction_add(h.payload)
        return h

    h = _run(scenario())
    assert h.provider_calls == [100]
    assert h.ledger()["status"] == "credited"


def test_core_readd_after_reverted_pays_again_with_cas(pg, monkeypatch):
    async def scenario():
        h = Harness(pg, monkeypatch)
        h.react()
        await h.cog.on_raw_reaction_add(h.payload)
        h.unreact()
        await h.cog.on_raw_reaction_remove(h.payload)
        assert h.ledger()["status"] == "reverted"
        h.react()
        await asyncio.gather(h.cog.on_raw_reaction_add(h.payload), h.cog.on_raw_reaction_add(h.payload))
        return h

    h = _run(scenario())
    assert h.provider_calls == [100, -100, 100]
    assert h.ledger()["status"] == "credited" and h.ledger()["attempt_count"] == 2


def test_core_readd_while_refund_in_flight_is_credited_after_revert(pg, monkeypatch):
    async def scenario():
        h = Harness(pg, monkeypatch)
        h.react()
        await h.cog.on_raw_reaction_add(h.payload)
        h.unreact()
        h.gate = asyncio.Event()
        h.started.clear()
        refund = asyncio.create_task(h.cog.on_raw_reaction_remove(h.payload))
        await h.started.wait()
        assert h.ledger()["status"] == "reverting"
        h.react()
        readd = asyncio.create_task(h.cog.on_raw_reaction_add(h.payload))
        await asyncio.sleep(0.05)
        assert h.provider_calls == [100, -100]
        h.gate.set()
        await asyncio.gather(refund, readd)
        return h

    h = _run(scenario())
    assert h.provider_calls == [100, -100, 100]
    assert h.ledger()["status"] == "credited"


def test_core_ambiguous_provider_result_is_not_retried_or_cleared(pg, monkeypatch):
    async def scenario():
        h = Harness(pg, monkeypatch)
        h.react()
        h.provider_status = 500
        await h.cog.on_raw_reaction_add(h.payload)
        h.provider_status = 200
        await h.cog.on_raw_reaction_add(h.payload)
        h.unreact()
        await h.cog.on_raw_reaction_remove(h.payload)
        return h

    h = _run(scenario())
    assert h.provider_calls == [100]
    assert h.ledger()["status"] == "unknown"


def test_reconcile_script_passes_worker_stopped_acknowledgement(monkeypatch):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import corebank_reconcile

    seen = {}

    def execute(builder, retries=1):
        client = mock.Mock()
        client.rpc.side_effect = lambda name, params: seen.update(params=params) or mock.Mock()
        builder(client)
        return SimpleNamespace(data={"status": "retryable"}), None

    monkeypatch.setattr(corebank_reconcile, "execute", execute)
    args = corebank_reconcile.build_parser().parse_args(
        ["--message-id", "1:g", "--decision", "not_paid", "--actor-id", "9", "--evidence", "e",
         "--worker-stopped"])
    corebank_reconcile.reconcile(args)
    assert seen["params"]["p_worker_quiesced"] is True
    args = corebank_reconcile.build_parser().parse_args(
        ["--message-id", "1:g", "--decision", "not_paid", "--actor-id", "9", "--evidence", "e"])
    corebank_reconcile.reconcile(args)
    assert seen["params"]["p_worker_quiesced"] is False


def test_snapshot_helper_reaches_atomic_rpc(pg):
    sys_path = str(SCRIPTS)
    import sys
    sys.path.insert(0, sys_path)
    from _sp_snapshot import import_sp_snapshot

    result = import_sp_snapshot({"history": {"A": 3, "B": "4"}, "last_update": "2026-01-01 00:00:00"}, pg)
    assert result["imported"] == 2
    with pytest.raises(Exception, match="not empty"):
        import_sp_snapshot({"history": {"C": 1}, "last_update": "2026-01-01 00:00:00"}, pg)


def test_core_flapping_reaction_events_terminate_with_bounded_provider_calls(pg, monkeypatch):
    async def scenario():
        h = Harness(pg, monkeypatch)
        h.react()
        flips = iter([True, False, True, False, True, False, True, False])

        async def flapping(*args):
            return next(flips)  # StopIteration would surface an unbounded loop

        h.cog._reaction_present = flapping
        await h.cog.on_raw_reaction_add(h.payload)
        return h

    h = _run(scenario())
    assert h.provider_calls == [100, -100]
    assert h.ledger()["status"] == "reverted"


def test_core_triple_flip_during_pending_converges_with_reaction_present(pg, monkeypatch):
    async def scenario():
        h = Harness(pg, monkeypatch)
        h.react()
        h.gate = asyncio.Event()
        e1 = asyncio.create_task(h.cog.on_raw_reaction_add(h.payload))
        await h.started.wait()
        h.unreact()
        e2 = asyncio.create_task(h.cog.on_raw_reaction_remove(h.payload))
        h.react()
        e3 = asyncio.create_task(h.cog.on_raw_reaction_add(h.payload))
        await asyncio.sleep(0.05)
        h.gate.set()
        await asyncio.gather(e1, e2, e3)
        return h

    h = _run(scenario())
    assert 789 in h.reactors
    assert h.ledger()["status"] == "credited"
    assert sum(h.provider_calls) == 100


def test_core_triple_flip_during_refund_converges_in_both_end_states(pg, monkeypatch):
    async def scenario(end_present):
        h = Harness(pg, monkeypatch)
        h.react()
        await h.cog.on_raw_reaction_add(h.payload)
        h.unreact()
        h.gate = asyncio.Event()
        h.started.clear()
        e1 = asyncio.create_task(h.cog.on_raw_reaction_remove(h.payload))
        await h.started.wait()
        assert h.ledger()["status"] == "reverting"
        h.react()
        e2 = asyncio.create_task(h.cog.on_raw_reaction_add(h.payload))
        if end_present:
            h.unreact()
            e3 = asyncio.create_task(h.cog.on_raw_reaction_remove(h.payload))
            h.react()
            e4 = asyncio.create_task(h.cog.on_raw_reaction_add(h.payload))
            tasks = (e1, e2, e3, e4)
        else:
            h.unreact()
            tasks = (e1, e2, asyncio.create_task(h.cog.on_raw_reaction_remove(h.payload)))
        await asyncio.sleep(0.05)
        h.gate.set()
        await asyncio.gather(*tasks)
        return h

    present = _run(scenario(True))
    assert 789 in present.reactors and present.ledger()["status"] == "credited"
    assert sum(present.provider_calls) == 100
    pg.conn.execute("DELETE FROM core_credited")
    absent = _run(scenario(False))
    assert 789 not in absent.reactors and absent.ledger()["status"] == "reverted"
    assert sum(absent.provider_calls) == 0
