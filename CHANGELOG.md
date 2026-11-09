# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

