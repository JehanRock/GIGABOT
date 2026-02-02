"""
Auto-swarm trigger logic for GigaBot.

Determines when to automatically use swarm execution based on task complexity.
Inspired by Kimi K2.5's Agent Swarm capabilities.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.routing.classifier import ClassificationResult, TaskType
    from nanobot.config.schema import SwarmConfig


def should_use_swarm(
    message: str,
    classification: "ClassificationResult",
    config: "SwarmConfig | None" = None,
) -> tuple[bool, str]:
    """
    Determine if a task should use swarm execution.
    
    Uses multiple indicators to calculate a complexity score:
    - Explicit triggers (/swarm command)
    - Message length
    - Task classification tier
    - Task type
    - Keyword indicators
    
    Args:
        message: The user message.
        classification: Task classification result from router.
        config: Optional swarm configuration.
    
    Returns:
        Tuple of (should_use_swarm, suggested_pattern).
    """
    from nanobot.routing.classifier import TaskType
    
    # Check if swarm is enabled
    if config and not config.enabled:
        return False, ""
    
    # Check for auto-trigger setting
    auto_trigger = True
    complexity_threshold = 3
    if config:
        auto_trigger = getattr(config, 'auto_trigger', True)
        complexity_threshold = getattr(config, 'complexity_threshold', 3)
    
    if not auto_trigger:
        # Only trigger on explicit command
        if "/swarm" in message.lower():
            return True, auto_select_pattern(classification)
        return False, ""
    
    # Explicit triggers always activate swarm
    if "/swarm" in message.lower():
        return True, auto_select_pattern(classification)
    
    # Calculate complexity score
    complexity_score = 0
    
    # Long messages indicate complex requests
    if len(message) > 500:
        complexity_score += 1
    if len(message) > 1000:
        complexity_score += 1
    
    # Specialist tier indicates complex task
    if classification.tier == "specialist":
        complexity_score += 2
    
    # Certain task types are inherently complex
    complex_task_types = [
        TaskType.RESEARCH,
        TaskType.COMPLEX_ANALYSIS,
        TaskType.BRAINSTORM,
    ]
    if classification.task_type in complex_task_types:
        complexity_score += 2
    
    # Keyword indicators
    swarm_keywords = [
        "comprehensive",
        "multiple",
        "compare",
        "analyze all",
        "research",
        "investigate",
        "deep dive",
        "thorough",
        "systematic",
        "in-depth",
        "evaluate multiple",
        "pros and cons",
        "trade-offs",
    ]
    
    keyword_matches = sum(1 for kw in swarm_keywords if kw in message.lower())
    if keyword_matches >= 1:
        complexity_score += 1
    if keyword_matches >= 2:
        complexity_score += 1
    
    # Multi-step indicators
    multi_step_patterns = [
        "first", "then", "finally",
        "step 1", "step 2",
        "1.", "2.", "3.",
        "design and implement",
        "research and summarize",
        "analyze and recommend",
    ]
    if any(p in message.lower() for p in multi_step_patterns):
        complexity_score += 1
    
    # Determine if swarm should be used
    should_swarm = complexity_score >= complexity_threshold
    
    if should_swarm:
        pattern = auto_select_pattern(classification)
        return True, pattern
    
    return False, ""


def auto_select_pattern(classification: "ClassificationResult") -> str:
    """
    Auto-select the best swarm pattern based on task classification.
    
    Args:
        classification: Task classification result.
    
    Returns:
        Pattern name: "research", "code", "review", or "brainstorm".
    """
    from nanobot.routing.classifier import TaskType
    
    # Map task types to patterns
    pattern_map = {
        # Research pattern
        TaskType.RESEARCH: "research",
        TaskType.COMPLEX_ANALYSIS: "research",
        TaskType.SIMPLE_QUERY: "research",
        
        # Code pattern
        TaskType.CODE: "code",
        TaskType.IMPLEMENT: "code",
        TaskType.DEBUG: "code",
        TaskType.REFACTOR: "code",
        
        # Brainstorm pattern
        TaskType.BRAINSTORM: "brainstorm",
        TaskType.CREATIVE: "brainstorm",
        
        # Default fallbacks
        TaskType.CHAT: "research",
        TaskType.TASK_MANAGEMENT: "research",
        TaskType.UNKNOWN: "research",
    }
    
    return pattern_map.get(classification.task_type, "research")


def get_complexity_score(
    message: str,
    classification: "ClassificationResult",
) -> tuple[int, list[str]]:
    """
    Calculate complexity score with detailed breakdown.
    
    Useful for debugging and testing swarm trigger logic.
    
    Args:
        message: The user message.
        classification: Task classification result.
    
    Returns:
        Tuple of (score, list of factors that contributed).
    """
    from nanobot.routing.classifier import TaskType
    
    score = 0
    factors = []
    
    # Message length
    if len(message) > 500:
        score += 1
        factors.append(f"Long message ({len(message)} chars)")
    if len(message) > 1000:
        score += 1
        factors.append(f"Very long message ({len(message)} chars)")
    
    # Classification tier
    if classification.tier == "specialist":
        score += 2
        factors.append(f"Specialist tier")
    
    # Task type
    complex_types = [TaskType.RESEARCH, TaskType.COMPLEX_ANALYSIS, TaskType.BRAINSTORM]
    if classification.task_type in complex_types:
        score += 2
        factors.append(f"Complex task type: {classification.task_type.value}")
    
    # Keywords
    swarm_keywords = [
        "comprehensive", "multiple", "compare", "analyze all",
        "research", "investigate", "deep dive", "thorough",
    ]
    matched = [kw for kw in swarm_keywords if kw in message.lower()]
    if matched:
        score += min(len(matched), 2)
        factors.append(f"Keywords: {', '.join(matched)}")
    
    return score, factors
