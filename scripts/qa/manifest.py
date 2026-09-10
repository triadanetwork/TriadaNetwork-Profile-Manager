#!/usr/bin/env python3
"""Generate a SHA-256 manifest for a Windows/source release artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    artifact = args.artifact.resolve()
    if not artifact.is_file():
        raise SystemExit(f"artifact not found: {artifact}")
    out = args.output or artifact.with_suffix(artifact.suffix + ".sha256.json")
    payload = {
        "product": "Triada Network",
        "version": args.version,
        "artifact": artifact.name,
        "size": artifact.stat().st_size,
        "sha256": sha256(artifact),
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
