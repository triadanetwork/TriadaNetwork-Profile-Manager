from __future__ import annotations

import argparse
from triada_desktop.backup import create_backup

parser = argparse.ArgumentParser()
parser.add_argument("--include-browser-data", action="store_true")
args = parser.parse_args()
print(create_backup(include_browser_data=args.include_browser_data))
