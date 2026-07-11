#!/usr/bin/env python3
"""
Ensure Aether market data lives on LaCie (primary store).

- Verifies LaCie is mounted
- Re-syncs any SSD backup trees → LaCie (never deletes source)
- Confirms data/fmp and data/databento symlinks point at LaCie
- Refuses if LaCie missing (so we don't silently fill the Mac)

Safe to re-run anytime. Does not delete paid data.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LACIE_ROOT = Path("/Volumes/LaCie/Aether")
LACIE_RAW = LACIE_ROOT / "data" / "raw"
DATA = ROOT / "data"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def main() -> int:
    print("=" * 60, flush=True)
    print("ENSURE LACIE SYNC", datetime.now(timezone.utc).isoformat(), flush=True)
    print("=" * 60, flush=True)

    if not LACIE_ROOT.exists():
        print("FAIL: LaCie not mounted at /Volumes/LaCie/Aether", flush=True)
        print("Mount the drive before any download/sync.", flush=True)
        return 2

    for sub in ("fmp", "databento", "PROTECT_DO_NOT_DELETE"):
        (LACIE_RAW / sub).mkdir(parents=True, exist_ok=True)

    # Symlinks for project data/ pointers
    DATA.mkdir(parents=True, exist_ok=True)
    for name, target in [
        ("fmp", LACIE_RAW / "fmp"),
        ("databento", LACIE_RAW / "databento"),
    ]:
        link = DATA / name
        target.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            if link.resolve() != target.resolve():
                link.unlink()
                link.symlink_to(target)
                print(f"fixed symlink data/{name} -> {target}", flush=True)
            else:
                print(f"ok symlink data/{name} -> {target}", flush=True)
        elif link.exists() and link.is_dir():
            backup = DATA / f"{name}_ssd_backup_KEEP"
            if not backup.exists():
                link.rename(backup)
                print(f"moved {link} -> {backup}", flush=True)
            else:
                run(
                    [
                        "rsync",
                        "-a",
                        "--exclude",
                        "._*",
                        f"{link}/",
                        f"{backup}/",
                    ]
                )
                # do not rm -rf here; leave for manual if needed
                print(f"WARN: {link} still a dir; backup exists at {backup}", flush=True)
            if not link.exists():
                link.symlink_to(target)
                print(f"created symlink data/{name} -> {target}", flush=True)
        else:
            link.symlink_to(target)
            print(f"created symlink data/{name} -> {target}", flush=True)

    # Sync SSD backups onto LaCie (never --delete)
    pairs = [
        (DATA / "fmp_ssd_backup_KEEP", LACIE_RAW / "fmp" / "ssd_rescue_20260710"),
        (
            DATA / "aether-data" / "databento_ssd_backup_KEEP",
            LACIE_RAW / "databento" / "ssd_rescue_20260710",
        ),
    ]
    for src, dst in pairs:
        if src.exists() and src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            run(
                [
                    "rsync",
                    "-a",
                    "--exclude",
                    "._*",
                    "--exclude",
                    ".DS_Store",
                    f"{src}/",
                    f"{dst}/",
                ]
            )
            print(f"synced {src} -> {dst}", flush=True)
        else:
            print(f"skip missing backup {src}", flush=True)

    # Also merge SSD fmp backup into primary fmp without clobbering
    fmp_bak = DATA / "fmp_ssd_backup_KEEP"
    if fmp_bak.exists():
        run(
            [
                "rsync",
                "-a",
                "--ignore-existing",
                "--exclude",
                "._*",
                f"{fmp_bak}/",
                f"{LACIE_RAW / 'fmp'}/",
            ]
        )

    # Inventory sizes
    for label, path in [
        ("fmp", LACIE_RAW / "fmp"),
        ("databento", LACIE_RAW / "databento"),
    ]:
        if path.exists():
            out = subprocess.check_output(["du", "-sh", str(path)], text=True).split()[0]
            print(f"LaCie {label}: {out}", flush=True)

    eod = LACIE_RAW / "fmp" / "archive_expiry" / "eod_bulk"
    if eod.exists():
        n = sum(
            1
            for p in eod.glob("*.csv")
            if not p.name.startswith("._") and p.stat().st_size > 1000
        )
        print(f"eod_bulk files on LaCie: {n}", flush=True)

    # Write stamp
    stamp = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "fmp_link": str((DATA / "fmp").resolve()) if (DATA / "fmp").exists() else None,
        "databento_link": str((DATA / "databento").resolve())
        if (DATA / "databento").exists()
        else None,
    }
    import json

    (LACIE_RAW / "PROTECT_DO_NOT_DELETE").mkdir(parents=True, exist_ok=True)
    (LACIE_RAW / "PROTECT_DO_NOT_DELETE" / "last_sync.json").write_text(
        json.dumps(stamp, indent=2)
    )
    print("DONE — primary store is LaCie", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
