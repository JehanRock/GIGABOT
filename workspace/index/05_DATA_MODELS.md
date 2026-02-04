# Data Models & Configuration

## ⚙️ Configuration (`config/`)

-   **`config.json`**: The master configuration file. Controls enabled features, API keys (referenced), and system defaults.
-   **`loader.py`**: Logic for loading and validating the config.
-   **`schema.py`**: Pydantic models defining the expected structure of the config.

## 🗄️ Database Models

*(To be populated based on `nanobot/memory/store.py` and `nanobot/session/manager.py`)*

-   **Sessions:** Stores chat history and context.
-   **Vectors:** Stores embeddings for semantic search.

## 📝 TypeScript Interfaces (`ui/dashboard/src/types/`)

-   **`index.ts`**: Shared type definitions for the frontend, mirroring the backend data structures.
