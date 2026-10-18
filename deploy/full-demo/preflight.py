"""Check a future server's deployment env without displaying any secret values."""
import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values


def validate(values):
    errors = []
    for key in ("SITE_HOST", "OBJECTS_HOST", "ACME_EMAIL", "DEMO_USER", "DEMO_PASSWORD_HASH", "POSTGRES_PASSWORD", "MINIO_USER", "MINIO_PASSWORD", "RETOUCH_JWT_SECRET", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"):
        value = values.get(key) or ""
        if not value or "REPLACE" in value or "example.com" in value:
            errors.append(f"{key}: required real server value missing")
    for key in ("SITE_HOST", "OBJECTS_HOST"):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", values.get(key) or ""):
            errors.append(f"{key}: enter a DNS host, without scheme, port or path")
    if values.get("SITE_HOST") == values.get("OBJECTS_HOST"):
        errors.append("SITE_HOST and OBJECTS_HOST must differ")
    for key in ("POSTGRES_PASSWORD", "MINIO_PASSWORD", "RETOUCH_JWT_SECRET"):
        if not re.fullmatch(r"[0-9a-fA-F]{64,}", values.get(key) or ""):
            errors.append(f"{key}: use independent 64+ character random hex")
    if not re.fullmatch(r"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}", values.get("DEMO_PASSWORD_HASH") or ""):
        errors.append("DEMO_PASSWORD_HASH: generate a bcrypt hash using caddy hash-password")
    try:
        if not 1 <= int(values.get("DEMO_DAILY_POST_LIMIT") or "60") <= 1000:
            raise ValueError
    except ValueError:
        errors.append("DEMO_DAILY_POST_LIMIT: expected 1..1000")
    if urlsplit(values.get("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com").scheme != "https":
        errors.append("DASHSCOPE_BASE_URL: HTTPS required")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(__file__).with_name(".env"))
    args = parser.parse_args()
    if not args.env_file.is_file():
        parser.exit(2, "Deployment env file not found. Copy env.example on the future server.\n")
    errors = validate(dotenv_values(args.env_file, interpolate=False))
    for error in errors:
        print(error)
    if not errors:
        print("PASS: deployment fields validated; values hidden. DNS, provider balance and network access still require live checks.")
    raise SystemExit(1 if errors else 0)
