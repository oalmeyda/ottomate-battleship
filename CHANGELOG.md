# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-11-11

### Changed
- **Runtime Upgrade to Python 3.15 (`Dockerfile`, `.github/workflows/ci.yml`, `pyproject.toml`)**:
  - Upgraded runtime to Python 3.15 (`FROM python:3.15-slim` in container and `requires-python = ">=3.15"`).
  - Synchronized Copier repository templates with `python_version: '3.15'` from `ottomate-core` v1.29.3.
- **Vendored Core Dependency (`wheels/`)**:
  - Upgraded vendored wheel to `ottomate_core-1.29.3-py3-none-any.whl` (`ottomate-core>=1.29.3,<1.30`) with recursive MutationObserver freeze protection.
- **Cache-Busting Static Assets (`index.html`)**:
  - Aligned static asset query parameters to `?v=0.1.6`.

## [0.1.5] - 2026-11-10

### Fixed
- **Hub Pending Action Cleanup (`app/api/battleship_router.py`)**:
  - Wired `clear_turn_pending_action("battleship", match_id)` upon match deletion to prevent ghost turn entries in the Hub.
- **Canonical Service URL Resolution & Logging (`app/api/battleship_router.py`)**:
  - Retrieved canonical URL dynamically from service configuration metadata (`SERVICE_CARD_METADATA`) and added exception logging on Hub synchronization failures.

### Changed
- **Consolidated API Client (`app/static/js/battleship.js`)**:
  - Eliminated custom fallback `apiFetch` logic in favor of unified `window.Ottomate.api()`.
- **Upgraded Core Dependency**: Bumped to `ottomate-core>=1.29.0,<1.30` vendoring wheel `1.29.0` with synthesized audio mute toggle (`Ottomate.audio`), daily challenge seed isolation, and error detail preservation.
- **Cache-Busting Asset Alignment (`index.html`)**: Aligned static asset query parameters to `?v=0.1.5`.

## [0.1.4] - 2026-11-10

### Added
- **Core Grid Engine Integration (`app/services/battleship_engine.py`)**:
  - Delegated 2D coordinate parsing (`parse_coordinate`) and formatting (`format_coordinate`) to `ottomate_core.grid_engine`.
- **Synthesized Web Audio Engine (`app/static/js/battleship.js`, `index.html`)**:
  - Loaded `/core-static/js/ottomate-audio.js`.
  - Wired interactive audio effects for ocean clicks, ship hits/explosions, and victory fanfare.
- **Hub Turn Action Center Synchronization (`app/api/battleship_router.py`)**:
  - Wired `sync_turn_pending_action` and `clear_turn_pending_action` for PvP match turns and match completions.
- **People Modal Auto-Binding (`app/static/js/battleship.js`)**:
  - Initialized `window.Ottomate.people.init({ appName: "Ottomate Battleship" })` and wired profile/directory modal delegates.
- **Shared API Helper**:
  - Delegated `fetch` requests to `window.Ottomate.api()`.

### Changed
- **Upgraded Core Dependency**: Bumped to `ottomate-core>=1.28.4` with automated cache-buster query verification.
- **Cache-Busting Asset Alignment (`index.html`)**: Aligned all static asset query parameters to `?v=0.1.4`.

## [0.1.3] - 2026-11-09

### Fixed
- **Header Auth State & Other Auth Suppression**:
  - Integrated `Ottomate.updateProfilePill(user)` and `Ottomate.toggleAuthButtons(true/false)` to automatically hide competing sign-in buttons (Email link, Google) once logged in.
  - Upgraded to `ottomate-core>=1.28.1` with hardened multi-provider auth button suppression and MutationObserver profile pill listener.

## [0.1.2] - 2026-11-09

### Fixed
- **Mobile Responsive Layout & Grid Overflow**:
  - Eliminated horizontal over-running and viewport blowout on mobile devices ($\le 600\text{px}$) by enforcing `overflow-x: hidden` and `box-sizing: border-box`.
  - Added wrapping to `.grid-fleet-row`, `.fleet-health-bar`, and `.grid-header-row` so ship health badges stack gracefully instead of pushing the card past the screen edge.
  - Scaled tactical ocean grids responsively on mobile screens down to 24px/28px per cell with compact padding and font sizing.

## [0.1.1] - 2026-11-09

### Added
- Auto-sync `SERVICE_CARD_METADATA` to Firestore `services` registry upon application startup for Ottomate Hub dynamic discovery.

## [0.1.0] - 2026-11-09

### Added
- Initial project scaffolding for `ottomate-battleship`.
- Classic 10x10 naval tactical grid engine (Carrier, Battleship, Cruiser, Submarine, Destroyer).
- Two-phase gameplay: Fleet deployment and turn-based battle with "streak on hit" firing rules.
- Strict anti-cheating server-side fog-of-war masking.
- PvP human matchmaking and PvE AI bot opponent (Easy, Medium, Hard).
- 3-tier RBAC authorization, proxy delegation, and multi-database Firestore isolation (`battleship` and `(default)`).
- Responsive tactical radar frontend with dual-grid view and short-polling live updates.
- Scoped leaderboards and command record statistics (Overall vs. Humans Only), tracking record, win %, hit accuracy, ships sunk/lost, hit/miss streaks, win streaks, and flawless victories.
- Dynamic rematch flow for match participants and game administrators.
- Stabilized two-row tactical board card headers isolating streak and strike badges from fixed fleet ship indicators.
- Bot targeting aiming crosshair, hit impact flash, and human-paced delays.
- Full deployment to Google Cloud Platform on Cloud Run (`https://ottomate-battleship.web.app`).

