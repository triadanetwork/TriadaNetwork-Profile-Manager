#!/usr/bin/env python3
"""Create a minimal signed-update manifest payload from a built installer."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("installer", type=Path)
parser.add_argument("--version", required=True)
parser.add_argument("--channel", choices=("stable", "beta"), default="stable")
parser.add_argument("--download-url", required=True)
args = parser.parse_args()

digest = hashlib.sha256(args.installer.read_bytes()).hexdigest()
manifest = {
    "version": args.version,
    "channel": args.channel,
    "download_url": args.download_url,
    "sha256": digest,
    "installer_args": [],
}
print(json.dumps(manifest, indent=2))
