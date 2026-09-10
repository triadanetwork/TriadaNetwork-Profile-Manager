# UI E2E tests

This directory is reserved for Playwright tests. Keep UI E2E separate from
Python integration tests so a release can distinguish local API correctness
from browser-level UX validation.

When `@playwright/test` is added to the project, the intended commands are:

```powershell
npx playwright install --with-deps chromium
npx playwright test
```
