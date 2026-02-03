"""
Tool Advisor for GigaBot.

Provides adaptive tool selection based on:
- Historical success rates per model
- Tool performance tracking
- Alternative tool suggestions
- Learning from usage patterns
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.profiler.profile import ModelProfile


@dataclass
class ToolUsageStats:
    """Statistics for a tool-model combination."""
    tool_name: str
    model_id: str
    total_calls: int = 0
    successful_calls: int = 0
    total_latency_ms: float = 0.0
    last_used: datetime = field(default_factory=datetime.now)
    common_errors: dict[str, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.5  # Neutral for unused combinations
        return self.successful_calls / self.total_calls
    
    @property
    def average_latency(self) -> float:
        """Calculate average latency in ms."""
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls
    
    def record_call(
        self,
        success: bool,
        latency_ms: float = 0.0,
        error: str = "",
    ) -> None:
        """Record a tool call outcome."""
        self.total_calls += 1
        self.last_used = datetime.now()
        
        if success:
            self.successful_calls += 1
            self.total_latency_ms += latency_ms
        elif error:
            # Categorize error
            error_key = self._categorize_error(error)
            self.common_errors[error_key] = self.common_errors.get(error_key, 0) + 1
    
    def _categorize_error(self, error: str) -> str:
        """Categorize an error for tracking."""
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            return "timeout"
        if "permission" in error_lower or "denied" in error_lower:
            return "permission"
        if "not found" in error_lower:
            return "not_found"
        if "invalid" in error_lower or "missing" in error_lower:
            return "invalid_params"
        if "rate" in error_lower or "limit" in error_lower:
            return "rate_limit"
        return "other"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "model_id": self.model_id,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "total_latency_ms": self.total_latency_ms,
            "last_used": self.last_used.isoformat(),
            "common_errors": self.common_errors,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolUsageStats":
        """Create from dictionary."""
        last_used = data.get("last_used")
        if isinstance(last_used, str):
            last_used = datetime.fromisoformat(last_used)
        else:
            last_used = datetime.now()
        
        return cls(
            tool_name=data["tool_name"],
            model_id=data["model_id"],
            total_calls=data.get("total_calls", 0),
            successful_calls=data.get("successful_calls", 0),
            total_latency_ms=data.get("total_latency_ms", 0.0),
            last_used=last_used,
            common_errors=data.get("common_errors", {}),
        )


@dataclass
class ToolRecommendation:
    """A recommendation for tool usage."""
    tool_name: str
    confidence: float
    reason: str
    alternative: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class AdvisorConfig:
    """Configuration for the ToolAdvisor."""
    # Thresholds for recommendations
    min_calls_for_confidence: int = 5  # Min calls before using actual success rate
    default_confidence: float = 0.7  # Confidence when not enough data
    error_warning_threshold: int = 3  # Error count before warning
    error_confidence_penalty: float = 0.8  # Multiply confidence by this when errors detected
    low_tool_accuracy_penalty: float = 0.9  # Penalty for models with low tool accuracy
    tool_accuracy_threshold: float = 0.7  # Below this, apply penalty
    suggest_alternative_threshold: float = 0.5  # Confidence below this suggests alternative
    
    # Save settings
    auto_save_interval: int = 50  # Save stats every N calls


# Tool equivalence groups - tools that can substitute for each other
TOOL_ALTERNATIVES = {
    "read_file": ["list_dir"],  # If file read fails, maybe list dir first
    "edit_file": ["write_file"],  # If edit fails, try full write
    "web_search": ["web_fetch"],  # If search fails, try direct fetch
    "exec": ["process"],  # Different process execution methods
}


class ToolAdvisor:
    """
    Advises on tool selection based on historical performance.
    
    Features:
    - Track success rates per model-tool combination
    - Suggest alternatives when tools fail
    - Learn which models work best with which tools
    - Provide usage warnings based on patterns
    """
    
    def __init__(
        self,
        storage_path: Path | None = None,
        config: AdvisorConfig | None = None,
    ):
        """
        Initialize the tool advisor.
        
        Args:
            storage_path: Path to store usage statistics.
            config: Configuration for thresholds and behavior.
        """
        self.storage_path = storage_path
        self.config = config or AdvisorConfig()
        self._stats: dict[str, ToolUsageStats] = {}  # key: f"{model_id}:{tool_name}"
        
        if storage_path:
            self._load_stats()
    
    def _get_key(self, model_id: str, tool_name: str) -> str:
        """Get storage key for a model-tool combination."""
        return f"{model_id}:{tool_name}"
    
    def _get_stats(self, model_id: str, tool_name: str) -> ToolUsageStats:
        """Get or create stats for a model-tool combination."""
        key = self._get_key(model_id, tool_name)
        if key not in self._stats:
            self._stats[key] = ToolUsageStats(
                tool_name=tool_name,
                model_id=model_id,
            )
        return self._stats[key]
    
    def record_tool_call(
        self,
        model_id: str,
        tool_name: str,
        success: bool,
        latency_ms: float = 0.0,
        error: str = "",
    ) -> None:
        """
        Record a tool call outcome.
        
        Args:
            model_id: Model that made the call.
            tool_name: Tool that was called.
            success: Whether the call succeeded.
            latency_ms: Execution time in milliseconds.
            error: Error message if failed.
        """
        stats = self._get_stats(model_id, tool_name)
        stats.record_call(success, latency_ms, error)
        
        # Periodically save
        total_calls = sum(s.total_calls for s in self._stats.values())
        if total_calls > 0 and total_calls % self.config.auto_save_interval == 0:
            self._save_stats()
    
    def get_recommendation(
        self,
        model_id: str,
        tool_name: str,
        model_profile: "ModelProfile | None" = None,
    ) -> ToolRecommendation:
        """
        Get recommendation for using a tool with a model.
        
        Args:
            model_id: Model that will call the tool.
            tool_name: Tool to be called.
            model_profile: Optional model profile for capability info.
        
        Returns:
            ToolRecommendation with confidence and warnings.
        """
        cfg = self.config
        stats = self._get_stats(model_id, tool_name)
        warnings = []
        alternative = None
        
        # Base confidence on success rate
        if stats.total_calls >= cfg.min_calls_for_confidence:
            confidence = stats.success_rate
        else:
            # Not enough data - use default confidence
            confidence = cfg.default_confidence
        
        # Check for common error patterns
        if stats.common_errors:
            most_common_error = max(stats.common_errors, key=stats.common_errors.get)
            error_count = stats.common_errors[most_common_error]
            
            if error_count > cfg.error_warning_threshold:
                warnings.append(f"Frequent '{most_common_error}' errors with this tool")
                confidence *= cfg.error_confidence_penalty
        
        # Check model profile for tool-related guardrails
        if model_profile:
            if model_profile.guardrails.avoid_parallel_tools:
                warnings.append("Model struggles with parallel tool calls")
            
            if model_profile.guardrails.needs_tool_examples:
                warnings.append("Model benefits from tool examples in prompt")
            
            # Check tool calling accuracy
            if model_profile.capabilities.tool_calling_accuracy < cfg.tool_accuracy_threshold:
                confidence *= cfg.low_tool_accuracy_penalty
                warnings.append("Model has lower tool calling accuracy")
        
        # Suggest alternative if confidence is low
        if confidence < cfg.suggest_alternative_threshold and tool_name in TOOL_ALTERNATIVES:
            alternatives = TOOL_ALTERNATIVES[tool_name]
            # Find best alternative
            for alt in alternatives:
                alt_stats = self._get_stats(model_id, alt)
                if alt_stats.success_rate > confidence or alt_stats.total_calls < cfg.min_calls_for_confidence:
                    alternative = alt
                    break
        
        # Generate reason
        if stats.total_calls == 0:
            reason = "No usage history - proceeding with caution"
        elif confidence >= 0.8:
            reason = f"Good track record ({stats.success_rate:.0%} success rate)"
        elif confidence >= 0.6:
            reason = f"Acceptable success rate ({stats.success_rate:.0%})"
        else:
            reason = f"Low success rate ({stats.success_rate:.0%}) - consider alternative"
        
        return ToolRecommendation(
            tool_name=tool_name,
            confidence=confidence,
            reason=reason,
            alternative=alternative,
            warnings=warnings,
        )
    
    def get_best_model_for_tool(
        self,
        tool_name: str,
        available_models: list[str],
        min_calls: int = 3,
    ) -> tuple[str | None, float]:
        """
        Find the best model for a specific tool.
        
        Args:
            tool_name: Tool to find best model for.
            available_models: Models to consider.
            min_calls: Minimum calls required for consideration.
        
        Returns:
            Tuple of (best_model_id, success_rate).
        """
        best_model = None
        best_rate = 0.0
        
        for model_id in available_models:
            stats = self._get_stats(model_id, tool_name)
            
            if stats.total_calls >= min_calls:
                if stats.success_rate > best_rate:
                    best_rate = stats.success_rate
                    best_model = model_id
        
        return best_model, best_rate
    
    def get_tool_leaderboard(
        self,
        tool_name: str,
        top_n: int = 5,
    ) -> list[tuple[str, float, int]]:
        """
        Get top models for a tool by success rate.
        
        Args:
            tool_name: Tool to get leaderboard for.
            top_n: Number of top models to return.
        
        Returns:
            List of (model_id, success_rate, total_calls) tuples.
        """
        candidates = []
        
        for key, stats in self._stats.items():
            if stats.tool_name == tool_name and stats.total_calls > 0:
                candidates.append((
                    stats.model_id,
                    stats.success_rate,
                    stats.total_calls,
                ))
        
        # Sort by success rate, then by total calls
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        return candidates[:top_n]
    
    def get_model_tool_matrix(
        self,
        model_ids: list[str] | None = None,
        tool_names: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Get success rate matrix for models vs tools.
        
        Args:
            model_ids: Models to include (None = all tracked).
            tool_names: Tools to include (None = all tracked).
        
        Returns:
            Nested dict of model_id -> tool_name -> success_rate.
        """
        matrix: dict[str, dict[str, float]] = {}
        
        for key, stats in self._stats.items():
            if model_ids and stats.model_id not in model_ids:
                continue
            if tool_names and stats.tool_name not in tool_names:
                continue
            
            if stats.model_id not in matrix:
                matrix[stats.model_id] = {}
            
            matrix[stats.model_id][stats.tool_name] = stats.success_rate
        
        return matrix
    
    def get_problematic_combinations(
        self,
        min_calls: int = 5,
        max_success_rate: float = 0.5,
    ) -> list[tuple[str, str, float, int]]:
        """
        Find model-tool combinations with low success rates.
        
        Args:
            min_calls: Minimum calls to consider.
            max_success_rate: Maximum success rate to flag.
        
        Returns:
            List of (model_id, tool_name, success_rate, total_calls) tuples.
        """
        problematic = []
        
        for stats in self._stats.values():
            if stats.total_calls >= min_calls and stats.success_rate <= max_success_rate:
                problematic.append((
                    stats.model_id,
                    stats.tool_name,
                    stats.success_rate,
                    stats.total_calls,
                ))
        
        # Sort by success rate ascending (worst first)
        problematic.sort(key=lambda x: x[2])
        
        return problematic
    
    def _save_stats(self) -> None:
        """Save statistics to storage."""
        if not self.storage_path:
            return
        
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "stats": {
                    key: stats.to_dict()
                    for key, stats in self._stats.items()
                },
            }
            
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save tool advisor stats: {e}")
    
    def _load_stats(self) -> None:
        """Load statistics from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
            
            for key, stats_data in data.get("stats", {}).items():
                self._stats[key] = ToolUsageStats.from_dict(stats_data)
            
            logger.debug(f"Loaded {len(self._stats)} tool usage records")
            
        except Exception as e:
            logger.warning(f"Failed to load tool advisor stats: {e}")
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        total_calls = sum(s.total_calls for s in self._stats.values())
        total_successes = sum(s.successful_calls for s in self._stats.values())
        
        unique_models = set(s.model_id for s in self._stats.values())
        unique_tools = set(s.tool_name for s in self._stats.values())
        
        return {
            "total_combinations": len(self._stats),
            "unique_models": len(unique_models),
            "unique_tools": len(unique_tools),
            "total_calls": total_calls,
            "overall_success_rate": total_successes / total_calls if total_calls > 0 else 0.0,
        }
