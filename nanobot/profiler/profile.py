"""
Model Profile data structures for GigaBot's Model Profiler.

Defines the capability profile that results from interviewing a model,
including scores, strengths/weaknesses, and guardrail recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# Profile schema version for migrations
PROFILE_VERSION = "1.0"

# Task type to capability mapping
TASK_CAPABILITY_MAP = {
    "code": ["code_generation", "reasoning_depth", "instruction_following"],
    "implement": ["code_generation", "instruction_following", "context_utilization"],
    "debug": ["code_generation", "reasoning_depth", "context_utilization"],
    "refactor": ["code_generation", "reasoning_depth"],
    "research": ["context_utilization", "hallucination_resistance", "reasoning_depth"],
    "analysis": ["reasoning_depth", "context_utilization", "hallucination_resistance"],
    "creative": ["instruction_following"],  # Less constrained
    "review": ["reasoning_depth", "hallucination_resistance", "instruction_following"],
    "test": ["code_generation", "reasoning_depth", "instruction_following"],
    "design": ["reasoning_depth", "context_utilization"],
    "simple": ["instruction_following"],
    "chat": ["instruction_following", "hallucination_resistance"],
}

# Role to required capabilities mapping
ROLE_CAPABILITY_MAP = {
    "architect": {
        "required": ["reasoning_depth", "context_utilization"],
        "preferred": ["hallucination_resistance", "long_context_handling"],
        "weights": {"reasoning_depth": 0.3, "context_utilization": 0.25, 
                   "hallucination_resistance": 0.2, "long_context_handling": 0.15,
                   "instruction_following": 0.1},
    },
    "lead_dev": {
        "required": ["code_generation", "reasoning_depth"],
        "preferred": ["tool_calling_accuracy", "instruction_following"],
        "weights": {"code_generation": 0.3, "reasoning_depth": 0.25,
                   "tool_calling_accuracy": 0.2, "instruction_following": 0.15,
                   "context_utilization": 0.1},
    },
    "senior_dev": {
        "required": ["code_generation", "tool_calling_accuracy"],
        "preferred": ["instruction_following"],
        "weights": {"code_generation": 0.35, "tool_calling_accuracy": 0.25,
                   "instruction_following": 0.2, "reasoning_depth": 0.2},
    },
    "junior_dev": {
        "required": ["instruction_following", "code_generation"],
        "preferred": [],
        "weights": {"instruction_following": 0.4, "code_generation": 0.4,
                   "tool_calling_accuracy": 0.2},
    },
    "qa_engineer": {
        "required": ["reasoning_depth", "instruction_following"],
        "preferred": ["hallucination_resistance"],
        "weights": {"reasoning_depth": 0.3, "instruction_following": 0.3,
                   "hallucination_resistance": 0.2, "code_generation": 0.2},
    },
    "auditor": {
        "required": ["hallucination_resistance", "reasoning_depth"],
        "preferred": ["context_utilization"],
        "weights": {"hallucination_resistance": 0.35, "reasoning_depth": 0.3,
                   "context_utilization": 0.2, "instruction_following": 0.15},
    },
    "researcher": {
        "required": ["context_utilization", "hallucination_resistance"],
        "preferred": ["long_context_handling"],
        "weights": {"context_utilization": 0.3, "hallucination_resistance": 0.3,
                   "long_context_handling": 0.2, "reasoning_depth": 0.2},
    },
}


@dataclass
class CapabilityScores:
    """Capability scores from model evaluation (0.0 - 1.0)."""
    tool_calling_accuracy: float = 0.0      # Can format tool calls correctly
    instruction_following: float = 0.0       # Follows system prompts precisely
    context_utilization: float = 0.0         # Uses provided context effectively
    code_generation: float = 0.0             # Code quality and correctness
    reasoning_depth: float = 0.0             # Multi-step logical reasoning
    hallucination_resistance: float = 0.0    # Sticks to facts, admits uncertainty
    structured_output: float = 0.0           # JSON/format compliance
    long_context_handling: float = 0.0       # Performance with large contexts
    
    def get_score(self, capability: str) -> float:
        """Get score for a specific capability."""
        return getattr(self, capability, 0.0)
    
    def get_weighted_average(self, weights: dict[str, float]) -> float:
        """Calculate weighted average of specified capabilities."""
        total = 0.0
        weight_sum = 0.0
        for cap, weight in weights.items():
            score = self.get_score(cap)
            total += score * weight
            weight_sum += weight
        return total / weight_sum if weight_sum > 0 else 0.0
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "tool_calling_accuracy": self.tool_calling_accuracy,
            "instruction_following": self.instruction_following,
            "context_utilization": self.context_utilization,
            "code_generation": self.code_generation,
            "reasoning_depth": self.reasoning_depth,
            "hallucination_resistance": self.hallucination_resistance,
            "structured_output": self.structured_output,
            "long_context_handling": self.long_context_handling,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "CapabilityScores":
        """Create from dictionary."""
        return cls(
            tool_calling_accuracy=data.get("tool_calling_accuracy", 0.0),
            instruction_following=data.get("instruction_following", 0.0),
            context_utilization=data.get("context_utilization", 0.0),
            code_generation=data.get("code_generation", 0.0),
            reasoning_depth=data.get("reasoning_depth", 0.0),
            hallucination_resistance=data.get("hallucination_resistance", 0.0),
            structured_output=data.get("structured_output", 0.0),
            long_context_handling=data.get("long_context_handling", 0.0),
        )


@dataclass
class GuardrailRecommendations:
    """Recommended guardrails for a model based on evaluation."""
    needs_structured_output: bool = False   # Requires JSON mode
    needs_explicit_format: bool = False     # Needs format examples in prompt
    needs_tool_examples: bool = False       # Benefits from tool call examples
    max_reliable_context: int = 128000      # Tokens before performance degrades
    recommended_temperature: float = 0.7    # Optimal temperature
    tool_call_retry_limit: int = 3          # Safe retry count before escalation
    needs_step_by_step: bool = False        # Benefits from chain-of-thought
    avoid_parallel_tools: bool = False      # Struggles with multiple tool calls
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "needs_structured_output": self.needs_structured_output,
            "needs_explicit_format": self.needs_explicit_format,
            "needs_tool_examples": self.needs_tool_examples,
            "max_reliable_context": self.max_reliable_context,
            "recommended_temperature": self.recommended_temperature,
            "tool_call_retry_limit": self.tool_call_retry_limit,
            "needs_step_by_step": self.needs_step_by_step,
            "avoid_parallel_tools": self.avoid_parallel_tools,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuardrailRecommendations":
        """Create from dictionary."""
        return cls(
            needs_structured_output=data.get("needs_structured_output", False),
            needs_explicit_format=data.get("needs_explicit_format", False),
            needs_tool_examples=data.get("needs_tool_examples", False),
            max_reliable_context=data.get("max_reliable_context", 128000),
            recommended_temperature=data.get("recommended_temperature", 0.7),
            tool_call_retry_limit=data.get("tool_call_retry_limit", 3),
            needs_step_by_step=data.get("needs_step_by_step", False),
            avoid_parallel_tools=data.get("avoid_parallel_tools", False),
        )


@dataclass
class RuntimeStats:
    """Runtime statistics updated during model operation."""
    total_calls: int = 0
    successful_calls: int = 0
    tool_call_successes: int = 0
    tool_call_failures: int = 0
    total_tokens_used: int = 0
    average_latency_ms: float = 0.0
    common_errors: dict[str, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def tool_accuracy(self) -> float:
        """Calculate tool call accuracy."""
        total_tool_calls = self.tool_call_successes + self.tool_call_failures
        if total_tool_calls == 0:
            return 0.0
        return self.tool_call_successes / total_tool_calls
    
    def record_call(
        self,
        success: bool,
        tool_success: bool | None = None,
        tokens: int = 0,
        latency_ms: float = 0.0,
        error_type: str | None = None,
    ) -> None:
        """Record a model call outcome."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        
        if tool_success is not None:
            if tool_success:
                self.tool_call_successes += 1
            else:
                self.tool_call_failures += 1
        
        self.total_tokens_used += tokens
        
        # Update rolling average latency
        if latency_ms > 0:
            if self.average_latency_ms == 0:
                self.average_latency_ms = latency_ms
            else:
                # Exponential moving average
                self.average_latency_ms = 0.9 * self.average_latency_ms + 0.1 * latency_ms
        
        if error_type:
            self.common_errors[error_type] = self.common_errors.get(error_type, 0) + 1
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "tool_call_successes": self.tool_call_successes,
            "tool_call_failures": self.tool_call_failures,
            "total_tokens_used": self.total_tokens_used,
            "average_latency_ms": self.average_latency_ms,
            "common_errors": self.common_errors,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeStats":
        """Create from dictionary."""
        return cls(
            total_calls=data.get("total_calls", 0),
            successful_calls=data.get("successful_calls", 0),
            tool_call_successes=data.get("tool_call_successes", 0),
            tool_call_failures=data.get("tool_call_failures", 0),
            total_tokens_used=data.get("total_tokens_used", 0),
            average_latency_ms=data.get("average_latency_ms", 0.0),
            common_errors=data.get("common_errors", {}),
        )


@dataclass
class ModelProfile:
    """
    Complete capability profile for an AI model.
    
    Created through the interview process and updated during runtime
    to reflect actual performance characteristics.
    """
    model_id: str
    profile_version: str = PROFILE_VERSION
    interviewed_at: datetime = field(default_factory=datetime.now)
    interviewer_model: str = ""
    
    # Capability scores
    capabilities: CapabilityScores = field(default_factory=CapabilityScores)
    
    # Qualitative assessment
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    optimal_tasks: list[str] = field(default_factory=list)
    avoid_tasks: list[str] = field(default_factory=list)
    
    # Guardrail recommendations
    guardrails: GuardrailRecommendations = field(default_factory=GuardrailRecommendations)
    
    # Runtime statistics
    runtime_stats: RuntimeStats = field(default_factory=RuntimeStats)
    
    # Interview notes (from the interviewer model)
    interview_notes: str = ""
    
    def get_overall_score(self) -> float:
        """Calculate weighted average of all capability scores."""
        weights = {
            "tool_calling_accuracy": 0.15,
            "instruction_following": 0.15,
            "context_utilization": 0.15,
            "code_generation": 0.15,
            "reasoning_depth": 0.15,
            "hallucination_resistance": 0.15,
            "structured_output": 0.05,
            "long_context_handling": 0.05,
        }
        return self.capabilities.get_weighted_average(weights)
    
    def get_role_suitability(self, role_id: str) -> tuple[float, str]:
        """
        Calculate how suitable this model is for a role.
        
        Returns:
            Tuple of (suitability_score, reasoning).
        """
        if role_id not in ROLE_CAPABILITY_MAP:
            return 0.5, f"Unknown role: {role_id}"
        
        role_reqs = ROLE_CAPABILITY_MAP[role_id]
        
        # Check required capabilities
        for cap in role_reqs["required"]:
            score = self.capabilities.get_score(cap)
            if score < 0.6:
                return score, f"Insufficient {cap} ({score:.2f} < 0.6 required)"
        
        # Calculate weighted suitability
        suitability = self.capabilities.get_weighted_average(role_reqs["weights"])
        
        # Generate reasoning
        if suitability >= 0.8:
            reasoning = f"Excellent fit - strong in all required capabilities"
        elif suitability >= 0.7:
            reasoning = f"Good fit - meets requirements with some areas for improvement"
        elif suitability >= 0.6:
            reasoning = f"Adequate fit - meets minimum requirements"
        else:
            weak_caps = [
                cap for cap in role_reqs["required"]
                if self.capabilities.get_score(cap) < 0.7
            ]
            reasoning = f"Poor fit - weak in: {', '.join(weak_caps)}"
        
        return suitability, reasoning
    
    def is_suitable_for_task(self, task_type: str) -> tuple[bool, float, str]:
        """
        Check if model is suitable for a task type.
        
        Returns:
            Tuple of (is_suitable, confidence, reasoning).
        """
        # Check if task should be avoided
        if task_type in self.avoid_tasks:
            return False, 0.9, f"Task type '{task_type}' is in avoid list"
        
        # Check if task is optimal
        if task_type in self.optimal_tasks:
            return True, 0.9, f"Task type '{task_type}' is in optimal list"
        
        # Check capability requirements
        required_caps = TASK_CAPABILITY_MAP.get(task_type, ["instruction_following"])
        
        scores = [self.capabilities.get_score(cap) for cap in required_caps]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        
        is_suitable = avg_score >= 0.6
        reasoning = f"Average score {avg_score:.2f} for required capabilities"
        
        return is_suitable, avg_score, reasoning
    
    def get_guardrail_prompt(self) -> str:
        """
        Generate guardrail additions for this model's prompts.
        
        Returns additional instructions to help the model succeed.
        """
        lines = []
        
        if self.guardrails.needs_structured_output:
            lines.append("IMPORTANT: Always format your response as valid JSON when returning structured data.")
        
        if self.guardrails.needs_explicit_format:
            lines.append("Follow the exact format specified in the instructions. Do not deviate from the requested structure.")
        
        if self.guardrails.needs_tool_examples:
            lines.append("When calling tools, ensure all required parameters are provided with correct types.")
        
        if self.guardrails.needs_step_by_step:
            lines.append("Think through this step by step before providing your final answer.")
        
        if self.guardrails.avoid_parallel_tools:
            lines.append("Call tools one at a time, waiting for each result before proceeding.")
        
        # Add weakness-specific guidance
        if "hallucination" in self.weaknesses or "speculation" in self.weaknesses:
            lines.append("Only state facts you are certain about. If unsure, say 'I don't know' rather than guessing.")
        
        if "long_context" in self.weaknesses:
            lines.append("Focus on the most recent and relevant context when formulating your response.")
        
        return "\n".join(lines) if lines else ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "model_id": self.model_id,
            "profile_version": self.profile_version,
            "interviewed_at": self.interviewed_at.isoformat(),
            "interviewer_model": self.interviewer_model,
            "capabilities": self.capabilities.to_dict(),
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "optimal_tasks": self.optimal_tasks,
            "avoid_tasks": self.avoid_tasks,
            "guardrails": self.guardrails.to_dict(),
            "runtime_stats": self.runtime_stats.to_dict(),
            "interview_notes": self.interview_notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelProfile":
        """Create profile from dictionary."""
        interviewed_at = data.get("interviewed_at")
        if isinstance(interviewed_at, str):
            interviewed_at = datetime.fromisoformat(interviewed_at)
        elif interviewed_at is None:
            interviewed_at = datetime.now()
        
        return cls(
            model_id=data["model_id"],
            profile_version=data.get("profile_version", PROFILE_VERSION),
            interviewed_at=interviewed_at,
            interviewer_model=data.get("interviewer_model", ""),
            capabilities=CapabilityScores.from_dict(data.get("capabilities", {})),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            optimal_tasks=data.get("optimal_tasks", []),
            avoid_tasks=data.get("avoid_tasks", []),
            guardrails=GuardrailRecommendations.from_dict(data.get("guardrails", {})),
            runtime_stats=RuntimeStats.from_dict(data.get("runtime_stats", {})),
            interview_notes=data.get("interview_notes", ""),
        )
    
    def format_summary(self) -> str:
        """Format a human-readable summary of the profile."""
        lines = [
            f"Model Profile: {self.model_id}",
            "-" * (len(self.model_id) + 15),
            f"Overall Score: {self.get_overall_score():.2f}",
            "",
            "Capability Scores:",
        ]
        
        caps = self.capabilities.to_dict()
        for cap_name, score in caps.items():
            bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            display_name = cap_name.replace("_", " ").title()
            lines.append(f"  {display_name:25} {score:.2f} {bar}")
        
        if self.strengths:
            lines.append("")
            lines.append("Strengths:")
            for s in self.strengths[:5]:
                lines.append(f"  - {s}")
        
        if self.weaknesses:
            lines.append("")
            lines.append("Weaknesses:")
            for w in self.weaknesses[:5]:
                lines.append(f"  - {w}")
        
        if self.optimal_tasks:
            lines.append("")
            lines.append(f"Best for: {', '.join(self.optimal_tasks[:5])}")
        
        if self.avoid_tasks:
            lines.append(f"Avoid for: {', '.join(self.avoid_tasks[:5])}")
        
        # Runtime stats if available
        if self.runtime_stats.total_calls > 0:
            lines.append("")
            lines.append("Runtime Stats:")
            lines.append(f"  Total Calls: {self.runtime_stats.total_calls}")
            lines.append(f"  Success Rate: {self.runtime_stats.success_rate:.1%}")
            lines.append(f"  Tool Accuracy: {self.runtime_stats.tool_accuracy:.1%}")
        
        return "\n".join(lines)
