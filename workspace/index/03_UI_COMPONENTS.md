# UI Components Catalog

This file indexes the React components, hooks, and stores used in the Dashboard (`nanobot/ui/dashboard/`).

## 🧩 Components (`src/components/`)

### Chat
-   `ChatPanel.tsx`: Main chat interface container.
-   `MessageList.tsx`: Renders the list of chat messages.
-   `MessageInput.tsx`: User input area with attachments/tools.
-   `ModelSelector.tsx`: Dropdown to choose the active LLM.

### Channels
-   `ChannelsPanel.tsx`: Configuration for external channels (Discord, Telegram, etc.).
-   `ChannelList.tsx`: List of active/configured channels.

### Config & Settings
-   `ConfigPanel.tsx`: General system configuration.
-   `SettingsPanel.tsx`: User-specific settings.

### Monitoring
-   `ActivityPanel.tsx`: Real-time system activity log.
-   `DebugPanel.tsx`: Developer tools and raw log views.
-   `SystemHealth.tsx`: CPU/Memory/Status indicators.

### Layout
-   `Sidebar.tsx`: Main navigation.
-   `Header.tsx`: Top bar with status and user info.

## 🎣 Custom Hooks (`src/hooks/`)

-   `useWebSocket.tsx`: Manages the real-time WebSocket connection to the backend.
-   `useStatus.ts`: Fetches and subscribes to system health status.
-   `useSessions.ts`: Manages chat session state.
-   `useChannels.ts`: CRUD operations for channel configuration.

## 🏪 State Management (`src/stores/`)

-   `uiStore.ts`: Global UI state (Zustand store) for themes, sidebar toggle, etc.
