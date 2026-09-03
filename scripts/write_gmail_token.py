"""Write `gmail_token.json` from a secure environment variable.

Usage:
 - Set `GMAIL_TOKEN_JSON` to the raw JSON token content, or
 - Set `GMAIL_TOKEN_JSON_B64` to the base64-encoded JSON content.

Example (Render start command):
  python scripts/write_gmail_token.py && python run.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path


def main() -> int:
    out_path = Path(__file__).resolve().parents[1] / "gmail_token.json"

    raw = os.environ.get("GMAIL_TOKEN_JSON")
    b64 = os.environ.get("GMAIL_TOKEN_JSON_B64")

    if not raw and not b64:
        print("No GMAIL_TOKEN_JSON or GMAIL_TOKEN_JSON_B64 found in environment; skipping write.")
        return 0

    if b64 and not raw:
        try:
            raw = base64.b64decode(b64).decode("utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Failed to decode GMAIL_TOKEN_JSON_B64: {exc}")
            return 2

    # Validate it's JSON.
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        print(f"GMAIL token content is not valid JSON: {exc}")
        return 3

    try:
        # Ensure parent exists
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically
        tmp = out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
        # set file mode to user-only where possible
        try:
            tmp.chmod(0o600)
        except Exception:
            pass
        tmp.replace(out_path)
        print(f"Wrote gmail token to {out_path}")
    except Exception as exc:  # pragma: no cover - IO errors environment-dependent
        print(f"Failed to write gmail token file: {exc}")
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
