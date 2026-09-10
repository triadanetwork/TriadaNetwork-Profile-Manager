# GitHub publication checklist

Before making the repository public:

## 1. Replace project links

Replace:

```text
YOUR_GITHUB_USERNAME
```

with the actual GitHub owner in:

- `.github/ISSUE_TEMPLATE/config.yml`
- `docs/roadmap.md`
- any repository badges/links you add later.

## 2. Add your community links

Replace the placeholders in `README.md` and `README.ru.md`:

```text
YOUR_TELEGRAM_USERNAME
YOUR_INSTAGRAM_USERNAME
```

## 3. Add donation addresses

Replace:

```text
YOUR_USDT_TRC20_ADDRESS
YOUR_BTC_ADDRESS
YOUR_ETH_ADDRESS
```

Do not add seed phrases, private keys or screenshots containing wallet secrets.

Verify each donation address on the correct network before publishing.

## 4. Check repository state

Run:

```bash
git status
git ls-files
```

Confirm that no personal databases, profiles, browser storage, cookies, backups, logs, local credentials or `.env` files are tracked.

## 5. Run the release gates

```bash
uv run python scripts/qa/release_gate.py
uv run pytest -q -m "not browser"

cd web
npm ci
npm run lint
npm run typecheck
npm run build:static
```

For the Windows release, build `TriadaNetwork.exe` and test the installer on a clean machine.

## 6. Review licenses

Keep `LICENSE` and `NOTICE.md`. Preserve applicable third-party notices when distributing bundled components.
