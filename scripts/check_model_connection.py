"""One small, real model request. Never print credentials or raw error bodies."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent_code"))

import anthropic
from photo_runtime import create_anthropic_client, resolve_anthropic_client_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = resolve_anthropic_client_settings()
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": settings["provider"], "requested_model": settings["model"],
        "base_url": settings["base_url"], "max_output_tokens": 64, "success": False,
    }
    start = time.perf_counter()
    try:
        if settings["provider"] != "deepseek":
            raise ValueError("This check requires PHOTO_MODEL_PROVIDER=deepseek.")
        with create_anthropic_client(source_cli="check_model_connection.py") as client:
            response = client.with_options(timeout=30.0, max_retries=0).messages.create(
                model=settings["model"], max_tokens=64, thinking={"type": "disabled"},
                messages=[{"role": "user", "content": "Reply with exactly: DEEPSEEK_OK"}],
            )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        result.update(success=text == "DEEPSEEK_OK", returned_model=response.model,
            response_matches_expected=text == "DEEPSEEK_OK", stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
    except anthropic.APIStatusError as exc:
        result.update(error_type=type(exc).__name__, http_status=exc.status_code)
    except anthropic.APIConnectionError as exc:
        causes = []
        cause = exc.__cause__
        while cause is not None and len(causes) < 5:
            causes.append(type(cause).__name__)
            cause = cause.__cause__
        result.update(error_type=type(exc).__name__, connection_error_types=causes)
    except (ValueError, SystemExit) as exc:
        result.update(error_type=type(exc).__name__)
    result["elapsed_seconds"] = round(time.perf_counter() - start, 3)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
