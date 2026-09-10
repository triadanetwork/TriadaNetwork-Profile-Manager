# Triada Network

**Открытая desktop-платформа для управления браузерной инфраструктурой, профилями, прокси и рабочими пространствами команд.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![Status](https://img.shields.io/badge/Status-Release%20Candidate-orange.svg)](docs/qa/RELEASE_CANDIDATE_V2.3.md)


Triada Network — self-hosted платформа управления браузерной инфраструктурой на базе [Camoufox](https://github.com/daijro/camoufox). Проект объединяет долгоживущие браузерные профили, сохранение конфигурации fingerprint, управление прокси, browser sessions, Team/RBAC, аудит, локальную защиту данных, cloud control plane и полноценную Windows desktop-оболочку.

Основная идея — дать пользователю контроль над изолированными браузерными окружениями и операционной инфраструктурой без обязательной передачи локальных профилей стороннему SaaS.

## Основные возможности

### Профили

Каждый профиль — отдельное долговременное браузерное окружение со своим локальным storage и конфигурацией.

- Создание, редактирование, клонирование и удаление.
- Корзина с восстановлением и безвозвратным удалением.
- Поиск, фильтры, теги, группы и массовые операции.
- Назначение владельца и buyer в Team workspace.
- Локальный импорт и экспорт совместимых profile data.

### Fingerprint и Browser Runtime

Camoufox используется как browser engine, а Triada Network управляет окружающей профильной и операционной инфраструктурой.

- Установка и просмотр доступных browser runtime.
- Выбор активной версии.
- Удаление неактивной версии.
- Независимое версионирование приложения и browser runtime.
- Запуск и управление browser sessions.

### Proxy Manager

Прокси представлены как отдельный inventory.

- Proxy inventory.
- Proxy pools.
- HTTP / HTTPS / SOCKS.
- Provider, country, type.
- Health checks.
- Exit IP, география и latency.
- Назначение proxy профилям.
- Массовый импорт.
- Выбор proxy из pool.

Учетные данные proxy считаются чувствительными и не возвращаются обычными API-ответами.

### Browser Session Manager

Desktop-слой работает не только с UI-состоянием, но и с реальными процессами ОС.

- PID и uptime.
- `running / stopped / crashed / orphaned`.
- Restart и force-close.
- Reconcile активных sessions.
- Supervisor и recovery primitives.

### Team / RBAC

Одна модель поддерживает и **solo buyer**, и команды.

Роли:

```text
Owner
Admin
Team Lead
Buyer
Viewer
```

Personal workspace не перегружает интерфейс командными функциями. Team workspace добавляет ownership, assignment, permissions и аудит.

### Activity / Audit

Операции могут фиксироваться с actor, action, entity, entity ID, timestamp и metadata.

### Cloud Control Plane

Cloud-слой обеспечивает foundation для:

- аккаунтов;
- нескольких workspace;
- участников;
- scoped API keys;
- устройств;
- синхронизации профильной metadata;
- revision-based conflict detection.

Cookies, browser storage, raw fingerprint material и proxy credentials не входят в обычную metadata sync-модель.

### Desktop Security & Data

Есть:

- Windows DPAPI;
- локальное хранилище секретов;
- encrypted cookie/session bundles;
- backup/restore;
- backup integrity;
- orphan detection и quarantine;
- migrations;
- recovery/rollback;
- diagnostics.

Сессионные экспорты следует считать учетными данными и хранить как чувствительные данные.

## Запуск

### Backend

```powershell
uv sync
uv run triada-network --no-browser
```

API:

```text
http://localhost:8000
```

### Frontend

```powershell
cd web
npm ci
npm run dev
```

UI:

```text
http://localhost:3000
```

### Windows Desktop

```powershell
uv sync --extra desktop --extra build
uv run python scripts/build_desktop.py
```

Результат:

```text
dist\TriadaNetwork\TriadaNetwork.exe
```

## Структура проекта

```text
src/camoufox_pm/      Core, API, profiles и browser management
src/triada_desktop/    Desktop shell и local runtime
web/                   Next.js UI
cloud_control_plane/   Cloud service
tests/                 Unit, integration, QA и browser tests
docs/                  API, architecture, QA и release docs
ops/                   Deployment и observability
packaging/             PyInstaller и Inno Setup
scripts/               Build, backup, migration и release tools
extras/                Дополнительные интеграции
```

## Статус

`2.3.0-rc.1` — **Release Candidate**. Это не заявление о сертифицированной production-ready эксплуатации.

Перед public release должны пройти backend QA, frontend typecheck/build, Windows build, clean-machine installation, upgrade/uninstall, backup/restore и browser lifecycle tests.

Подробнее: [RELEASE_CANDIDATE_V2.3.md](docs/qa/RELEASE_CANDIDATE_V2.3.md).

## Поддержать проект

Если Triada Network полезен тебе, развитие проекта можно поддержать криптовалютой.

### USDT — TRC20

```text
TKjUobpMSR23Vwpw6nTHpRFFR7C5yZN7RB
```

### BTC

```text
bc1qd0nekagryuwqsd2vfmw2qlk5nx4ycy30693lse
```

### ETH

```text
0x4aF1Bd629eCAAe494da0503D1b2ef05Dd6622046
```

> 

## Социальные сети

### Telegram

```text
https://t.me/+ny3V6yCzdkFjZGI1
```

### Instagram

```text
https://www.instagram.com/triada.network
```

Перед публикацией замени placeholder-ссылки на официальные аккаунты проекта.

## Third-party software

Triada Network использует open-source компоненты, включая:

- [Camoufox](https://github.com/daijro/camoufox)
- [FastAPI](https://github.com/fastapi/fastapi)
- [Next.js](https://github.com/vercel/next.js)
- [Playwright](https://github.com/microsoft/playwright)
- [pywebview](https://github.com/r0x0r/pywebview)
- [PyInstaller](https://github.com/pyinstaller/pyinstaller)

Смотри [LICENSE](LICENSE) и [NOTICE.md](NOTICE.md).

## Security

Не публикуй:

- пароли;
- API keys;
- proxy credentials;
- cookies;
- session bundles;
- локальную базу;
- profile data;
- backup archives.

Подробнее: [SECURITY.md](SECURITY.md).

## Лицензия

Код проекта распространяется под MIT License с учетом лицензий и notices сторонних компонентов.

---

**Triada Network — контроль над собственной browser infrastructure без непрозрачной SaaS-обертки.**
