import os
import socket
import sys
from unittest import mock

# Disable dotenv before importing any bot module so a local .env cannot restore credentials.
try:
    import dotenv

    dotenv.load_dotenv = lambda *args, **kwargs: False
except ImportError:
    pass

for name in (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
    "DATABASE_URL",
    "DIRECT_URL",
    "DISCORD_TOKEN",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_API_KEY",
    "GITHUB_GIT_URL",
    "WEBHOOK_SECRET",
    "BOT_WEBHOOK_URL",
    "CHATBOT_WEBHOOK_URL",
):
    os.environ[name] = ""

# Ensure bot/ is importable regardless of pytest's working directory.
BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)


class _NetworkBlockedSocket(socket.socket):
    def connect(self, address):
        raise AssertionError("Outbound network is disabled in bot tests")

    def connect_ex(self, address):
        raise AssertionError("Outbound network is disabled in bot tests")


def pytest_runtest_setup(item):
    """Block accidental outbound sockets in every bot test."""
    item._omp_network_guard = mock.patch.object(socket, "socket", _NetworkBlockedSocket)
    item._omp_network_guard.start()
    item._omp_create_connection_guard = mock.patch(
        "socket.create_connection",
        side_effect=AssertionError("Outbound network is disabled in bot tests"),
    )
    item._omp_create_connection_guard.start()
    item._omp_dns_guard = mock.patch(
        "socket.getaddrinfo",
        side_effect=AssertionError("Outbound DNS is disabled in bot tests"),
    )
    item._omp_dns_guard.start()


def pytest_runtest_teardown(item, nextitem):
    item._omp_network_guard.stop()
    item._omp_create_connection_guard.stop()
    item._omp_dns_guard.stop()
