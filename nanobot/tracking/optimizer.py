"""
Self-optimization system for GigaBot.

Analyzes usage patterns and suggests optimizations:
- Tier downgrades for simple queries
- Response caching
- Context pruning
- Budget optimization
"""

from typing import Any, TYPE_CHECKING
from dataclasses import dataclass, field

from nanobot.tracking.tokens import TokenTracker, UsageStats

if TYPE_CHECKING:
    from nanobot.tracking.cache import ResponseCache


@dataclass
class OptimizationSuggestion:
    """A suggestion for optimization."""
    category: str  # tier, cache, context, budget
    title: str
    description: str
    potential_savings: float  # Estimated token reduction % or USD
    priority: str  # high, medium, low
    action: str  # What to do
    estimated_usd: float = 0.0  # Estimated USD savings


class SelfOptimizer:
    """
    Analyzes usage patterns and suggests optimizations.
    
    Strategies:
    - Tier optimization: Route simple queries to cheaper models
    - Caching: Cache repeated queries
    - Context pruning: Reduce context for long conversations
    - Budget management: Adjust usage based on budget
    """
    
    def __init__(self, tracker: TokenTracker):
        self.tracker = tracker
        
        # Response cache for optimization
        self._cache: dict[str, str] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def analyze(self) -> list[OptimizationSuggestion]:
        """
        Analyze current usage and generate optimization suggestions.
        
        Returns:
            List of optimization suggestions.
        """
        suggestions = []
        
        # Analyze tier usage
        suggestions.extend(self._analyze_tier_usage())
        
        # Analyze caching opportunities
        suggestions.extend(self._analyze_caching())
        
        # Analyze context usage
        suggestions.extend(self._analyze_context())
        
        # Analyze budget
        suggestions.extend(self._analyze_budget())
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 2))
        
        return suggestions
    
    def _analyze_tier_usage(self) -> list[OptimizationSuggestion]:
        """Analyze tier usage for optimization opportunities."""
        suggestions = []
        stats = self.tracker.get_weekly_stats()
        
        tier_usage = stats.tier_usage
        total = sum(tier_usage.values()) or 1
        
        # Check specialist tier usage
        specialist_pct = tier_usage.get("specialist", 0) / total
        if specialist_pct > 0.3:
            suggestions.append(OptimizationSuggestion(
                category="tier",
                title="High Specialist Tier Usage",
                description=f"Specialist tier accounts for {specialist_pct*100:.0f}% of tokens. Consider if some queries could use the coder or daily_driver tier.",
                potential_savings=specialist_pct * 50,  # Could save 50% on these
                priority="high",
                action="Review specialist tier queries and downgrade where appropriate",
            ))
        
        # Check if daily_driver is underutilized
        daily_pct = tier_usage.get("daily_driver", 0) / total
        if daily_pct < 0.5:
            suggestions.append(OptimizationSuggestion(
                category="tier",
                title="Daily Driver Underutilized",
                description=f"Daily driver tier only accounts for {daily_pct*100:.0f}% of tokens. Many queries could potentially use this cheaper tier.",
                potential_savings=30,
                priority="medium",
                action="Enable tiered routing to automatically route simple queries to daily_driver",
            ))
        
        return suggestions
    
    def _analyze_caching(self) -> list[OptimizationSuggestion]:
        """Analyze caching opportunities."""
        suggestions = []
        
        # Check cache hit rate
        total_requests = self._cache_hits + self._cache_misses
        if total_requests > 10:
            hit_rate = self._cache_hits / total_requests
            
            if hit_rate < 0.2:
                suggestions.append(OptimizationSuggestion(
                    category="cache",
                    title="Low Cache Hit Rate",
                    description=f"Cache hit rate is only {hit_rate*100:.0f}%. Consider caching frequent queries.",
                    potential_savings=20,
                    priority="medium",
                    action="Enable response caching for repeated queries",
                ))
            elif hit_rate > 0.5:
                savings = hit_rate * 100
                suggestions.append(OptimizationSuggestion(
                    category="cache",
                    title="Good Cache Performance",
                    description=f"Cache hit rate is {hit_rate*100:.0f}%, saving approximately {savings:.0f}% of tokens on cached queries.",
                    potential_savings=0,
                    priority="low",
                    action="Continue current caching strategy",
                ))
        
        return suggestions
    
    def _analyze_context(self) -> list[OptimizationSuggestion]:
        """Analyze context usage for optimization."""
        suggestions = []
        stats = self.tracker.get_session_stats()
        
        # Check tokens per request (high = potentially large contexts)
        if stats.request_count > 5:
            avg_tokens = stats.tokens_per_request
            
            if avg_tokens > 5000:
                suggestions.append(OptimizationSuggestion(
                    category="context",
                    title="High Tokens Per Request",
                    description=f"Average of {avg_tokens:.0f} tokens per request suggests large contexts. Consider context pruning.",
                    potential_savings=30,
                    priority="high",
                    action="Enable context summarization for long conversations",
                ))
            elif avg_tokens > 2000:
                suggestions.append(OptimizationSuggestion(
                    category="context",
                    title="Moderate Context Size",
                    description=f"Average of {avg_tokens:.0f} tokens per request. Monitor for growth.",
                    potential_savings=10,
                    priority="low",
                    action="Consider enabling context window guard",
                ))
        
        return suggestions
    
    def _analyze_budget(self) -> list[OptimizationSuggestion]:
        """Analyze budget-related optimizations."""
        suggestions = []
        
        daily = self.tracker.get_daily_stats()
        weekly = self.tracker.get_weekly_stats()
        
        # Check daily budget utilization
        if self.tracker.daily_budget > 0:
            usage_pct = daily.total_tokens / self.tracker.daily_budget
            
            if usage_pct > 0.9:
                suggestions.append(OptimizationSuggestion(
                    category="budget",
                    title="Near Daily Budget Limit",
                    description=f"At {usage_pct*100:.0f}% of daily budget. Consider reducing token usage.",
                    potential_savings=0,
                    priority="high",
                    action="Switch to cheaper tiers or reduce request frequency",
                ))
        
        # Estimate cost efficiency
        cost = self.tracker.estimate_cost(weekly)
        if weekly.request_count > 0:
            cost_per_request = cost / weekly.request_count
            
            if cost_per_request > 0.10:  # More than 10 cents per request
                suggestions.append(OptimizationSuggestion(
                    category="budget",
                    title="High Cost Per Request",
                    description=f"Average cost is ${cost_per_request:.4f} per request. Consider using cheaper models.",
                    potential_savings=50,
                    priority="high",
                    action="Enable tiered routing to optimize model selection",
                ))
        
        return suggestions
    
    def check_cache(self, query: str) -> str | None:
        """
        Check if a query is cached.
        
        Args:
            query: The query to check.
        
        Returns:
            Cached response or None.
        """
        cache_key = self._hash_query(query)
        
        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]
        
        self._cache_misses += 1
        return None
    
    def cache_response(self, query: str, response: str) -> None:
        """
        Cache a query response.
        
        Args:
            query: The original query.
            response: The response to cache.
        """
        cache_key = self._hash_query(query)
        
        # Limit cache size
        if len(self._cache) > 1000:
            # Remove oldest entries (simple approach)
            keys = list(self._cache.keys())[:100]
            for key in keys:
                del self._cache[key]
        
        self._cache[cache_key] = response
    
    def _hash_query(self, query: str) -> str:
        """Generate cache key for a query."""
        import hashlib
        # Normalize query
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get_efficiency_score(self) -> float:
        """
        Calculate efficiency score (0-100).
        
        Based on:
        - Tier distribution (cheaper tiers = higher score)
        - Cache hit rate
        - Cost per request
        """
        score = 50.0  # Base score
        
        stats = self.tracker.get_weekly_stats()
        tier_usage = stats.tier_usage
        total = sum(tier_usage.values()) or 1
        
        # Tier distribution bonus
        daily_pct = tier_usage.get("daily_driver", 0) / total
        score += daily_pct * 20  # Up to +20 for daily driver usage
        
        # Cache hit bonus
        total_requests = self._cache_hits + self._cache_misses
        if total_requests > 0:
            hit_rate = self._cache_hits / total_requests
            score += hit_rate * 15  # Up to +15 for cache hits
        
        # Cost penalty for high per-request cost
        if stats.request_count > 0:
            cost = self.tracker.estimate_cost(stats)
            cost_per_request = cost / stats.request_count
            
            if cost_per_request > 0.10:
                score -= 15  # Penalty for expensive requests
            elif cost_per_request < 0.01:
                score += 15  # Bonus for cheap requests
        
        return max(0, min(100, score))
    
    def get_summary(self) -> dict[str, Any]:
        """Get optimization summary."""
        suggestions = self.analyze()
        
        return {
            "efficiency_score": round(self.get_efficiency_score(), 1),
            "cache_hit_rate": self._cache_hits / max(self._cache_hits + self._cache_misses, 1),
            "cache_size": len(self._cache),
            "suggestion_count": len(suggestions),
            "high_priority_count": sum(1 for s in suggestions if s.priority == "high"),
            "suggestions": [
                {
                    "title": s.title,
                    "category": s.category,
                    "priority": s.priority,
                }
                for s in suggestions[:5]  # Top 5
            ],
        }


class CostOptimizer:
    """
    Intelligent cost optimization for LLM usage.
    
    Works with ResponseCache for caching decisions and provides:
    - Cost estimation for queries
    - Model downgrade suggestions
    - Caching recommendations
    - Savings reports
    """
    
    # Model cost tiers (cheaper options for each tier)
    MODEL_TIERS = {
        "expensive": [
            "anthropic/claude-opus-4-5",
            "openai/gpt-4",
            "google/gemini-2.0-pro",
        ],
        "moderate": [
            "anthropic/claude-sonnet-4-5",
            "openai/gpt-4.1",
            "openai/gpt-4-turbo",
        ],
        "cheap": [
            "moonshot/kimi-k2.5",
            "google/gemini-2.0-flash",
            "deepseek/deepseek-chat",
            "anthropic/claude-haiku",
        ],
    }
    
    # Task types suitable for cheaper models
    SIMPLE_TASK_TYPES = [
        "chat", "simple_query", "greeting", "clarification",
        "translation", "summarization_short", "formatting",
    ]
    
    def __init__(
        self,
        tracker: TokenTracker,
        cache: "ResponseCache | None" = None,
        daily_budget_usd: float = 0,
        weekly_budget_usd: float = 0,
    ):
        """
        Initialize the cost optimizer.
        
        Args:
            tracker: Token tracker for usage data
            cache: Optional response cache
            daily_budget_usd: Daily budget in USD (0 = unlimited)
            weekly_budget_usd: Weekly budget in USD (0 = unlimited)
        """
        self.tracker = tracker
        self.cache = cache
        self.daily_budget_usd = daily_budget_usd
        self.weekly_budget_usd = weekly_budget_usd
    
    def should_cache(self, query: str, task_type: str = "") -> bool:
        """
        Determine if a query should be cached.
        
        Caching is recommended for:
        - Simple, factual queries
        - Repeated patterns
        - Non-time-sensitive requests
        
        Args:
            query: The query to evaluate
            task_type: Optional task type classification
            
        Returns:
            True if the query should be cached
        """
        # Don't cache if cache is disabled
        if self.cache is None:
            return False
        
        # Don't cache very short queries (likely incomplete)
        if len(query.strip()) < 10:
            return False
        
        # Don't cache time-sensitive queries
        time_keywords = ["now", "today", "current", "latest", "recent"]
        query_lower = query.lower()
        if any(kw in query_lower for kw in time_keywords):
            return False
        
        # Don't cache personal/context-dependent queries
        personal_keywords = ["my", "our", "we", "remember", "last time", "before"]
        if any(kw in query_lower for kw in personal_keywords):
            return False
        
        # Cache simple task types
        if task_type in self.SIMPLE_TASK_TYPES:
            return True
        
        # Default: cache factual/informational queries
        factual_keywords = ["what is", "how to", "explain", "define", "list"]
        return any(kw in query_lower for kw in factual_keywords)
    
    def suggest_model_downgrade(
        self,
        current_model: str,
        task_type: str = "",
        query: str = ""
    ) -> str | None:
        """
        Suggest a cheaper model if appropriate.
        
        Args:
            current_model: Currently selected model
            task_type: Task classification
            query: The query (for complexity analysis)
            
        Returns:
            Suggested cheaper model, or None if no downgrade recommended
        """
        # Check if current model is expensive
        is_expensive = current_model in self.MODEL_TIERS["expensive"]
        is_moderate = current_model in self.MODEL_TIERS["moderate"]
        
        if not (is_expensive or is_moderate):
            return None  # Already using cheap model
        
        # Check if task is simple
        if task_type in self.SIMPLE_TASK_TYPES:
            return self.MODEL_TIERS["cheap"][0]  # Suggest cheapest
        
        # Check query complexity
        if query:
            # Simple heuristics for complexity
            word_count = len(query.split())
            has_code = any(kw in query.lower() for kw in ["code", "function", "class", "implement"])
            has_complex = any(kw in query.lower() for kw in ["analyze", "compare", "evaluate", "critique"])
            
            # Simple queries can use cheaper models
            if word_count < 20 and not has_code and not has_complex:
                if is_expensive:
                    return self.MODEL_TIERS["moderate"][0]
                elif is_moderate:
                    return self.MODEL_TIERS["cheap"][0]
        
        return None
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """
        Estimate cost in USD for a request.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            model: Model identifier
            
        Returns:
            Estimated cost in USD
        """
        # Get model costs (per 1M tokens)
        costs = self.tracker.MODEL_COSTS.get(model, self.tracker.MODEL_COSTS["default"])
        
        input_cost = (prompt_tokens / 1_000_000) * costs["input"]
        output_cost = (completion_tokens / 1_000_000) * costs["output"]
        
        return input_cost + output_cost
    
    def estimate_query_cost(self, query: str, model: str) -> float:
        """
        Estimate cost for a query before execution.
        
        Args:
            query: The query text
            model: Model to use
            
        Returns:
            Estimated cost in USD
        """
        # Estimate tokens (rough: 4 chars per token)
        prompt_tokens = len(query) // 4 + 100  # Add overhead for system prompt
        completion_tokens = 500  # Average estimate
        
        return self.estimate_cost(prompt_tokens, completion_tokens, model)
    
    def get_optimization_suggestions(self) -> list[OptimizationSuggestion]:
        """
        Generate cost optimization suggestions.
        
        Returns:
            List of actionable suggestions
        """
        suggestions = []
        
        # Get usage stats
        daily_stats = self.tracker.get_daily_stats()
        weekly_stats = self.tracker.get_weekly_stats()
        
        # 1. Budget warnings
        if self.daily_budget_usd > 0:
            daily_cost = self.tracker.estimate_cost(daily_stats)
            daily_pct = daily_cost / self.daily_budget_usd
            
            if daily_pct >= 0.95:
                suggestions.append(OptimizationSuggestion(
                    category="budget",
                    title="Daily Budget Critical",
                    description=f"At {daily_pct*100:.0f}% of daily budget (${daily_cost:.2f}/${self.daily_budget_usd:.2f})",
                    potential_savings=0,
                    priority="high",
                    action="Consider pausing non-essential queries or switching to cheaper models",
                    estimated_usd=0,
                ))
            elif daily_pct >= 0.8:
                suggestions.append(OptimizationSuggestion(
                    category="budget",
                    title="Daily Budget Warning",
                    description=f"At {daily_pct*100:.0f}% of daily budget",
                    potential_savings=0,
                    priority="medium",
                    action="Monitor usage and consider model downgrades",
                    estimated_usd=0,
                ))
        
        # 2. Cache performance
        if self.cache:
            cache_stats = self.cache.get_stats()
            if cache_stats.total_hits + cache_stats.total_misses >= 10:
                hit_rate = cache_stats.hit_rate
                
                if hit_rate < 0.2:
                    suggestions.append(OptimizationSuggestion(
                        category="cache",
                        title="Low Cache Hit Rate",
                        description=f"Cache hit rate is only {hit_rate*100:.0f}%",
                        potential_savings=30,
                        priority="medium",
                        action="Review query patterns - consider caching more query types",
                        estimated_usd=self._estimate_cache_savings(weekly_stats, 0.3),
                    ))
                
                # Report savings
                if cache_stats.total_tokens_saved > 1000:
                    estimated_savings = (cache_stats.total_tokens_saved / 1_000_000) * 1.0
                    suggestions.append(OptimizationSuggestion(
                        category="cache",
                        title="Cache Savings Active",
                        description=f"Saved ~{cache_stats.total_tokens_saved:,} tokens via caching",
                        potential_savings=0,
                        priority="low",
                        action=f"Cache is working! Estimated savings: ${estimated_savings:.4f}",
                        estimated_usd=estimated_savings,
                    ))
        
        # 3. Model tier optimization
        tier_usage = weekly_stats.tier_usage
        total_tokens = sum(tier_usage.values()) or 1
        
        specialist_pct = tier_usage.get("specialist", 0) / total_tokens
        if specialist_pct > 0.25:
            savings = specialist_pct * self.tracker.estimate_cost(weekly_stats) * 0.5
            suggestions.append(OptimizationSuggestion(
                category="tier",
                title="High Specialist Model Usage",
                description=f"Specialist tier accounts for {specialist_pct*100:.0f}% of usage",
                potential_savings=50,
                priority="high",
                action="Route simple queries to daily_driver tier",
                estimated_usd=savings,
            ))
        
        # 4. Context size
        if weekly_stats.request_count > 5:
            avg_tokens = weekly_stats.tokens_per_request
            if avg_tokens > 4000:
                excess_tokens = (avg_tokens - 2000) * weekly_stats.request_count
                savings = (excess_tokens / 1_000_000) * 1.0
                suggestions.append(OptimizationSuggestion(
                    category="context",
                    title="Large Context Windows",
                    description=f"Average {avg_tokens:.0f} tokens per request",
                    potential_savings=40,
                    priority="medium",
                    action="Enable context compaction to reduce prompt sizes",
                    estimated_usd=savings,
                ))
        
        # Sort by estimated USD savings
        suggestions.sort(key=lambda s: s.estimated_usd, reverse=True)
        
        return suggestions
    
    def _estimate_cache_savings(self, stats: UsageStats, target_hit_rate: float) -> float:
        """Estimate potential savings from improved caching."""
        # If we could cache target_hit_rate of requests
        potential_cached = stats.request_count * target_hit_rate
        avg_tokens_per_request = stats.tokens_per_request if stats.request_count > 0 else 1000
        tokens_saved = potential_cached * avg_tokens_per_request
        
        return (tokens_saved / 1_000_000) * 1.0  # ~$1 per 1M tokens average
    
    def get_savings_report(self) -> dict[str, Any]:
        """
        Get a comprehensive savings report.
        
        Returns:
            Dictionary with savings data
        """
        weekly_stats = self.tracker.get_weekly_stats()
        weekly_cost = self.tracker.estimate_cost(weekly_stats)
        
        cache_savings = 0.0
        cache_stats = None
        if self.cache:
            cache_stats = self.cache.get_stats()
            cache_savings = (cache_stats.total_tokens_saved / 1_000_000) * 1.0
        
        return {
            "period": "weekly",
            "total_requests": weekly_stats.request_count,
            "total_tokens": weekly_stats.total_tokens,
            "estimated_cost_usd": round(weekly_cost, 4),
            "cache_enabled": self.cache is not None,
            "cache_hit_rate": cache_stats.hit_rate if cache_stats else 0,
            "cache_tokens_saved": cache_stats.total_tokens_saved if cache_stats else 0,
            "cache_savings_usd": round(cache_savings, 4),
            "total_savings_usd": round(cache_savings, 4),
            "suggestions": len(self.get_optimization_suggestions()),
        }
    
    def check_budget(self) -> tuple[bool, str | None]:
        """
        Check if within budget limits.
        
        Returns:
            Tuple of (within_budget, alert_message)
        """
        if self.daily_budget_usd <= 0 and self.weekly_budget_usd <= 0:
            return True, None  # No budget set
        
        daily_stats = self.tracker.get_daily_stats()
        daily_cost = self.tracker.estimate_cost(daily_stats)
        
        if self.daily_budget_usd > 0 and daily_cost >= self.daily_budget_usd:
            return False, f"Daily budget exceeded: ${daily_cost:.2f}/${self.daily_budget_usd:.2f}"
        
        if self.daily_budget_usd > 0 and daily_cost >= self.daily_budget_usd * 0.95:
            return True, f"Daily budget warning: ${daily_cost:.2f}/${self.daily_budget_usd:.2f} (95%)"
        
        weekly_stats = self.tracker.get_weekly_stats()
        weekly_cost = self.tracker.estimate_cost(weekly_stats)
        
        if self.weekly_budget_usd > 0 and weekly_cost >= self.weekly_budget_usd:
            return False, f"Weekly budget exceeded: ${weekly_cost:.2f}/${self.weekly_budget_usd:.2f}"
        
        if self.weekly_budget_usd > 0 and weekly_cost >= self.weekly_budget_usd * 0.95:
            return True, f"Weekly budget warning: ${weekly_cost:.2f}/${self.weekly_budget_usd:.2f} (95%)"
        
        return True, None
