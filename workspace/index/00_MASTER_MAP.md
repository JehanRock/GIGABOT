# GigaBOT Universal Index

This directory serves as the central "Brain" for the GigaBOT AI Agent. It contains a comprehensive index of all system components, functions, architectures, and debugging protocols.

## 📂 Index Structure

| File | Description |
| :--- | :--- |
| **[01_ARCHITECTURE.md](./01_ARCHITECTURE.md)** | High-level system design, Swarm architecture, and Event Bus. |
| **[02_CORE_FUNCTIONS.md](./02_CORE_FUNCTIONS.md)** | Catalog of Python backend functions, classes, and services. |
| **[03_UI_COMPONENTS.md](./03_UI_COMPONENTS.md)** | Catalog of React frontend components, hooks, and stores. |
| **[04_SCRIPTS_CLI.md](./04_SCRIPTS_CLI.md)** | Documentation for CLI commands, Cron jobs, and utility scripts. |
| **[05_DATA_MODELS.md](./05_DATA_MODELS.md)** | Database schemas, Configuration structures, and Type definitions. |
| **[06_DEBUG_LOG.md](./06_DEBUG_LOG.md)** | **Debug Sub-agent Protocols**, Known Issues, and Fix Logs. |

## 🚀 Quick Links

- **Main Entry Point:** `nanobot/__main__.py`
- **API Server:** `nanobot/ui/server.py`
- **Frontend App:** `nanobot/ui/dashboard/src/App.tsx`
- **Config File:** `config/config.json`
- **Swarm Orchestrator:** `nanobot/swarm/orchestrator.py`

## 🤖 AI Agent Instructions

1.  **Read First:** Always check this `00_MASTER_MAP.md` to locate the relevant documentation for your task.
2.  **Update Often:** When adding new features or files, update the corresponding Index file immediately.
3.  **Debug Protocol:** If an error occurs, consult `06_DEBUG_LOG.md` for the "Lightning" Debug Sub-agent workflow.
