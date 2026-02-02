"""
Task classifier for tiered model routing.

Classifies incoming messages to determine the appropriate model tier.
Uses a combination of:
1. Keyword detection (fast path)
2. Pattern matching
3. Optional LLM-based classification
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Any


class TaskType(str, Enum):
    """Types of tasks for routing."""
    CHAT = "chat"
    SIMPLE_QUERY = "simple_query"
    TASK_MANAGEMENT = "task_management"
    CODE = "code"
    DEBUG = "debug"
    IMPLEMENT = "implement"
    REFACTOR = "refactor"
    BRAINSTORM = "brainstorm"
    CREATIVE = "creative"
    COMPLEX_ANALYSIS = "complex_analysis"
    RESEARCH = "research"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of task classification."""
    task_type: TaskType
    confidence: float  # 0.0 to 1.0
    tier: str  # Suggested tier name
    keywords_matched: list[str] = field(default_factory=list)
    reasoning: str = ""


# Keyword patterns for fast classification
TIER_KEYWORDS = {
    "daily_driver": {
        TaskType.CHAT: [
            r"\b(hi|hello|hey|thanks|thank you|bye|goodbye)\b",
            r"\b(how are you|what's up|how's it going)\b",
            r"^[^?]{1,50}$",  # Short statements without questions
        ],
        TaskType.SIMPLE_QUERY: [
            r"\b(what is|what's|who is|when|where|why|how)\b.*\?$",
            r"\b(tell me about|explain|describe)\b",
            r"\b(define|meaning of)\b",
        ],
        TaskType.TASK_MANAGEMENT: [
            r"\b(remind|schedule|set.*alarm|todo|task)\b",
            r"\b(add to list|create reminder)\b",
        ],
    },
    "coder": {
        TaskType.CODE: [
            r"\b(code|function|class|method|variable|api)\b",
            r"\b(python|javascript|typescript|rust|go|java)\b",
            r"\b(write|create|generate).*\b(script|program|code)\b",
        ],
        TaskType.DEBUG: [
            r"\b(debug|fix|error|bug|issue|broken|not working)\b",
            r"\b(traceback|exception|stack trace)\b",
            r"\b(why is.*not|doesn't work|failed)\b",
        ],
        TaskType.IMPLEMENT: [
            r"\b(implement|build|develop|create)\b.*\b(feature|system|module)\b",
            r"\b(add|integrate).*\b(functionality|support)\b",
        ],
        TaskType.REFACTOR: [
            r"\b(refactor|improve|optimize|clean up)\b.*\b(code|function|class)\b",
            r"\b(make.*better|simplify|restructure)\b",
        ],
    },
    "specialist": {
        TaskType.BRAINSTORM: [
            r"\b(brainstorm|ideas|suggest|possibilities)\b",
            r"\b(what.*options|alternatives|approaches)\b",
            r"\b(help me think|let's think about)\b",
        ],
        TaskType.CREATIVE: [
            r"\b(write|compose|draft).*\b(story|essay|article|poem)\b",
            r"\b(creative|imaginative|innovative)\b",
            r"\b(design|conceptualize|envision)\b",
        ],
        TaskType.COMPLEX_ANALYSIS: [
            r"\b(analyze|evaluate|assess|compare)\b.*\b(in depth|thoroughly|comprehensively)\b",
            r"\b(trade-?offs|pros and cons|advantages.*disadvantages)\b",
            r"\b(deep dive|comprehensive review)\b",
        ],
        TaskType.RESEARCH: [
            r"\b(research|investigate|study|explore)\b",
            r"\b(find.*information|gather.*data)\b",
            r"\b(literature review|state of the art)\b",
        ],
    },
}

# Compiled patterns for performance
_compiled_patterns: dict[str, dict[TaskType, list[re.Pattern]]] = {}


def _compile_patterns() -> None:
    """Compile regex patterns for performance."""
    global _compiled_patterns
    if _compiled_patterns:
        return
    
    for tier, task_patterns in TIER_KEYWORDS.items():
        _compiled_patterns[tier] = {}
        for task_type, patterns in task_patterns.items():
            _compiled_patterns[tier][task_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]


def classify_by_keywords(message: str) -> ClassificationResult:
    """
    Classify a message using keyword patterns.
    
    Args:
        message: The user message to classify.
    
    Returns:
        ClassificationResult with detected task type and tier.
    """
    _compile_patterns()
    
    best_match: ClassificationResult | None = None
    
    for tier, task_patterns in _compiled_patterns.items():
        for task_type, patterns in task_patterns.items():
            matched_keywords = []
            for pattern in patterns:
                match = pattern.search(message)
                if match:
                    matched_keywords.append(match.group(0))
            
            if matched_keywords:
                # Calculate confidence based on number of matches
                confidence = min(0.5 + (len(matched_keywords) * 0.15), 0.95)
                
                if best_match is None or confidence > best_match.confidence:
                    best_match = ClassificationResult(
                        task_type=task_type,
                        confidence=confidence,
                        tier=tier,
                        keywords_matched=matched_keywords,
                        reasoning=f"Matched keywords: {', '.join(matched_keywords[:3])}",
                    )
    
    if best_match:
        return best_match
    
    # Default to daily driver for unknown
    return ClassificationResult(
        task_type=TaskType.UNKNOWN,
        confidence=0.3,
        tier="daily_driver",
        reasoning="No keywords matched, using default tier",
    )


def classify_by_heuristics(message: str) -> ClassificationResult:
    """
    Classify using additional heuristics beyond keywords.
    
    Args:
        message: The user message to classify.
    
    Returns:
        ClassificationResult with detected task type and tier.
    """
    # Check message length - longer messages often need specialist
    if len(message) > 500:
        return ClassificationResult(
            task_type=TaskType.COMPLEX_ANALYSIS,
            confidence=0.6,
            tier="specialist",
            reasoning="Long message suggests complex request",
        )
    
    # Check for code blocks
    if "```" in message or message.count("\n") > 5:
        return ClassificationResult(
            task_type=TaskType.CODE,
            confidence=0.7,
            tier="coder",
            reasoning="Contains code blocks or multi-line content",
        )
    
    # Check for question complexity
    question_words = ["why", "how", "what if", "explain why"]
    complex_questions = sum(1 for w in question_words if w in message.lower())
    if complex_questions >= 2:
        return ClassificationResult(
            task_type=TaskType.COMPLEX_ANALYSIS,
            confidence=0.6,
            tier="specialist",
            reasoning="Multiple complex question patterns",
        )
    
    return ClassificationResult(
        task_type=TaskType.UNKNOWN,
        confidence=0.0,
        tier="daily_driver",
        reasoning="No heuristics matched",
    )


@dataclass
class TaskClassifier:
    """
    Task classifier that combines multiple classification methods.
    
    Classification priority:
    1. User override commands (/use coder, /use specialist)
    2. Keyword detection
    3. Heuristic analysis
    4. Optional LLM classification
    5. Fallback to default tier
    """
    
    use_llm: bool = False
    llm_provider: Any = None  # LLMProvider for advanced classification
    classifier_model: str = ""
    fallback_tier: str = "daily_driver"
    
    def classify(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """
        Classify a message to determine the appropriate model tier.
        
        Args:
            message: The user message to classify.
            context: Optional context (history, metadata, etc.)
        
        Returns:
            ClassificationResult with tier recommendation.
        """
        # Check for user override commands
        override_result = self._check_user_override(message)
        if override_result:
            return override_result
        
        # Keyword classification
        keyword_result = classify_by_keywords(message)
        if keyword_result.confidence >= 0.7:
            return keyword_result
        
        # Heuristic classification
        heuristic_result = classify_by_heuristics(message)
        if heuristic_result.confidence > keyword_result.confidence:
            return heuristic_result
        
        # Return best result or keyword result
        if keyword_result.confidence > 0:
            return keyword_result
        
        # LLM classification (if enabled and available)
        if self.use_llm and self.llm_provider:
            llm_result = self._classify_with_llm(message, context)
            if llm_result and llm_result.confidence > 0.5:
                return llm_result
        
        # Fallback
        return ClassificationResult(
            task_type=TaskType.UNKNOWN,
            confidence=0.3,
            tier=self.fallback_tier,
            reasoning="Using fallback tier",
        )
    
    def _check_user_override(self, message: str) -> ClassificationResult | None:
        """Check for user override commands like /use coder."""
        override_patterns = {
            r"^/use\s+(daily[_-]?driver|simple|basic)": "daily_driver",
            r"^/use\s+(coder|code|dev)": "coder",
            r"^/use\s+(specialist|expert|advanced)": "specialist",
        }
        
        for pattern, tier in override_patterns.items():
            if re.match(pattern, message, re.IGNORECASE):
                return ClassificationResult(
                    task_type=TaskType.UNKNOWN,
                    confidence=1.0,
                    tier=tier,
                    reasoning=f"User override: {tier}",
                )
        
        return None
    
    def _classify_with_llm(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult | None:
        """
        Use LLM to classify the task (more accurate but slower).
        
        Note: This runs synchronously using asyncio.run().
        For high-traffic scenarios, consider using async classification.
        """
        if not self.llm_provider or not self.classifier_model:
            return None
        
        import asyncio
        
        prompt = f"""Classify this user message into one of these tiers:
- daily_driver: Simple chat, basic questions, casual conversation
- coder: Code-related tasks, debugging, implementation, refactoring
- specialist: Complex analysis, brainstorming, creative writing, research

Message: "{message[:500]}"

Respond with ONLY a JSON object:
{{"tier": "<tier_name>", "task_type": "<type>", "confidence": <0.0-1.0>, "reasoning": "<brief reason>"}}

Valid task types: chat, simple_query, task_management, code, debug, implement, refactor, brainstorm, creative, complex_analysis, research"""

        try:
            # Run async chat synchronously
            async def _call_llm():
                response = await self.llm_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.classifier_model,
                    max_tokens=200,
                    temperature=0.1,
                )
                return response.content
            
            # Try to get existing event loop, otherwise create new one
            try:
                loop = asyncio.get_running_loop()
                # Already in async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _call_llm())
                    result = future.result(timeout=10)
            except RuntimeError:
                # No event loop, safe to use asyncio.run
                result = asyncio.run(_call_llm())
            
            if not result:
                return None
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', result)
            if json_match:
                data = json.loads(json_match.group())
                
                # Map task type string to enum
                task_type_str = data.get("task_type", "unknown")
                task_type = TaskType.UNKNOWN
                for tt in TaskType:
                    if tt.value == task_type_str:
                        task_type = tt
                        break
                
                return ClassificationResult(
                    task_type=task_type,
                    confidence=float(data.get("confidence", 0.7)),
                    tier=data.get("tier", self.fallback_tier),
                    reasoning=f"LLM: {data.get('reasoning', 'classified by LLM')}",
                )
                
        except Exception as e:
            # Log error but don't fail - fall back to other methods
            pass
        
        return None


def classify_task(
    message: str,
    classifier: TaskClassifier | None = None,
    context: dict[str, Any] | None = None,
) -> ClassificationResult:
    """
    Convenience function to classify a task.
    
    Args:
        message: The user message.
        classifier: Optional classifier instance.
        context: Optional context.
    
    Returns:
        ClassificationResult with tier recommendation.
    """
    if classifier is None:
        classifier = TaskClassifier()
    
    return classifier.classify(message, context)
