"""Run upstream migrations in the dedicated local acceptance database.

Avoid Alembic's locale-based INI decoding on Chinese Windows. Execute the
unchanged upstream migrations through Alembic's public Python API.
"""
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config

root = Path(__file__).resolve().parents[1]
url = urlsplit(os.environ.get("DATABASE_URL", ""))
if (url.hostname, url.port, url.path) != ("127.0.0.1", 7311, "/retouch"):
    raise SystemExit("Expected the dedicated local acceptance database")

logging.basicConfig(level=logging.INFO)
config = Config()
config.set_main_option("path_separator", "os")
config.set_main_option("prepend_sys_path", str(root / "integrations/ai-retouch-agent/backend"))
config.set_main_option("script_location", str(root / "integrations/ai-retouch-agent/backend/migrations"))
command.upgrade(config, "head")
print("UPSTREAM_MIGRATIONS_OK")
