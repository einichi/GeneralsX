#!/usr/bin/env python3
"""Read-only inspection of loose skirmish scripts and BIG archive candidates.

Usage: python3 scripts/qa/smoke/inspect-skirmish-assets.py ASSET_ROOT
Reports JSON and exits 1 if a required SCB has no candidate at the root or in
its archives. This is an asset-layout check, not an engine/VFS integration test:
it does not model archive precedence, -mod, external fallback roots, or execute
scripts. Nested loose files are reported but cannot satisfy a root lookup.
"""

import argparse
import json
import struct
import sys
from pathlib import Path


SCRIPT_NAMES = ("SkirmishScripts.scb", "MultiplayerScripts.scb")
TARGETS = {f"data/scripts/{name.lower()}" for name in SCRIPT_NAMES}
TARGETS.add("maps/tournament desert/tournament desert.map")


def read_exact(stream, size):
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("Truncated BIG directory")
    return data


def inspect_archive(path):
    """Read BIG's directory only; never extract or change retail assets."""
    entries = []
    with path.open("rb") as stream:
        header = read_exact(stream, 16)
        if header[:4] not in (b"BIGF", b"BIG4"):
            raise ValueError("Unrecognized BIG header")
        count = struct.unpack_from(">I", header, 8)[0]
        file_size = path.stat().st_size
        if count > file_size // 9:
            raise ValueError("Invalid BIG entry count")
        for _ in range(count):
            offset, size = struct.unpack(">II", read_exact(stream, 8))
            name = bytearray()
            while True:
                char = read_exact(stream, 1)
                if char == b"\0":
                    break
                name.extend(char)
                if len(name) > 4096:
                    raise ValueError("Invalid BIG entry name")
            normalized = name.decode("latin1").replace("\\", "/").lower()
            if normalized in TARGETS:
                if offset + size > file_size:
                    raise ValueError("BIG entry extends beyond archive")
                entries.append({"name": normalized, "bytes": size})
    return entries


def inspect(root):
    report = {"root": str(root), "scripts": [], "archive_candidates": [], "errors": []}
    for name in SCRIPT_NAMES:
        expected = root / "Data" / "Scripts" / name
        report["scripts"].append({
            "name": name,
            "expected_path": str(expected),
            "exists_at_root": expected.is_file(),
            "nested_loose_candidates": sorted(
                str(path.relative_to(root)) for path in root.rglob("*")
                if path.is_file() and path.name.lower() == name.lower() and path != expected
            ),
        })
    archives = sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".big"),
        key=lambda path: str(path).lower(),
    )
    report["archive_count"] = len(archives)
    available = set()
    for path in archives:
        # Match the Zero Hour engine's duplicate INIZH exclusion.
        if str(path).replace("\\", "/").lower().endswith("data/ini/inizh.big"):
            continue
        try:
            entries = inspect_archive(path)
        except (OSError, ValueError) as error:
            report["errors"].append({"archive": str(path), "error": str(error)})
            continue
        if entries:
            report["archive_candidates"].append({"archive": str(path), "entries": entries})
            available.update(entry["name"] for entry in entries)
    for item in report["scripts"]:
        item["candidate_available"] = item["exists_at_root"] or (
            f"data/scripts/{item['name'].lower()}" in available
        )
    report["required_script_candidates_available"] = all(
        item["candidate_available"] for item in report["scripts"]
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_root", type=Path)
    args = parser.parse_args()
    root = args.asset_root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")
    report = inspect(root)
    print(json.dumps(report, indent=2))
    return 0 if report["required_script_candidates_available"] and not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
