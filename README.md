<div align="center">
  <h1>GigaBot</h1>
  <h3>Enterprise-Grade AI Assistant Framework</h3>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/status-beta-orange" alt="Status">
  </p>
</div>

**GigaBot** is an enterprise-grade AI assistant framework that transforms the lightweight foundations of personal AI assistants into a comprehensive, production-ready platform.

Built with a focus on **performance**, **security**, **privacy**, and **autonomy** — GigaBot delivers powerful multi-agent capabilities while maintaining a clean, extensible codebase.

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Channel** | Telegram, WhatsApp, Discord, Signal, Matrix, Slack |
| **Tiered Routing** | Automatic model selection based on task complexity |
| **Agent Team** | Company-style hierarchy with persona-based agents |
| **Multi-Agent Swarm** | Orchestrate multiple agents for complex tasks |
| **Quality Gates** | Mandatory QA review and security audits |
| **Deliberation Mode** | Board-style discussions for strategic decisions |
| **Security Layers** | Auth, policies, sandboxing, approval workflows |
| **Self-Hosted** | Complete privacy, no telemetry, encrypted channels |
| **WebUI Dashboard** | Real-time monitoring with WebSocket streaming |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           GigaBot                               │
├─────────────────────────────────────────────────────────────────┤
│  Channels          │  Agent Core        │  Services             │
│  ├─ Telegram       │  ├─ Loop           │  ├─ Cron              │
│  ├─ WhatsApp       │  ├─ Context        │  ├─ Heartbeat         │
│  ├─ Discord        │  ├─ Tools          │  ├─ Hooks             │
│  ├─ Signal         │  ├─ Memory         │  ├─ WebUI             │
│  ├─ Matrix         │  ├─ Compaction     │  └─ Daemon            │
│  └─ Slack          │  └─ Subagents      │                       │
├─────────────────────────────────────────────────────────────────┤
│  Routing           │  Swarm & Team      │  Security             │
│  ├─ Classifier     │  ├─ Orchestrator   │  ├─ Auth              │
│  └─ Router         │  ├─ Team Agents    │  ├─ Policy            │
│                    │  ├─ Deliberation   │  ├─ Sandbox           │
│                    │  ├─ Quality Gate   │  ├─ Approval          │
│                    │  └─ Patterns       │  └─ Audit             │
├─────────────────────────────────────────────────────────────────┤
│  Providers (LiteLLM)                                            │
│  OpenRouter │ Anthropic │ OpenAI │ Moonshot │ DeepSeek │ Ollama │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
# From source
git clone https://github.com/your-repo/gigabot.git
cd gigabot
pip install -e .
```

### Configuration

```bash
# Interactive setup
gigabot onboard

# Or create config manually
mkdir -p ~/.gigabot
```

### Run

```bash
# Start all services
gigabot gateway

# Or run specific components
gigabot chat          # CLI chat
gigabot ui            # WebUI only
```

## Configuration

Configuration is stored in `~/.gigabot/config.yaml`:

```yaml
agents:
  defaults:
    model: anthropic/claude-opus-4-5
    max_tokens: 8192
    temperature: 0.7
  
  tiered_routing:
    enabled: true
    tiers:
      daily_driver:
        models: [moonshot/kimi-k2.5]
      coder:
        models: [anthropic/claude-sonnet-4-5]
      specialist:
        models: [anthropic/claude-opus-4-5]

channels:
  telegram:
    enabled: true
    token: ${TELEGRAM_BOT_TOKEN}
    allow_from: []
  
  discord:
    enabled: true
    token: ${DISCORD_BOT_TOKEN}
    allow_guilds: []
    allow_channels: []

security:
  auth:
    mode: token
    token: ${GIGABOT_AUTH_TOKEN}
  
  sandbox:
    mode: non-main
    scope: session

providers:
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
```

## Tiered Model Routing

GigaBot automatically routes tasks to the optimal model based on complexity:

| Tier | Use Cases | Example Models |
|------|-----------|----------------|
| **Daily Driver** | Simple chat, basic questions, task management | Moonshot Kimi, GPT-4o-mini |
| **Coder** | Code generation, debugging, implementation | Claude Sonnet, GPT-4o |
| **Specialist** | Complex analysis, research, creative writing | Claude Opus, o1 |

## Multi-Agent Swarm

Orchestrate multiple agents for complex tasks:

```python
from gigabot.swarm import SwarmOrchestrator

orchestrator = SwarmOrchestrator(config, provider, workspace)
result = await orchestrator.execute(
    objective="Research and summarize AI trends",
    pattern="research"
)
```

Available patterns: `research`, `code`, `review`, `brainstorm`

## Agent Team (Persona-Based Hierarchy)

GigaBot features a company-style agent hierarchy with specialized roles:

| Role | Model | Responsibility |
|------|-------|----------------|
| **Architect** | Claude Opus | System design, technical decisions |
| **Lead Dev** | Claude Sonnet | Complex implementation, code review |
| **Senior Dev** | Kimi K2.5 | Feature development |
| **Junior Dev** | Gemini Flash | Simple tasks, bug fixes |
| **QA Engineer** | Claude Sonnet | Testing, quality review |
| **Auditor** | Claude Opus | Security review, final approval |
| **Researcher** | Gemini Flash | Information gathering |

### Interaction Modes

**Deliberation Mode** — Team discusses and presents options:
```bash
gigabot reach "How should we improve authentication security?"
# Or in chat: /reach How should we improve authentication security?
```

**Execution Mode** — Team delegates and completes work:
```bash
gigabot done "Add dark mode to the dashboard"
# Or in chat: /done Add dark mode to the dashboard
```

### Quality Gates

All team work passes through mandatory review:
1. **QA Review** — Correctness, completeness, quality
2. **Security Audit** — Vulnerability assessment (for sensitive tasks)

## Security

GigaBot implements defense in depth:

1. **Network Layer**: Bind mode, auth tokens, Tailscale integration
2. **Channel Layer**: DM pairing, user/guild/channel allowlists
3. **Tool Layer**: Allow/deny lists, approval workflows, elevated mode
4. **Runtime Layer**: Docker sandbox, resource limits, capability dropping

## CLI Reference

| Command | Description |
|---------|-------------|
| `gigabot gateway` | Start all services |
| `gigabot chat` | Interactive chat |
| `gigabot run <prompt>` | Single query |
| `gigabot onboard` | Interactive setup |
| `gigabot status` | System status |
| `gigabot reach <goal>` | Team deliberation mode |
| `gigabot done <task>` | Team execution mode |
| `gigabot team status` | Show team composition |
| `gigabot team roles` | List available roles |
| `gigabot security audit` | Run security checks |
| `gigabot approvals list` | List pending approvals |
| `gigabot daemon install` | Install as system service |
| `gigabot cron list` | List scheduled jobs |

## WebUI Dashboard

Access the dashboard at `http://localhost:18790` when running `gigabot gateway`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/api/status` | GET | System status |
| `/api/config` | GET | Configuration |
| `/api/sessions` | GET | Active sessions |
| `/api/tracking` | GET | Token usage |
| `/api/channels` | GET | Channel status |
| `/api/chat` | POST | Send message |
| `/ws` | WS | Streaming |
| `/health` | GET | Health check |

## Deployment

### Docker

```bash
# Build and run
docker compose up -d

# With WhatsApp bridge
docker compose --profile whatsapp up -d
```

### System Service

```bash
# Install as service
gigabot daemon install

# Start/stop
gigabot daemon start
gigabot daemon stop
```

## Extending GigaBot

### Custom Tools

```python
from gigabot.agent.tools import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Does something useful"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        }
    
    async def execute(self, input: str) -> str:
        return f"Processed: {input}"
```

### Custom Channels

```python
from gigabot.channels.base import BaseChannel

class MyChannel(BaseChannel):
    name = "my_channel"
    
    async def start(self) -> None:
        # Connect to platform
        pass
    
    async def stop(self) -> None:
        # Disconnect
        pass
    
    async def send(self, msg: OutboundMessage) -> None:
        # Send message
        pass
```

---

## Acknowledgments

GigaBot stands on the shoulders of giants. We gratefully acknowledge:

### Nanobot by HKUDS

GigaBot is built upon the foundation of **[Nanobot](https://github.com/HKUDS/nanobot)**, created by the **Hong Kong University Data Science (HKUDS)** research group. Nanobot demonstrated that powerful AI agent functionality could be achieved in an ultra-lightweight codebase (~4,000 lines) — a philosophy GigaBot continues to honor while expanding into enterprise territory.

The original Nanobot was inspired by Clawdbot and provided:
- Clean, readable agent architecture
- Minimal footprint with maximum capability
- Research-ready extensibility

### OpenClaw

Special thanks to **[OpenClaw](https://github.com/openclaw/openclaw)** for architectural inspiration. OpenClaw's comprehensive approach to personal AI assistants — including multi-channel communication, gateway architecture, and extensive tooling — has significantly influenced GigaBot's enterprise features:

- Multi-channel strategy (WhatsApp, Telegram, Discord, Signal, Matrix, Slack)
- Gateway-based service architecture
- Daemon and service management patterns
- Security and sandboxing approaches

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

PRs welcome! The codebase is intentionally kept clean and readable.

---

<p align="center">
  <em>GigaBot — Enterprise AI, Lightweight Core</em>
</p>
