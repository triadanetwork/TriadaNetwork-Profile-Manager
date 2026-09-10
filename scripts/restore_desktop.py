from __future__ import annotations

import argparse
from triada_desktop.backup import restore_backup

parser = argparse.ArgumentParser()
parser.add_argument("backup")
parser.add_argument("--include-browser-data", action="store_true")
args = parser.parse_args()
restore_backup(args.backup, include_browser_data=args.include_browser_data)
print("Restore complete")
