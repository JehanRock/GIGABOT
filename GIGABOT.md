# GigaBot

**Enterprise-Grade AI Assistant Framework**

GigaBot transforms the Nanobot foundation into a comprehensive AI assistant platform with focus on:
- **Performance**: Tiered model routing, streaming responses, context optimization
- **Security**: Multi-layer authentication, tool policies, sandboxed execution
- **Privacy**: Self-hosted, no telemetry, encrypted channels
- **Autonomy**: Scheduled tasks, webhooks, multi-agent swarms
- **Accessibility**: Multiple channels, web dashboard, CLI

---

## Quick Start

### Installation

```bash
# From PyPI
pip install nanobot-ai

# From source
git clone https://github.com/your-repo/nanobot.git
cd nanobot
pip install -e .
```

### Configuration

```bash
# Interactive setup
nanobot onboard

# Or create config manually
mkdir -p ~/.nanobot
```

### Run

```bash
# Start the gateway (all services)
nanobot gateway

# Or run specific components
nanobot chat          # CLI chat
nanobot ui            # WebUI only
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GigaBot                                  │
├─────────────────────────────────────────────────────────────────┤
│  Channels          │  Agent Core        │  Services             │
│  ├─ Telegram       │  ├─ Loop           │  ├─ Cron              │
│  ├─ WhatsApp       │  ├─ Context        │  ├─ Heartbeat         │
│  ├─ Discord        │  ├─ Tools          │  ├─ Hooks             │
│  ├─ Signal         │  ├─ Memory         │  ├─ WebUI             │
│  ├─ Matrix         │  ├─ Compaction     │  └─ Daemon            │
│  └─ Slack          │  └─ Subagents      │                       │
├─────────────────────────────────────────────────────────────────┤
│  Routing           │  Swarm             │  Security             │
│  ├─ Classifier     │  ├─ Orchestrator   │  ├─ Auth              │
│  └─ Router         │  ├─ Workers        │  ├─ Policy            │
│                    │  └─ Patterns       │  ├─ Sandbox           │
│                    │                    │  ├─ Approval          │
│                    │                    │  └─ Audit             │
├─────────────────────────────────────────────────────────────────┤
│  Providers (LiteLLM)                                            │
│  OpenRouter │ Anthropic │ OpenAI │ Moonshot │ DeepSeek │ Ollama │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

### Multi-Channel Communication

GigaBot supports multiple chat platforms:

| Channel | Status | Features |
|---------|--------|----------|
| Telegram | ✅ | Bot API, groups, DMs |
| WhatsApp | ✅ | Via bridge, E2EE |
| Discord | ✅ | Guilds, DMs, slash commands |
| Signal | ✅ | E2EE, groups |
| Matrix | ✅ | E2EE, federation |
| Slack | ✅ | Workspaces, threads |

### Tiered Model Routing

Automatic routing to optimal models based on task complexity:

```yaml
# Daily Driver (fast, cheap)
- Simple chat
- Basic questions
- Task management

# Coder (balanced)
- Code generation
- Debugging
- Implementation

# Specialist (powerful, expensive)
- Complex analysis
- Research
- Creative writing
```

### Security Layers

1. **Network Layer**: Bind mode, auth tokens, Tailscale
2. **Channel Layer**: DM pairing, allowlists
3. **Tool Layer**: Allow/deny lists, approval workflows
4. **Runtime Layer**: Docker sandbox, resource limits

### Multi-Agent Swarms

Orchestrate multiple agents for complex tasks:

```python
from nanobot.swarm import SwarmOrchestrator

orchestrator = SwarmOrchestrator(config, provider, workspace)
result = await orchestrator.execute(
    objective="Research and summarize AI trends",
    pattern="research"  # Uses predefined workflow
)
```

### Context Management

Automatic context window guard:
- Token counting (tiktoken)
- Auto-summarization when approaching limits
- Preserves recent messages and important context

### Streaming Responses

Real-time token output for better UX:
- Provider-level streaming
- WebSocket delivery
- Channel-specific implementations

---

## CLI Reference

```bash
# Core Commands
nanobot gateway          # Start all services
nanobot chat            # Interactive chat
nanobot run <prompt>    # Single query

# Configuration
nanobot onboard         # Interactive setup
nanobot config show     # Show config
nanobot status          # System status

# Security
nanobot security audit  # Run security checks

# Approvals
nanobot approvals list   # List pending
nanobot approvals approve <id>
nanobot approvals deny <id>

# Daemon Service
nanobot daemon install   # Install as service
nanobot daemon status    # Check status
nanobot daemon logs      # View logs

# Cron
nanobot cron list        # List jobs
nanobot cron run <id>    # Trigger manually
```

---

## Configuration

Configuration is stored in `~/.nanobot/config.yaml`:

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
    allow_from: []  # Empty = allow all
  
  discord:
    enabled: true
    token: ${DISCORD_BOT_TOKEN}
    allow_guilds: []
    allow_channels: []

security:
  auth:
    mode: token  # none, token, password, tailscale
    token: ${NANOBOT_AUTH_TOKEN}
  
  sandbox:
    mode: non-main  # off, non-main, all
    scope: session

providers:
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
```

---

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
nanobot daemon install

# Start/stop
nanobot daemon start
nanobot daemon stop
```

### Environment Variables

See `.env.example` for all available variables.

---

## API Reference

### WebUI Endpoints

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

### WebSocket Protocol

```javascript
// Connect
ws = new WebSocket('ws://localhost:18790/ws');

// Send message
ws.send(JSON.stringify({
    action: 'chat',
    message: 'Hello!',
    session_id: 'webui:default'
}));

// Receive
// { type: 'typing', status: true }
// { type: 'response', content: '...' }
```

---

## Extending GigaBot

### Custom Tools

```python
from nanobot.agent.tools import Tool

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
from nanobot.channels.base import BaseChannel

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

### Webhooks

```python
from nanobot.hooks import Hook, HookAction, get_hook_service

hook = Hook(
    id="my-webhook",
    event="message.received",
    action=HookAction.WEBHOOK,
    target="https://my-server.com/webhook",
    filter={"channel": "telegram"}
)

service = get_hook_service()
service.add_hook(hook)
```

---

## Troubleshooting

### Common Issues

**Bot not responding**
1. Check channel is enabled in config
2. Verify API keys are set
3. Check logs: `nanobot daemon logs`

**High token usage**
1. Enable tiered routing
2. Lower context threshold
3. Check for loops in agent

**Connection errors**
1. Verify network connectivity
2. Check firewall rules
3. Ensure correct API base URLs

### Debug Mode

```bash
# Verbose logging
LOG_LEVEL=DEBUG nanobot gateway

# Test single query
nanobot run "test" --verbose
```

### Security Audit

```bash
# Run all checks
nanobot security audit

# Check specific area
nanobot security audit --category auth
```

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

---

## Support

- GitHub Issues: Bug reports and feature requests
- Discussions: Questions and community help
