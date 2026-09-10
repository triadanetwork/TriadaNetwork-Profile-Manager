# Triada Network Web UI

The Triada Network frontend is a Next.js 16 application. FastAPI can serve its static export so the product can also run as a single local process.

## Development

```bash
npm ci
npm run dev
```

By default the development proxy targets:

```text
http://localhost:8000
```

Override it with `API_PROXY_TARGET`:

```bash
API_PROXY_TARGET=http://localhost:8099 npm run dev
```

## Static build

```bash
npm run build:static
```

The build is copied into `src/camoufox_pm/webui/` by:

```bash
python ../scripts/build_webui.py
```

## Structure

```text
src/
  app/
    page.tsx
    groups/
    settings/
    team/
    activity/
    cloud/
    proxy-pools/
    tasks/
    browser-runtime/
    diagnostics/
    backups/
    security/
    updates/
  components/
  lib/api.ts
```

## Design

The interface follows the Triada Network visual system:

- `#000000` — primary canvas
- `#808080` — secondary interface tone
- `#C0C0C0` — primary signal / control tone
- `#FFFFFF` — primary text / high-contrast surface

The frontend uses local/system font stacks and does not depend on `next/font` network loading during build.
