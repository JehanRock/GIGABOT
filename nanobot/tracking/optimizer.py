"""
Self-optimization system for GigaBot.

Analyzes usage patterns and suggests optimizations:
- Tier downgrades for simple queries
- Response caching
- Context pruning
- Budget optimization
"""

from typing import Any
from dataclasses import dataclass, field

from nanobot.tracking.tokens import TokenTracker, UsageStats


@dataclass
class OptimizationSuggestion:
    """A suggestion for optimization."""
    category: str  # tier, cache, context, budget
    title: str
    description: str
    potential_savings: float  # Estimated token reduction %
    priority: str  # high, medium, low
    action: str  # What to do


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
