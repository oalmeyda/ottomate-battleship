# Ottomate Battleship (`ottomate-battleship`)

[![CI](https://github.com/oalmeyda/ottomate-battleship/actions/workflows/ci.yml/badge.svg)](https://github.com/oalmeyda/ottomate-battleship/actions)
[![Release](https://img.shields.io/github/v/release/ottomate-battleship?color=green)](https://github.com/oalmeyda/ottomate-battleship/releases)

Ottomate Battleship is a classic 1v1 turn-based naval strategy game in the Ottomate gaming ecosystem. Players deploy their fleet across a 10x10 tactical ocean grid and take turns firing artillery strikes. A hit grants a bonus shot ("streak on hit"), while a miss ends the turn. The first player to sink all 5 opponent ships claims victory.

---

## 🎮 Gameplay Features

- **Standard Naval Fleet**: 5 ships (Carrier: 5, Battleship: 4, Cruiser: 3, Submarine: 3, Destroyer: 2).
- **Streak on Hit**: Successfully hitting an enemy vessel allows you to fire again; missing surrenders the turn to the opponent.
- **Server-Side Fog of War**: Opponent ship positions are strictly masked on the server until hit or completely destroyed, preventing network inspection cheating.
- **PvP & PvE Modes**: Challenge other players via private match invites or practice solo against AI Bot commanders (Easy, Medium, Hard).
- **3-Tier RBAC & Proxy Delegation**: Built upon `ottomate-core`'s 3-tier access control and proxy play capabilities.
- **Responsive Tactical UI**: Dual-grid layout featuring "Your Fleet" and "Target Radar", drag-and-drop or 1-click randomized fleet deployment, and scale-to-zero short polling.

---

## 🚀 Quickstart & Development

### 1. Local Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

# Install vendored ottomate-core wheel and development dependencies:
pip install --find-links wheels -e ".[dev]"
```

### 2. Running Unit Tests & Ruff Linter

```bash
ruff check .
pytest -v
```

### 3. Running the Local Dev Server

```bash
DEV_MODE=1 uvicorn app.main:app --reload --port 8080
```

Navigate to `http://localhost:8080` to play.

