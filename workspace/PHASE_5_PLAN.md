# Phase 5: Proactive Intelligence & Memory Evolution

## Inspired by MemUbot - Key Differentiators

Based on MemUbot's architecture, GigaBot can implement proactive AI capabilities that anticipate user needs, track intent patterns, and optimize costs through intelligent memory management.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     PROACTIVE ENGINE                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Intent       │  │ Pattern      │  │ Proactive    │      │
│  │ Tracker      │─▶│ Analyzer     │─▶│ Scheduler    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────────────────────────────────────────┐      │
│  │              MEMORY EVOLUTION SYSTEM              │      │
│  ├──────────────────────────────────────────────────┤      │
│  │ Auto-Promote │ Auto-Expire │ Cross-Reference     │      │
│  └──────────────────────────────────────────────────┘      │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────┐      │
│  │              COST OPTIMIZATION LAYER              │      │
│  ├──────────────────────────────────────────────────┤      │
│  │ Token Tracker │ Cache Manager │ Deduplication    │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 1: Intent Tracking System

### 1.1 Create IntentTracker (`nanobot/intent/tracker.py`)

Track the "why" behind user requests:

```python
@dataclass
class UserIntent:
    id: str
    user_id: str
    raw_request: str
    inferred_goal: str          # What the user is trying to accomplish
    category: str               # work, personal, learning, etc.
    urgency: float              # 0.0 to 1.0
    recurring: bool             # Is this a repeated pattern?
    related_intents: list[str]  # Links to previous similar intents
    created_at: datetime
    completed_at: datetime | None
    satisfaction_score: float   # 0.0 to 1.0, based on follow-ups

class IntentTracker:
    """Captures and analyzes user intentions over time."""
    
    async def capture_intent(self, message: str, session_id: str) -> UserIntent
    async def analyze_patterns(self, user_id: str) -> list[PatternInsight]
    async def predict_next_intent(self, user_id: str) -> list[PredictedIntent]
    def get_intent_history(self, user_id: str, days: int = 30) -> list[UserIntent]
```

### 1.2 Intent Categories

Pre-defined categories for classification:
- **work**: Tasks, meetings, projects, deadlines
- **learning**: Research, tutorials, skill acquisition
- **personal**: Reminders, notes, life organization
- **creative**: Writing, brainstorming, ideation
- **technical**: Coding, debugging, system administration
- **communication**: Drafts, responses, scheduling

---

## Part 2: Proactive Agent System

### 2.1 Create ProactiveEngine (`nanobot/proactive/engine.py`)

```python
class ProactiveAction:
    """An action the agent can take proactively."""
    id: str
    type: str                   # reminder, suggestion, automation
    trigger: str                # schedule, pattern, event
    priority: float
    content: str
    context: dict
    requires_confirmation: bool

class ProactiveEngine:
    """
    Anticipates user needs and initiates helpful actions.
    
    Unlike reactive agents that wait for commands, this engine:
    - Monitors patterns and schedules
    - Generates proactive suggestions
    - Automates routine tasks
    - Sends timely reminders
    """
    
    async def check_triggers(self) -> list[ProactiveAction]
    async def execute_action(self, action: ProactiveAction) -> bool
    async def learn_from_feedback(self, action_id: str, accepted: bool)
```

### 2.2 Proactive Action Types

| Type | Description | Example |
|------|-------------|---------|
| **reminder** | Time-based prompts | "You have a meeting in 30 minutes" |
| **suggestion** | Pattern-based recommendations | "Based on your Friday routine, should I prepare the weekly report?" |
| **automation** | Pre-approved recurring tasks | Auto-summarize daily notes at 6 PM |
| **insight** | Discovered patterns | "You seem to work best on code in the morning" |
| **anticipation** | Predicted needs | "Here's the research you'll probably need for tomorrow's task" |

---

## Part 3: Memory Evolution System

### 3.1 Create MemoryEvolution (`nanobot/memory/evolution.py`)

Self-organizing memory that improves over time:

```python
class MemoryEvolution:
    """
    Manages memory lifecycle and self-organization.
    
    Features:
    - Auto-promotion: Frequently accessed memories gain importance
    - Auto-expiration: Unused memories decay
    - Cross-referencing: Link related memories automatically
    - Consolidation: Merge similar memories
    """
    
    async def evolve(self) -> EvolutionReport:
        """Run periodic evolution cycle."""
        
    async def promote_memory(self, entry_id: str, reason: str)
    async def expire_memory(self, entry_id: str)
    async def cross_reference(self, entry_id: str) -> list[str]
    async def consolidate_similar(self, threshold: float = 0.85) -> int
```

### 3.2 Memory Access Tracking

Add to MemoryEntry:
```python
@dataclass
class MemoryEntry:
    # ... existing fields ...
    access_count: int = 0
    last_accessed: datetime | None = None
    promotion_score: float = 0.0
    decay_rate: float = 0.01      # How fast it loses importance
    cross_references: list[str] = field(default_factory=list)
```

### 3.3 Evolution Rules

1. **Promotion Rules**
   - Accessed 3+ times in a week → +0.1 importance
   - Referenced by agent in response → +0.05 importance
   - Linked to active project → +0.15 importance

2. **Decay Rules**
   - Not accessed in 30 days → -0.1 importance
   - Importance below 0.1 → candidate for archival
   - Archive after 90 days of no access

3. **Consolidation Rules**
   - Similarity > 0.85 → merge candidates
   - Same topic within 24 hours → auto-merge
   - Keep most detailed version, link to source

---

## Part 4: Cost Optimization Layer

### 4.1 Create CostOptimizer (`nanobot/tracking/optimizer.py`)

Intelligent token management:

```python
class CostOptimizer:
    """
    Reduces API costs while maintaining quality.
    
    Strategies:
    - Response caching for identical queries
    - Memory deduplication
    - Context pruning (remove low-value memories)
    - Model downgrades for simple tasks
    """
    
    def should_cache(self, query: str) -> bool
    def get_cached_response(self, query: str) -> str | None
    def estimate_cost(self, prompt: str, model: str) -> float
    def suggest_optimization(self, usage: UsageStats) -> list[Suggestion]
```

### 4.2 Caching Strategy

```python
@dataclass
class CacheEntry:
    query_hash: str
    response: str
    model_used: str
    created_at: datetime
    expires_at: datetime
    hit_count: int
    
class ResponseCache:
    """Cache for frequent queries."""
    
    def cache(self, query: str, response: str, ttl: int = 3600)
    def get(self, query: str) -> str | None
    def invalidate_by_pattern(self, pattern: str)
```

### 4.3 Cost Tracking Dashboard

Add to UI:
- Daily/weekly/monthly token usage charts
- Cost breakdown by model
- Savings from caching (tokens saved)
- Optimization suggestions

---

## Part 5: Configuration Schema

Add to `config/schema.py`:

```python
class ProactiveConfig(BaseModel):
    """Proactive intelligence configuration."""
    enabled: bool = True
    
    # Intent tracking
    track_intents: bool = True
    intent_analysis_model: str = "moonshot/kimi-k2.5"
    
    # Proactive actions
    proactive_suggestions: bool = True
    require_confirmation: bool = True
    max_daily_proactive: int = 10
    
    # Automation
    allow_automation: bool = False
    automation_allowlist: list[str] = []

class MemoryEvolutionConfig(BaseModel):
    """Memory evolution configuration."""
    enabled: bool = True
    evolution_interval_hours: int = 24
    auto_promote: bool = True
    auto_expire: bool = True
    auto_consolidate: bool = True
    min_importance_threshold: float = 0.1
    archive_after_days: int = 90

class CostOptimizationConfig(BaseModel):
    """Cost optimization configuration."""
    enabled: bool = True
    response_caching: bool = True
    cache_ttl_seconds: int = 3600
    deduplicate_memories: bool = True
    context_pruning: bool = True
    budget_alerts: bool = True
```

---

## Part 6: CLI Commands

```bash
# Intent commands
gigabot intent history           # View recent intents
gigabot intent patterns          # Show discovered patterns
gigabot intent predict           # Predicted next intents

# Proactive commands
gigabot proactive status         # Proactive engine status
gigabot proactive pending        # Pending proactive actions
gigabot proactive approve <id>   # Approve an action
gigabot proactive dismiss <id>   # Dismiss an action
gigabot proactive automate       # Configure automation rules

# Memory evolution commands
gigabot memory evolve            # Trigger evolution cycle
gigabot memory stats             # Memory statistics
gigabot memory promote <id>      # Manually promote memory
gigabot memory archive           # Archive expired memories

# Cost optimization commands
gigabot cost report              # Usage and cost report
gigabot cost cache-stats         # Cache hit/miss stats
gigabot cost optimize            # Get optimization suggestions
```

---

## Implementation Order

1. **Intent Tracker** (Foundation)
   - Intent capture and storage
   - Basic pattern analysis
   - Integration with agent loop

2. **Memory Evolution** (Build on existing memory)
   - Access tracking
   - Promotion/decay logic
   - Cross-referencing

3. **Cost Optimizer** (Low-hanging fruit)
   - Response caching
   - Token tracking improvements
   - Budget alerts

4. **Proactive Engine** (Advanced)
   - Trigger system
   - Action generation
   - User confirmation workflow

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Intent prediction accuracy | 70% | Predicted vs actual intents |
| Cost reduction | 30% | Tokens saved via caching |
| Proactive acceptance rate | 60% | Accepted vs dismissed actions |
| Memory relevance | 80% | Retrieved memories used in response |

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `nanobot/intent/__init__.py` | Create | Intent module |
| `nanobot/intent/tracker.py` | Create | Intent tracking |
| `nanobot/proactive/__init__.py` | Create | Proactive module |
| `nanobot/proactive/engine.py` | Create | Proactive engine |
| `nanobot/proactive/actions.py` | Create | Action types |
| `nanobot/memory/evolution.py` | Create | Memory evolution |
| `nanobot/tracking/optimizer.py` | Modify | Add cost optimization |
| `nanobot/tracking/cache.py` | Create | Response cache |
| `nanobot/config/schema.py` | Modify | Add new configs |
| `nanobot/cli/commands.py` | Modify | Add CLI commands |
| `nanobot/agent/loop.py` | Modify | Integrate intent + proactive |

---

## Comparison: After Phase 5

| Feature | MemUbot | GigaBot After Phase 5 |
|---------|---------|----------------------|
| 24/7 Proactive Agents | Yes | Yes |
| Intent Capture | Yes | Yes |
| Memory Self-Evolution | Yes | Yes |
| Cost Optimization | Yes | Yes |
| Multi-Platform | Yes | Yes (6 channels) |
| Multi-Agent Swarm | Limited | Yes (Advanced) |
| Model Profiler | No | Yes (Unique) |
| Self-Healing Tools | No | Yes (Unique) |
| Remote Nodes | No | Yes (Unique) |
| Quality Gates | No | Yes (Unique) |
