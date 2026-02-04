"""
Intent tracking system for GigaBot.

Captures the "why" behind user requests:
- What goal is the user trying to accomplish?
- Is this a recurring pattern?
- What category does this fall into?
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any
from enum import Enum


class IntentCategory(str, Enum):
    """Categories for user intents."""
    WORK = "work"               # Tasks, meetings, projects, deadlines
    PERSONAL = "personal"       # Reminders, notes, life organization
    LEARNING = "learning"       # Research, tutorials, skill acquisition
    CREATIVE = "creative"       # Writing, brainstorming, ideation
    TECHNICAL = "technical"     # Coding, debugging, system administration
    COMMUNICATION = "communication"  # Drafts, responses, scheduling
    OTHER = "other"             # Uncategorized


@dataclass
class UserIntent:
    """A captured user intent."""
    id: str
    user_id: str
    session_id: str
    raw_request: str
    inferred_goal: str
    category: str
    urgency: float  # 0.0-1.0
    recurring: bool
    related_intents: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    satisfaction_score: float = 0.0  # 0.0-1.0, based on follow-ups
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserIntent":
        """Create from dictionary."""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('completed_at'):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)


@dataclass
class PatternInsight:
    """A discovered pattern in user behavior."""
    id: str
    pattern_type: str  # "recurring_task", "time_preference", "topic_cluster"
    description: str
    confidence: float  # 0.0-1.0
    frequency: int     # How often this pattern occurs
    examples: list[str] = field(default_factory=list)  # Intent IDs as examples
    discovered_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['discovered_at'] = self.discovered_at.isoformat()
        data['last_seen'] = self.last_seen.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternInsight":
        """Create from dictionary."""
        data['discovered_at'] = datetime.fromisoformat(data['discovered_at'])
        data['last_seen'] = datetime.fromisoformat(data['last_seen'])
        return cls(**data)


@dataclass
class PredictedIntent:
    """A predicted future intent."""
    predicted_goal: str
    category: str
    confidence: float  # 0.0-1.0
    based_on_patterns: list[str]  # Pattern IDs
    reasoning: str


class IntentTracker:
    """
    Captures and analyzes user intentions over time.
    
    Features:
    - LLM-powered intent extraction from messages
    - Pattern discovery across intent history
    - Intent prediction based on patterns
    - Satisfaction tracking
    """
    
    # Prompt for intent extraction
    EXTRACTION_PROMPT = """Analyze this user message and extract the underlying intent.

User message: {message}

Respond with JSON only (no markdown):
{{
    "inferred_goal": "What the user is ultimately trying to accomplish",
    "category": "work|personal|learning|creative|technical|communication|other",
    "urgency": 0.0-1.0,
    "recurring": true/false (does this seem like a recurring task?)
}}"""

    PATTERN_ANALYSIS_PROMPT = """Analyze these user intents and identify patterns.

Intents (most recent first):
{intents}

Look for:
1. Recurring tasks (same or similar goals)
2. Time preferences (when certain types of requests happen)
3. Topic clusters (related subjects)

Respond with JSON only (no markdown):
{{
    "patterns": [
        {{
            "pattern_type": "recurring_task|time_preference|topic_cluster",
            "description": "Description of the pattern",
            "confidence": 0.0-1.0,
            "frequency": number of occurrences,
            "example_ids": ["intent_id1", "intent_id2"]
        }}
    ]
}}"""

    PREDICTION_PROMPT = """Based on these user patterns and recent intents, predict what the user might need next.

Recent intents:
{recent_intents}

Discovered patterns:
{patterns}

Current time: {current_time}

Respond with JSON only (no markdown):
{{
    "predictions": [
        {{
            "predicted_goal": "What the user will likely want",
            "category": "work|personal|learning|creative|technical|communication|other",
            "confidence": 0.0-1.0,
            "reasoning": "Why you predict this"
        }}
    ]
}}"""
    
    def __init__(
        self,
        workspace: Path,
        provider: Any = None,
        model: str = "moonshot/kimi-k2.5"
    ):
        """
        Initialize the intent tracker.
        
        Args:
            workspace: Workspace path for storage
            provider: LLM provider for intent extraction
            model: Model to use for analysis
        """
        self.workspace = workspace
        self.provider = provider
        self.model = model
        
        # Storage paths
        self.intent_dir = workspace / "memory" / "intents"
        self.intent_dir.mkdir(parents=True, exist_ok=True)
        
        self.intents_file = self.intent_dir / "intents.json"
        self.patterns_file = self.intent_dir / "patterns.json"
        
        # In-memory cache
        self._intents_cache: list[UserIntent] | None = None
        self._patterns_cache: list[PatternInsight] | None = None
    
    def _load_intents(self) -> list[UserIntent]:
        """Load intents from storage."""
        if self._intents_cache is not None:
            return self._intents_cache
        
        if not self.intents_file.exists():
            self._intents_cache = []
            return self._intents_cache
        
        try:
            data = json.loads(self.intents_file.read_text())
            self._intents_cache = [UserIntent.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            self._intents_cache = []
        
        return self._intents_cache
    
    def _save_intents(self) -> None:
        """Save intents to storage."""
        intents = self._load_intents()
        data = [i.to_dict() for i in intents]
        self.intents_file.write_text(json.dumps(data, indent=2))
    
    def _load_patterns(self) -> list[PatternInsight]:
        """Load patterns from storage."""
        if self._patterns_cache is not None:
            return self._patterns_cache
        
        if not self.patterns_file.exists():
            self._patterns_cache = []
            return self._patterns_cache
        
        try:
            data = json.loads(self.patterns_file.read_text())
            self._patterns_cache = [PatternInsight.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            self._patterns_cache = []
        
        return self._patterns_cache
    
    def _save_patterns(self) -> None:
        """Save patterns to storage."""
        patterns = self._load_patterns()
        data = [p.to_dict() for p in patterns]
        self.patterns_file.write_text(json.dumps(data, indent=2))
    
    async def capture_intent(
        self,
        message: str,
        session_id: str,
        user_id: str = "default"
    ) -> UserIntent:
        """
        Capture intent from a user message.
        
        Uses LLM to extract:
        - Inferred goal
        - Category
        - Urgency
        - Whether it's recurring
        
        Args:
            message: The user's message
            session_id: Current session ID
            user_id: User identifier
            
        Returns:
            UserIntent with extracted information
        """
        # Default values if no provider
        inferred_goal = message[:200]  # Truncate for storage
        category = IntentCategory.OTHER.value
        urgency = 0.5
        recurring = False
        
        # Use LLM for extraction if available
        if self.provider:
            try:
                prompt = self.EXTRACTION_PROMPT.format(message=message[:500])
                response = await self.provider.complete(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model,
                    max_tokens=500,
                    temperature=0.3
                )
                
                # Parse JSON response
                content = response.get("content", "")
                # Clean up potential markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content.strip())
                inferred_goal = data.get("inferred_goal", inferred_goal)
                category = data.get("category", category)
                urgency = float(data.get("urgency", urgency))
                recurring = bool(data.get("recurring", recurring))
                
            except Exception:
                # Fall back to defaults on error
                pass
        
        # Find related intents
        related = self._find_related_intents(message, user_id)
        
        # Create intent
        intent = UserIntent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            raw_request=message[:1000],  # Limit storage size
            inferred_goal=inferred_goal,
            category=category,
            urgency=urgency,
            recurring=recurring,
            related_intents=[r.id for r in related[:5]],
        )
        
        # Store
        intents = self._load_intents()
        intents.append(intent)
        self._save_intents()
        
        return intent
    
    def _find_related_intents(
        self,
        message: str,
        user_id: str,
        limit: int = 5
    ) -> list[UserIntent]:
        """Find intents related to this message."""
        intents = self._load_intents()
        user_intents = [i for i in intents if i.user_id == user_id]
        
        # Simple keyword matching for now
        # Could be enhanced with vector similarity
        message_words = set(message.lower().split())
        scored = []
        
        for intent in user_intents[-100:]:  # Check recent 100
            goal_words = set(intent.inferred_goal.lower().split())
            overlap = len(message_words & goal_words)
            if overlap > 0:
                scored.append((overlap, intent))
        
        # Sort by overlap score
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:limit]]
    
    async def analyze_patterns(
        self,
        user_id: str = "default",
        days: int = 30
    ) -> list[PatternInsight]:
        """
        Analyze intent history to discover patterns.
        
        Args:
            user_id: User to analyze
            days: How many days of history to analyze
            
        Returns:
            List of discovered patterns
        """
        intents = self.get_history(user_id, days=days)
        
        if len(intents) < 3:
            return []  # Not enough data
        
        # Format intents for LLM
        intent_summaries = []
        for i in intents[:50]:  # Limit to recent 50
            intent_summaries.append(
                f"- [{i.id[:8]}] {i.created_at.strftime('%Y-%m-%d %H:%M')} "
                f"({i.category}): {i.inferred_goal}"
            )
        
        patterns: list[PatternInsight] = []
        
        if self.provider:
            try:
                prompt = self.PATTERN_ANALYSIS_PROMPT.format(
                    intents="\n".join(intent_summaries)
                )
                response = await self.provider.complete(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model,
                    max_tokens=1000,
                    temperature=0.3
                )
                
                content = response.get("content", "")
                # Clean markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content.strip())
                
                for p in data.get("patterns", []):
                    pattern = PatternInsight(
                        id=str(uuid.uuid4()),
                        pattern_type=p.get("pattern_type", "other"),
                        description=p.get("description", ""),
                        confidence=float(p.get("confidence", 0.5)),
                        frequency=int(p.get("frequency", 1)),
                        examples=p.get("example_ids", []),
                    )
                    patterns.append(pattern)
                    
            except Exception:
                pass
        
        # Fallback: Simple recurring detection
        if not patterns:
            patterns = self._detect_simple_patterns(intents)
        
        # Update cache and save
        self._patterns_cache = patterns
        self._save_patterns()
        
        return patterns
    
    def _detect_simple_patterns(
        self,
        intents: list[UserIntent]
    ) -> list[PatternInsight]:
        """Simple pattern detection without LLM."""
        patterns = []
        
        # Group by category
        category_counts: dict[str, list[UserIntent]] = {}
        for intent in intents:
            cat = intent.category
            if cat not in category_counts:
                category_counts[cat] = []
            category_counts[cat].append(intent)
        
        # Find dominant categories
        for cat, cat_intents in category_counts.items():
            if len(cat_intents) >= 3:
                patterns.append(PatternInsight(
                    id=str(uuid.uuid4()),
                    pattern_type="topic_cluster",
                    description=f"Frequent {cat} requests ({len(cat_intents)} occurrences)",
                    confidence=min(len(cat_intents) / 10, 1.0),
                    frequency=len(cat_intents),
                    examples=[i.id for i in cat_intents[:5]],
                ))
        
        # Detect recurring goals (simple word overlap)
        goal_groups: dict[str, list[UserIntent]] = {}
        for intent in intents:
            # Use first 3 words as key
            key = " ".join(intent.inferred_goal.lower().split()[:3])
            if key not in goal_groups:
                goal_groups[key] = []
            goal_groups[key].append(intent)
        
        for key, group in goal_groups.items():
            if len(group) >= 2:
                patterns.append(PatternInsight(
                    id=str(uuid.uuid4()),
                    pattern_type="recurring_task",
                    description=f"Recurring: {group[0].inferred_goal[:50]}",
                    confidence=min(len(group) / 5, 1.0),
                    frequency=len(group),
                    examples=[i.id for i in group[:5]],
                ))
        
        return patterns
    
    async def predict_next_intent(
        self,
        user_id: str = "default"
    ) -> list[PredictedIntent]:
        """
        Predict what the user might need next.
        
        Args:
            user_id: User to predict for
            
        Returns:
            List of predicted intents with confidence
        """
        recent = self.get_history(user_id, days=7)
        patterns = self._load_patterns()
        
        if not recent:
            return []
        
        predictions: list[PredictedIntent] = []
        
        if self.provider and patterns:
            try:
                # Format for LLM
                recent_summaries = [
                    f"- {i.created_at.strftime('%Y-%m-%d %H:%M')}: {i.inferred_goal}"
                    for i in recent[:10]
                ]
                pattern_summaries = [
                    f"- {p.pattern_type}: {p.description} (confidence: {p.confidence:.1f})"
                    for p in patterns[:5]
                ]
                
                prompt = self.PREDICTION_PROMPT.format(
                    recent_intents="\n".join(recent_summaries),
                    patterns="\n".join(pattern_summaries),
                    current_time=datetime.now().strftime("%Y-%m-%d %H:%M %A")
                )
                
                response = await self.provider.complete(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model,
                    max_tokens=500,
                    temperature=0.5
                )
                
                content = response.get("content", "")
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content.strip())
                
                for p in data.get("predictions", []):
                    predictions.append(PredictedIntent(
                        predicted_goal=p.get("predicted_goal", ""),
                        category=p.get("category", "other"),
                        confidence=float(p.get("confidence", 0.5)),
                        based_on_patterns=[],
                        reasoning=p.get("reasoning", "")
                    ))
                    
            except Exception:
                pass
        
        # Fallback: Predict from recurring patterns
        if not predictions:
            for pattern in patterns:
                if pattern.pattern_type == "recurring_task" and pattern.confidence > 0.5:
                    predictions.append(PredictedIntent(
                        predicted_goal=pattern.description.replace("Recurring: ", ""),
                        category="other",
                        confidence=pattern.confidence * 0.8,
                        based_on_patterns=[pattern.id],
                        reasoning=f"Based on {pattern.frequency} similar past requests"
                    ))
        
        return predictions[:5]  # Top 5
    
    def mark_completed(
        self,
        intent_id: str,
        satisfaction: float = 1.0
    ) -> bool:
        """
        Mark an intent as completed.
        
        Args:
            intent_id: Intent to mark
            satisfaction: User satisfaction score (0.0-1.0)
            
        Returns:
            True if found and updated
        """
        intents = self._load_intents()
        
        for intent in intents:
            if intent.id == intent_id:
                intent.completed_at = datetime.now()
                intent.satisfaction_score = satisfaction
                self._save_intents()
                return True
        
        return False
    
    def get_history(
        self,
        user_id: str = "default",
        days: int = 30,
        category: str | None = None
    ) -> list[UserIntent]:
        """
        Get intent history for a user.
        
        Args:
            user_id: User to get history for
            days: How many days back
            category: Optional category filter
            
        Returns:
            List of intents, most recent first
        """
        intents = self._load_intents()
        cutoff = datetime.now() - timedelta(days=days)
        
        filtered = [
            i for i in intents
            if i.user_id == user_id
            and i.created_at >= cutoff
            and (category is None or i.category == category)
        ]
        
        # Sort most recent first
        filtered.sort(key=lambda x: x.created_at, reverse=True)
        return filtered
    
    def get_stats(self, user_id: str = "default") -> dict[str, Any]:
        """Get intent statistics."""
        intents = self._load_intents()
        user_intents = [i for i in intents if i.user_id == user_id]
        patterns = self._load_patterns()
        
        # Category distribution
        categories: dict[str, int] = {}
        for intent in user_intents:
            cat = intent.category
            categories[cat] = categories.get(cat, 0) + 1
        
        # Completion rate
        completed = sum(1 for i in user_intents if i.completed_at)
        completion_rate = completed / len(user_intents) if user_intents else 0
        
        # Average satisfaction
        satisfaction_scores = [
            i.satisfaction_score for i in user_intents
            if i.satisfaction_score > 0
        ]
        avg_satisfaction = (
            sum(satisfaction_scores) / len(satisfaction_scores)
            if satisfaction_scores else 0
        )
        
        return {
            "total_intents": len(user_intents),
            "category_distribution": categories,
            "completion_rate": completion_rate,
            "average_satisfaction": avg_satisfaction,
            "patterns_discovered": len(patterns),
            "recurring_intents": sum(1 for i in user_intents if i.recurring),
        }
    
    def invalidate_cache(self) -> None:
        """Clear caches."""
        self._intents_cache = None
        self._patterns_cache = None
