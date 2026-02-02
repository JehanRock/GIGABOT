"""
Tiered model router for GigaBot.

Routes requests to appropriate models based on classification and configuration.
Supports:
- Multiple model tiers with fallbacks
- Model health tracking
- Cost optimization
- User overrides
"""

import time
from dataclasses import dataclass, field
from typing import Any

from nanobot.routing.classifier import (
    TaskClassifier,
    ClassificationResult,
    TaskType,
)


@dataclass
class ModelHealth:
    """Health tracking for a model."""
    model: str
    healthy: bool = True
    last_failure: float = 0.0
    failure_count: int = 0
    cooldown_until: float = 0.0
    
    def mark_failed(self, cooldown_seconds: int = 300) -> None:
        """Mark model as failed and set cooldown."""
        self.healthy = False
        self.last_failure = time.time()
        self.failure_count += 1
        self.cooldown_until = time.time() + cooldown_seconds
    
    def mark_success(self) -> None:
        """Mark model as healthy after successful call."""
        self.healthy = True
        self.failure_count = 0
    
    def is_available(self) -> bool:
        """Check if model is available (healthy or cooldown expired)."""
        if self.healthy:
            return True
        return time.time() >= self.cooldown_until
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "healthy": self.healthy,
            "failure_count": self.failure_count,
            "available": self.is_available(),
        }


@dataclass
class TierConfig:
    """Configuration for a model tier."""
    name: str
    models: list[str]  # Ordered by preference
    triggers: list[str]  # Task types that trigger this tier
    priority: int = 0  # Higher = more preferred for ambiguous cases


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    model: str
    tier: str
    classification: ClassificationResult
    fallback_used: bool = False
    fallback_reason: str = ""


@dataclass
class TieredRouter:
    """
    Routes requests to appropriate model tiers.
    
    Configuration:
    - tiers: Dict of tier name -> TierConfig
    - classifier: TaskClassifier for determining task type
    - fallback_tier: Default tier when classification is uncertain
    - cooldown_seconds: Time to wait before retrying failed models
    """
    
    tiers: dict[str, TierConfig] = field(default_factory=dict)
    classifier: TaskClassifier = field(default_factory=TaskClassifier)
    fallback_tier: str = "daily_driver"
    cooldown_seconds: int = 300
    
    # Health tracking for models
    _model_health: dict[str, ModelHealth] = field(default_factory=dict)
    
    # Usage statistics
    _tier_usage: dict[str, int] = field(default_factory=dict)
    _model_usage: dict[str, int] = field(default_factory=dict)
    
    def route(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        force_tier: str | None = None,
    ) -> RoutingDecision:
        """
        Route a message to the appropriate model.
        
        Args:
            message: User message to process.
            context: Optional context for classification.
            force_tier: Force a specific tier (user override).
        
        Returns:
            RoutingDecision with selected model and tier.
        """
        # Classify the task
        classification = self.classifier.classify(message, context)
        
        # Determine tier
        if force_tier and force_tier in self.tiers:
            tier_name = force_tier
        elif classification.tier in self.tiers:
            tier_name = classification.tier
        else:
            tier_name = self.fallback_tier
        
        tier = self.tiers.get(tier_name)
        if not tier:
            # Emergency fallback - use first available tier
            tier = next(iter(self.tiers.values())) if self.tiers else None
            if not tier:
                raise ValueError("No tiers configured")
        
        # Select model from tier (respecting health)
        model, fallback_used, fallback_reason = self._select_model(tier)
        
        # Update statistics
        self._tier_usage[tier_name] = self._tier_usage.get(tier_name, 0) + 1
        self._model_usage[model] = self._model_usage.get(model, 0) + 1
        
        return RoutingDecision(
            model=model,
            tier=tier_name,
            classification=classification,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )
    
    def _select_model(self, tier: TierConfig) -> tuple[str, bool, str]:
        """
        Select an available model from the tier.
        
        Returns:
            Tuple of (model, fallback_used, fallback_reason)
        """
        # Try models in order of preference
        for model in tier.models:
            health = self._get_model_health(model)
            if health.is_available():
                return model, False, ""
        
        # All models in tier are unhealthy, try fallback tier
        if tier.name != self.fallback_tier:
            fallback = self.tiers.get(self.fallback_tier)
            if fallback and fallback.models:
                for model in fallback.models:
                    health = self._get_model_health(model)
                    if health.is_available():
                        return model, True, f"Tier {tier.name} unavailable"
        
        # Last resort: use first model even if unhealthy
        if tier.models:
            return tier.models[0], True, "All models unhealthy, using first available"
        
        # No models available at all
        return "", False, "No models configured for this tier"
    
    def _get_model_health(self, model: str) -> ModelHealth:
        """Get or create health tracking for a model."""
        if model not in self._model_health:
            self._model_health[model] = ModelHealth(model=model)
        return self._model_health[model]
    
    def mark_model_failed(self, model: str) -> None:
        """Mark a model as failed (for failover tracking)."""
        health = self._get_model_health(model)
        health.mark_failed(self.cooldown_seconds)
    
    def mark_model_success(self, model: str) -> None:
        """Mark a model as successful."""
        health = self._get_model_health(model)
        health.mark_success()
    
    def get_tier_for_task_type(self, task_type: TaskType) -> str | None:
        """Get the tier name that handles a specific task type."""
        task_str = task_type.value
        for tier_name, tier in self.tiers.items():
            if task_str in tier.triggers:
                return tier_name
        return None
    
    @property
    def model_health(self) -> dict[str, ModelHealth]:
        """Get the model health dictionary."""
        return self._model_health
    
    def get_statistics(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "tier_usage": dict(self._tier_usage),
            "model_usage": dict(self._model_usage),
            "model_health": {
                model: {
                    "healthy": health.healthy,
                    "failure_count": health.failure_count,
                    "available": health.is_available(),
                }
                for model, health in self._model_health.items()
            },
        }
    
    def reset_statistics(self) -> None:
        """Reset usage statistics."""
        self._tier_usage.clear()
        self._model_usage.clear()


def create_router_from_config(config: Any) -> TieredRouter:
    """
    Create a TieredRouter from configuration.
    
    Args:
        config: Configuration object with tiered_routing settings.
    
    Returns:
        Configured TieredRouter instance.
    """
    routing_config = config.agents.tiered_routing
    
    tiers = {}
    for tier_name, tier_config in routing_config.tiers.items():
        tiers[tier_name] = TierConfig(
            name=tier_name,
            models=tier_config.models,
            triggers=tier_config.triggers,
        )
    
    classifier = TaskClassifier(
        classifier_model=routing_config.classifier_model,
        fallback_tier=routing_config.fallback_tier,
    )
    
    return TieredRouter(
        tiers=tiers,
        classifier=classifier,
        fallback_tier=routing_config.fallback_tier,
    )


# Default router configuration
DEFAULT_TIERS = {
    "daily_driver": TierConfig(
        name="daily_driver",
        models=["moonshot/kimi-k2.5", "google/gemini-2.0-flash"],
        triggers=["chat", "simple_query", "task_management", "unknown"],
        priority=0,
    ),
    "coder": TierConfig(
        name="coder",
        models=["anthropic/claude-sonnet-4-5", "openai/gpt-4.1"],
        triggers=["code", "debug", "implement", "refactor"],
        priority=1,
    ),
    "specialist": TierConfig(
        name="specialist",
        models=["anthropic/claude-opus-4-5", "google/gemini-2.0-pro"],
        triggers=["brainstorm", "creative", "complex_analysis", "research"],
        priority=2,
    ),
}


def create_default_router() -> TieredRouter:
    """Create a router with default configuration."""
    return TieredRouter(
        tiers=DEFAULT_TIERS,
        classifier=TaskClassifier(),
        fallback_tier="daily_driver",
    )
