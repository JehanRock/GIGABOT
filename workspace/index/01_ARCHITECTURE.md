# System Architecture

## 🏗️ High-Level Overview

GigaBOT is a hybrid AI agent system combining a Python backend (FastAPI/Swarm) with a React frontend dashboard. It uses a "Swarm" architecture to delegate tasks to specialized sub-agents.

### Core Components

1.  **Nanobot (Backend):** The Python core handling logic, memory, and external integrations.
2.  **Dashboard (Frontend):** A React-based UI for monitoring, configuration, and direct interaction.
3.  **Swarm:** A multi-agent orchestration layer for complex task execution.
4.  **Bus:** An event-driven communication layer for internal messaging.

## 🐝 Swarm Architecture (`nanobot/swarm/`)

The Swarm is the "brain" that breaks down complex user requests into manageable tasks.

-   **Orchestrator (`orchestrator.py`):** The central node that receives tasks and assigns them to workers.
-   **Workers (`worker.py`):** Specialized agents (e.g., Coder, Researcher) that execute specific tasks.
-   **Roles (`roles.py`):** Definitions of capabilities and permissions for different worker types.
-   **Team (`team.py`):** Manages groups of workers collaborating on a shared goal.

## 🔌 Event Bus (`nanobot/bus/`)

Inter-component communication happens via the Event Bus.

-   **Events (`events.py`):** Definitions of system events (e.g., `MESSAGE_RECEIVED`, `TASK_COMPLETED`).
-   **Queue (`queue.py`):** Handles the asynchronous processing of events.

## 📡 Communication Channels (`nanobot/channels/`)

GigaBOT connects to the outside world through modular channels.

-   **Manager (`manager.py`):** Lifecycle management for all active channels.
-   **Implementations:**
    -   `discord.py`
    -   `telegram.py`
    -   `whatsapp.py`
    -   `slack.py`
    -   `matrix.py`
    -   `signal.py`

## 🧠 Memory Systems (`nanobot/memory/`)

-   **Vector Store (`vector.py`):** Semantic search for long-term context.
-   **SQL/KV Store (`store.py`):** Structured data storage for state and configurations.
