"""
Token usage tracking for GigaBot.

Tracks:
- Session tokens
- Daily/weekly totals
- Budget management
- Cost estimation
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field


@dataclass
class UsageStats:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    
    # By tier
    tier_usage: dict[str, int] = field(default_factory=dict)
    
    # By model
    model_usage: dict[str, int] = field(default_factory=dict)
    
    # Timing
    start_time: float = field(default_factory=time.time)
    
    @property
    def tokens_per_request(self) -> float:
        """Average tokens per request."""
        if self.request_count == 0:
            return 0
        return self.total_tokens / self.request_count


@dataclass
class BudgetAlert:
    """Budget alert notification."""
    level: str  # "warning", "critical"
    message: str
    current_usage: int
    budget: int
    percentage: float


class TokenTracker:
    """
    Tracks token usage across sessions.
    
    Features:
    - Real-time usage tracking
    - Daily/weekly budgets
    - Cost estimation
    - Usage alerts
    """
    
    # Estimated costs per 1M tokens (USD)
    MODEL_COSTS = {
        # Daily driver tier
        "moonshot/kimi-k2.5": {"input": 0.10, "output": 0.30},
        "google/gemini-2.0-flash": {"input": 0.075, "output": 0.30},
        
        # Coder tier
        "anthropic/claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
        "openai/gpt-4.1": {"input": 2.50, "output": 10.00},
        
        # Specialist tier
        "anthropic/claude-opus-4-5": {"input": 15.00, "output": 75.00},
        "google/gemini-2.0-pro": {"input": 1.25, "output": 5.00},
        
        # Default
        "default": {"input": 1.00, "output": 3.00},
    }
    
    def __init__(
        self,
        storage_path: Path | None = None,
        daily_budget: int = 0,  # 0 = unlimited
        weekly_budget: int = 0,
        alert_threshold: float = 0.8,
    ):
        self.storage_path = storage_path
        self.daily_budget = daily_budget
        self.weekly_budget = weekly_budget
        self.alert_threshold = alert_threshold
        
        # Current session
        self._session = UsageStats()
        
        # Historical data
        self._daily: dict[str, UsageStats] = {}
        self._weekly: dict[str, UsageStats] = {}
        
        # Alerts
        self._alerts: list[BudgetAlert] = []
        
        if storage_path:
            self._load()
    
    def track(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "",
        tier: str = "",
    ) -> None:
        """
        Track token usage from a request.
        
        Args:
            prompt_tokens: Input tokens used.
            completion_tokens: Output tokens used.
            model: Model identifier.
            tier: Tier used (daily_driver, coder, specialist).
        """
        total = prompt_tokens + completion_tokens
        
        # Update session stats
        self._session.prompt_tokens += prompt_tokens
        self._session.completion_tokens += completion_tokens
        self._session.total_tokens += total
        self._session.request_count += 1
        
        if tier:
            self._session.tier_usage[tier] = self._session.tier_usage.get(tier, 0) + total
        
        if model:
            self._session.model_usage[model] = self._session.model_usage.get(model, 0) + total
        
        # Update daily stats
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self._daily:
            self._daily[today] = UsageStats()
        
        daily = self._daily[today]
        daily.prompt_tokens += prompt_tokens
        daily.completion_tokens += completion_tokens
        daily.total_tokens += total
        daily.request_count += 1
        
        if tier:
            daily.tier_usage[tier] = daily.tier_usage.get(tier, 0) + total
        if model:
            daily.model_usage[model] = daily.model_usage.get(model, 0) + total
        
        # Check budgets
        self._check_budgets()
        
        # Save periodically
        if self._session.request_count % 10 == 0:
            self._save()
    
    def _check_budgets(self) -> None:
        """Check budget limits and generate alerts."""
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self._daily.get(today, UsageStats())
        
        # Daily budget check
        if self.daily_budget > 0:
            usage_pct = daily.total_tokens / self.daily_budget
            
            if usage_pct >= 1.0:
                self._alerts.append(BudgetAlert(
                    level="critical",
                    message="Daily budget exceeded",
                    current_usage=daily.total_tokens,
                    budget=self.daily_budget,
                    percentage=usage_pct,
                ))
            elif usage_pct >= self.alert_threshold:
                self._alerts.append(BudgetAlert(
                    level="warning",
                    message=f"Daily budget at {usage_pct*100:.0f}%",
                    current_usage=daily.total_tokens,
                    budget=self.daily_budget,
                    percentage=usage_pct,
                ))
        
        # Weekly budget check
        if self.weekly_budget > 0:
            weekly_total = self._get_weekly_total()
            usage_pct = weekly_total / self.weekly_budget
            
            if usage_pct >= 1.0:
                self._alerts.append(BudgetAlert(
                    level="critical",
                    message="Weekly budget exceeded",
                    current_usage=weekly_total,
                    budget=self.weekly_budget,
                    percentage=usage_pct,
                ))
            elif usage_pct >= self.alert_threshold:
                self._alerts.append(BudgetAlert(
                    level="warning",
                    message=f"Weekly budget at {usage_pct*100:.0f}%",
                    current_usage=weekly_total,
                    budget=self.weekly_budget,
                    percentage=usage_pct,
                ))
    
    def _get_weekly_total(self) -> int:
        """Get total tokens for the current week."""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        
        total = 0
        for i in range(7):
            date = week_start + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            if date_str in self._daily:
                total += self._daily[date_str].total_tokens
        
        return total
    
    def get_session_stats(self) -> UsageStats:
        """Get current session statistics."""
        return self._session
    
    def get_daily_stats(self, date: datetime | None = None) -> UsageStats:
        """Get statistics for a specific day."""
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        return self._daily.get(date_str, UsageStats())
    
    def get_weekly_stats(self) -> UsageStats:
        """Get aggregated weekly statistics."""
        stats = UsageStats()
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        
        for i in range(7):
            date = week_start + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            if date_str in self._daily:
                daily = self._daily[date_str]
                stats.prompt_tokens += daily.prompt_tokens
                stats.completion_tokens += daily.completion_tokens
                stats.total_tokens += daily.total_tokens
                stats.request_count += daily.request_count
                
                for tier, count in daily.tier_usage.items():
                    stats.tier_usage[tier] = stats.tier_usage.get(tier, 0) + count
                
                for model, count in daily.model_usage.items():
                    stats.model_usage[model] = stats.model_usage.get(model, 0) + count
        
        return stats
    
    def estimate_cost(self, stats: UsageStats | None = None) -> float:
        """
        Estimate cost for given usage stats.
        
        Returns:
            Estimated cost in USD.
        """
        stats = stats or self._session
        total_cost = 0.0
        
        for model, tokens in stats.model_usage.items():
            costs = self.MODEL_COSTS.get(model, self.MODEL_COSTS["default"])
            
            # Estimate 70% input, 30% output (rough average)
            input_tokens = tokens * 0.7
            output_tokens = tokens * 0.3
            
            cost = (input_tokens / 1_000_000 * costs["input"] +
                    output_tokens / 1_000_000 * costs["output"])
            total_cost += cost
        
        return total_cost
    
    def get_alerts(self, clear: bool = True) -> list[BudgetAlert]:
        """Get pending alerts."""
        alerts = self._alerts.copy()
        if clear:
            self._alerts.clear()
        return alerts
    
    def get_summary(self) -> dict[str, Any]:
        """Get usage summary."""
        session = self._session
        daily = self.get_daily_stats()
        weekly = self.get_weekly_stats()
        
        return {
            "session": {
                "tokens": session.total_tokens,
                "requests": session.request_count,
                "cost_estimate": f"${self.estimate_cost(session):.4f}",
            },
            "today": {
                "tokens": daily.total_tokens,
                "requests": daily.request_count,
                "budget_used": f"{daily.total_tokens / max(self.daily_budget, 1) * 100:.1f}%" if self.daily_budget else "N/A",
            },
            "week": {
                "tokens": weekly.total_tokens,
                "requests": weekly.request_count,
                "cost_estimate": f"${self.estimate_cost(weekly):.4f}",
            },
            "tier_breakdown": session.tier_usage,
        }
    
    def reset_session(self) -> None:
        """Reset session statistics."""
        self._session = UsageStats()
    
    def _save(self) -> None:
        """Save tracking data to storage."""
        if not self.storage_path:
            return
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "daily": {
                date: {
                    "prompt_tokens": stats.prompt_tokens,
                    "completion_tokens": stats.completion_tokens,
                    "total_tokens": stats.total_tokens,
                    "request_count": stats.request_count,
                    "tier_usage": stats.tier_usage,
                    "model_usage": stats.model_usage,
                }
                for date, stats in self._daily.items()
            },
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def _load(self) -> None:
        """Load tracking data from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
            
            for date, stats_data in data.get("daily", {}).items():
                self._daily[date] = UsageStats(
                    prompt_tokens=stats_data.get("prompt_tokens", 0),
                    completion_tokens=stats_data.get("completion_tokens", 0),
                    total_tokens=stats_data.get("total_tokens", 0),
                    request_count=stats_data.get("request_count", 0),
                    tier_usage=stats_data.get("tier_usage", {}),
                    model_usage=stats_data.get("model_usage", {}),
                )
        except Exception:
            pass  # Start fresh on error
