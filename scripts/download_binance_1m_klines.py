#!/usr/bin/env python3
"""Download Binance monthly 1m kline zip files listed in the source manifest."""

from __future__ import annotations

import csv
import shutil
import sys
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "data" / "minute_price_monthly_sources.csv"
OUT_DIR = ROOT / "data" / "binance_price_change_per-minute" / "raw"
DOWNLOAD_LOG = ROOT / "data" / "binance_price_change_per-minute" / "download_log.csv"


def download(url: str, dest: Path, retries: int = 3) -> tuple[str, str]:
    if dest.exists() and dest.stat().st_size > 0 and zipfile.is_zipfile(dest):
        return "skipped_existing", ""

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": "KN-Lab-binance-data-downloader/1.0"})
            with urlopen(req, timeout=60) as response, tmp.open("wb") as f:
                shutil.copyfileobj(response, f)
            if not zipfile.is_zipfile(tmp):
                tmp.unlink(missing_ok=True)
                return "failed", "downloaded file is not a valid zip"
            tmp.replace(dest)
            return "downloaded", ""
        except HTTPError as exc:
            tmp.unlink(missing_ok=True)
            return "failed", f"HTTP {exc.code}"
        except (TimeoutError, URLError, OSError) as exc:
            last_error = str(exc)
            tmp.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(2 * attempt)
    return "failed", last_error


def main() -> int:
    if not SOURCE_MANIFEST.exists():
        print(f"Missing manifest: {SOURCE_MANIFEST}", file=sys.stderr)
        return 1

    with SOURCE_MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        source_rows = list(csv.DictReader(f))

    log_rows = []
    counts: dict[str, int] = {}
    failures = []

    for idx, row in enumerate(source_rows, start=1):
        coin = row["coin"]
        url = row["source_url"]
        filename = url.rsplit("/", 1)[-1]
        dest = OUT_DIR / coin / filename
        status, error = download(url, dest)
        counts[status] = counts.get(status, 0) + 1
        if status == "failed":
            failures.append((coin, row["year_month"], url, error))
        log_rows.append(
            {
                **row,
                "local_path": str(dest.relative_to(ROOT)),
                "download_status": status,
                "error": error,
            }
        )
        print(f"[{idx:03d}/{len(source_rows):03d}] {status:16s} {coin:5s} {row['year_month']} {filename}")

    DOWNLOAD_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DOWNLOAD_LOG.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(log_rows[0].keys()) if log_rows else ["local_path", "download_status", "error"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    print("Summary:", ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"Download log: {DOWNLOAD_LOG}")
    if failures:
        print("Failures:", file=sys.stderr)
        for coin, year_month, url, error in failures[:20]:
            print(f"- {coin} {year_month}: {error} {url}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
