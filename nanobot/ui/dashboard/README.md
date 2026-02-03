# GigaBot Dashboard

Modern, responsive dashboard for GigaBot built with React, TanStack Query, and TailwindCSS.

## Features

- **Responsive Design**: Desktop, Tablet, and Mobile layouts
- **Real-time Updates**: WebSocket connection for live data
- **Chat Interface**: Conversation list with tool output visualization
- **Analytics**: Token usage, cost tracking, session statistics
- **Channel Management**: Status, configuration, QR login for messaging platforms
- **Session Management**: TanStack Table with sorting, filtering, pagination
- **Settings**: Theme toggle, authentication, configuration

## Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool with HMR
- **TanStack Query v5** - Data fetching and caching
- **TanStack Table v8** - Data tables
- **TailwindCSS v3** - Utility-first CSS
- **Zustand** - State management
- **Recharts** - Data visualization
- **Lucide React** - Icons

## Development

### Install dependencies

```bash
npm install
```

### Start development server

```bash
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies API requests to the GigaBot gateway at `http://127.0.0.1:18790`.

### Build for production

```bash
npm run build
```

The build output goes to `../dist/` and is served by the GigaBot gateway.

## Directory Structure

```
src/
├── components/
│   ├── layout/          # Sidebar, Header, BottomNav
│   ├── chat/            # Chat panel components
│   ├── overview/        # Dashboard stats and charts
│   ├── channels/        # Channel management
│   ├── sessions/        # Session table and details
│   └── settings/        # Settings panel
├── hooks/               # Custom React hooks
├── lib/                 # API client, utilities
├── stores/              # Zustand stores
└── types/               # TypeScript definitions
```

## Self-Update System

The dashboard supports hot-swap deployments:

1. Agent can modify source files via the `dashboard` tool
2. Changes are built to a staging directory
3. Atomic deployment swaps staging to production
4. Connected clients receive refresh notification

This enables the AI agent to improve its own interface while maintaining continuous availability.
