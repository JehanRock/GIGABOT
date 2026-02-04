# Scripts & CLI Tools

## 💻 CLI Commands (`nanobot/cli/`)

The `nanobot` CLI is the primary way to interact with the system from the terminal.

-   **Entry Point:** `nanobot/cli/commands.py`
-   **Usage:** `python -m nanobot [command]`

### Common Commands
*(To be populated based on `commands.py` analysis)*
-   `start`: Start the GigaBOT server.
-   `dev`: Start in development mode with hot-reloading.
-   `install`: Install dependencies or setup environment.

## 🕒 Cron Jobs (`config/cron/jobs.json`)

Scheduled tasks that run automatically.

-   **File:** `config/cron/jobs.json`
-   **Service:** `nanobot/cron/service.py`

## 🐳 Docker

-   **`Dockerfile`**: Defines the container image for the GigaBOT backend.
-   **`docker-compose.yml`**: Orchestrates the backend, database, and potentially frontend services.

## 🛠️ Utility Scripts

-   `bridge/`: TypeScript bridge for specific integrations (e.g., WhatsApp).
-   `nanobot/utils/helpers.py`: General helper functions used across the backend.
