## Bot Dofus Unity ( Dofus 3 ) : Farming / Fight / HDV / Craft

Windows bot for Dofus Unity with harvesting, combat, crafting, multiple accounts,
and session scheduling. Built with Python, PyQt6, and FluentWidgets.

[Download for Windows](https://github.com/Valentin-alix/BillBot/releases/latest)

![Bill running alongside Dofus Unity](./resources/screenshots/bot.gif)

## Features

- Harvesting, automatic combat, crafting, and marketplace sales.
- Character, inventory, bank, map, and route monitoring.
- Account schedules, email accounts, and proxy management.
- Activity logs, quarantined item controls, and protocol inspection.
- **Socket** mode: connects directly to the game servers without the game client.
- **MITM** mode: intercepts traffic between the Dofus Unity client and the servers.

## Getting started

### Download

Extract the Windows archive from the [latest release](https://github.com/Valentin-alix/BillBot/releases/latest)
and run `BillBot.exe`.

### From source

Requirements: **Windows**, **Python 3.12**, **Git LFS**, and **uv**.
Clone the repository and run these commands from its root in PowerShell:

```powershell
git lfs install
git lfs pull
uv sync
uv run playwright install chromium
Copy-Item .env.example .env
uv run python __main__.py
```

Copy `.env.example` only on first installation; keep any existing `.env`.
MITM mode requires Dofus Unity installed through the Ankama launcher.
Cytrus is optional and handles automatic updates.

### Configuration

In **Settings**, choose behaviors, define schedules, and assign accounts to profiles.
Start an activity from the account controls and use **Activity** to review errors.
Behavior changes apply on the next bot start; account automation settings apply
at the next operation.

## Development

- `src/`: bot and interface.
- `AnkamaLauncherEmulator/`: interactions with Ankama services.
- `DBDofusUnity/`: protocol mapper and Unity game-data reader.
- `scripts/`: packaging, launcher, maintenance, mapping, and data tools.

Run tools from the repository root. The **Debug** view provides message inspection
and searchable logs; start the standalone sniffer with
`uv run python -m scripts.mapping.sniffer`.
Each new Dofus build requires regenerating and verifying the protocol mapping.

### Build data tools

Before using the Unity static-data tools, install **.NET 10** and
**Visual Studio C++ build tools (v145)**, then run from the repository root
in **Git Bash on Windows**:

```bash
bash scripts/packaging/build-tools.sh
```

This builds UABEA, Il2CppInspector, and protodec.

### Checks

```powershell
uv run ruff check .
uv run pyright
uv run pytest tests
```

Run `uv run poe verify` for the final check; it also applies Ruff fixes.
