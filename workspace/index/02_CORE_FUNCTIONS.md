# Core Functions & Backend Catalog

This file indexes the key Python functions and classes in the `nanobot` package.

## 📦 Modules

### `nanobot.agent`
Core agent logic and tool management.
-   `compaction.py`: Context window management.
-   `context.py`: Session context handling.
-   `loop.py`: Main agent execution loop.
-   `tools/`: Directory of available tools (Browser, Shell, FileSystem, etc.).

### `nanobot.ui`
API and Server interface.
-   `server.py`: FastAPI application entry point.
-   `api.py`: API route definitions.

### `nanobot.nodes`
Distributed node management.
-   `manager.py`: Node lifecycle.
-   `router.py`: Request routing between nodes.

### `nanobot.skills`
Skill loading and management.
-   `skill-creator`: Tools for generating new skills.
-   `github`: GitHub integration.

### `nanobot.cron`
Scheduled task management.
-   `service.py`: Cron execution service.

### `nanobot.hooks`
Event hooks and triggers.
-   `service.py`: Hook registration and execution.

### `nanobot.security`
Security and permissions.
-   `auth.py`: Authentication logic.
-   `policy.py`: Access control policies.
-   `sandbox.py`: Execution sandboxing.

## 🛠️ Key Classes

| Class | File | Description |
| :--- | :--- | :--- |
| `SwarmOrchestrator` | `nanobot/swarm/orchestrator.py` | Manages agent delegation and task flow. |
| `ChannelManager` | `nanobot/channels/manager.py` | Controls lifecycle of all communication channels. |
| `MemoryStore` | `nanobot/memory/store.py` | Interface for persistent storage operations. |
| `APIServer` | `nanobot/ui/server.py` | The main FastAPI server instance. |
