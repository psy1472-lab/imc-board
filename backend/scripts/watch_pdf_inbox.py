"""data/inbox/ PDF를 주기적으로 감시해 자동 처리합니다."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESS_SCRIPT = PROJECT_ROOT / "backend" / "scripts" / "process_pdf_inbox.py"


def run_once(
    inbox: Path,
    upload_production: bool,
    password: str | None,
) -> int:
    cmd = [sys.executable, str(PROCESS_SCRIPT), "--inbox", str(inbox)]
    if upload_production:
        cmd.append("--upload-production")
    if password:
        cmd.extend(["--password", password])
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def watch(
    inbox: Path,
    interval_sec: int,
    upload_production: bool,
    password: str | None,
) -> int:
    inbox.mkdir(parents=True, exist_ok=True)
    print(f"Watching {inbox} every {interval_sec}s (Ctrl+C to stop)")
    try:
        while True:
            pdfs = list(inbox.glob("*.pdf"))
            if pdfs:
                print(f"Found {len(pdfs)} PDF(s), processing...")
                code = run_once(inbox, upload_production, password)
                if code != 0:
                    return code
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch inbox folder for new PDFs")
    parser.add_argument("--inbox", type=Path, default=PROJECT_ROOT / "data" / "inbox")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval seconds")
    parser.add_argument("--upload-production", action="store_true")
    parser.add_argument("--password", default=None)
    parser.add_argument("--once", action="store_true", help="Process once and exit")
    args = parser.parse_args()

    if args.once:
        raise SystemExit(run_once(args.inbox, args.upload_production, args.password))

    raise SystemExit(watch(args.inbox, args.interval, args.upload_production, args.password))


if __name__ == "__main__":
    main()
