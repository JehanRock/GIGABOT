# GigaBot

**Enterprise-Grade AI Assistant Framework**

GigaBot is an enterprise-grade AI assistant platform with focus on:
- **Performance**: Tiered model routing, streaming responses, context optimization
- **Security**: Multi-layer authentication, tool policies, sandboxed execution
- **Privacy**: Self-hosted, no telemetry, encrypted channels
- **Autonomy**: Scheduled tasks, webhooks, multi-agent swarms
- **Accessibility**: Multiple channels, web dashboard, CLI

---

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
# Start the gateway (all services)
gigabot gateway

# Or run specific components
gigabot chat          # CLI chat
gigabot ui            # WebUI only
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
from gigabot.swarm import SwarmOrchestrator

orchestrator = SwarmOrchestrator(config, provider, workspace)
result = await orchestrator.execute(
    objective="Research and summarize AI trends",
    pattern="research"  # Uses predefined workflow
)
```

### Agent Team (Persona-Based Hierarchy)

GigaBot features a company-style agent hierarchy where you are the CEO and the main agent acts as your Managing Director, delegating to specialized team members:

```
You (CEO)
    └── Main Agent (Managing Director)
            ├── Architect (Claude Opus) - System design
            ├── Lead Dev (Claude Sonnet) - Complex implementation
            ├── Senior Dev (Kimi K2.5) - Feature development
            ├── Junior Dev (Gemini Flash) - Simple tasks
            ├── QA Engineer (Claude Sonnet) - Quality review
            ├── Auditor (Claude Opus) - Security review
            └── Researcher (Gemini Flash) - Information gathering
```

**Two Interaction Modes:**

1. **"Reach this goal"** (Deliberation Mode):
   - Team members discuss and provide opinions
   - Synthesized into options with pros/cons
   - Presented to you for decision

2. **"Get this done"** (Execution Mode):
   - Automatic role assignment
   - Parallel task execution
   - Mandatory QA review
   - Security audit for sensitive tasks

```python
from gigabot.swarm import TeamOrchestrator

orchestrator = TeamOrchestrator(provider, workspace, config)

# Deliberation mode - discuss and present options
result = await orchestrator.execute(
    "How should we improve authentication?",
    mode="deliberate"
)

# Execution mode - delegate and complete
result = await orchestrator.execute(
    "Add dark mode to the dashboard",
    mode="execute"
)
```

### Quality Gates

All team output passes through mandatory review:

1. **QA Review** (mandatory):
   - Correctness and logic
   - Completeness of implementation
   - Error handling
   - Edge cases

2. **Security Audit** (conditional):
   - Vulnerability assessment
   - Input validation
   - Authentication/authorization
   - Data exposure risks

```yaml
agents:
  team:
    qa_gate_enabled: true
    audit_gate_enabled: true
    audit_threshold: sensitive  # all, sensitive, none
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
gigabot gateway          # Start all services
gigabot chat            # Interactive chat
gigabot run <prompt>    # Single query

# Configuration
gigabot onboard         # Interactive setup
gigabot config show     # Show config
gigabot status          # System status

# Team Commands (Persona-Based Hierarchy)
gigabot reach <goal>     # Deliberation mode - discuss & present options
gigabot done <task>      # Execution mode - delegate & complete
gigabot team status      # Show team composition
gigabot team roles       # List all roles with details
gigabot team assign <task>  # Test task assignment logic
gigabot team deliberate <question>  # Run deliberation session

# Swarm Commands
gigabot swarm run <objective>  # Execute swarm task
gigabot swarm patterns         # List available patterns
gigabot swarm test <message>   # Test swarm trigger

# Routing Commands
gigabot routing status   # Show routing tiers
gigabot routing test <message>  # Test routing decision

# Security
gigabot security audit  # Run security checks

# Approvals
gigabot approvals list   # List pending
gigabot approvals approve <id>
gigabot approvals deny <id>

# Daemon Service
gigabot daemon install   # Install as service
gigabot daemon status    # Check status
gigabot daemon logs      # View logs

# Cron
gigabot cron list        # List jobs
gigabot cron run <id>    # Trigger manually
```

### In-Chat Commands

When using chat channels (Telegram, Discord, etc.) or the CLI chat:

```
/reach <question>   # Team deliberation mode
/done <task>        # Team execution mode
/team               # Show team status
```

---

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
  
  # Agent Team (Persona-Based Hierarchy)
  team:
    enabled: true
    roles:
      architect:
        model: anthropic/claude-opus-4-5
      lead_dev:
        model: anthropic/claude-sonnet-4-5
      senior_dev:
        model: moonshot/kimi-k2.5
      junior_dev:
        model: google/gemini-2.0-flash
      qa_engineer:
        model: anthropic/claude-sonnet-4-5
      auditor:
        model: anthropic/claude-opus-4-5
      researcher:
        model: google/gemini-2.0-flash
    qa_gate_enabled: true
    audit_gate_enabled: true
    audit_threshold: sensitive  # all, sensitive, none
    deliberation_timeout: 120
    min_opinions: 3
  
  # Multi-Agent Swarm
  swarm:
    enabled: true
    max_workers: 5
    worker_model: moonshot/kimi-k2.5
    orchestrator_model: anthropic/claude-sonnet-4-5
    auto_trigger: true
    complexity_threshold: 3

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
    token: ${GIGABOT_AUTH_TOKEN}
  
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
gigabot daemon install

# Start/stop
gigabot daemon start
gigabot daemon stop
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

### Webhooks

```python
from gigabot.hooks import Hook, HookAction, get_hook_service

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
3. Check logs: `gigabot daemon logs`

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
LOG_LEVEL=DEBUG gigabot gateway

# Test single query
gigabot run "test" --verbose
```

### Security Audit

```bash
# Run all checks
gigabot security audit

# Check specific area
gigabot security audit --category auth
```

---

## Acknowledgments

GigaBot stands on the shoulders of giants. We gratefully acknowledge:

### Nanobot by HKUDS

GigaBot builds upon the foundation of **[Nanobot](https://github.com/HKUDS/nanobot)**, created by the **Hong Kong University Data Science (HKUDS)** research group. Nanobot demonstrated that powerful AI agent functionality could be achieved in an ultra-lightweight codebase (~4,000 lines).

### OpenClaw

Special inspiration from **[OpenClaw](https://github.com/openclaw/openclaw)** for multi-channel architecture, gateway design, and enterprise-grade security patterns.

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
