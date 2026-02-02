"""
Context window guard for GigaBot.

Prevents context overflow by auto-summarizing when approaching token limits.
Uses tiktoken for accurate token counting when available.
"""

import asyncio
from typing import Any
from dataclasses import dataclass

from loguru import logger

# Try to import tiktoken for accurate counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    tiktoken = None


@dataclass
class CompactionResult:
    """Result of compaction operation."""
    original_tokens: int
    compacted_tokens: int
    messages_removed: int
    summary_added: bool


class ContextGuard:
    """
    Guards against context overflow by monitoring token usage
    and compacting history when necessary.
    
    Features:
    - Token counting (tiktoken if available, estimation fallback)
    - Configurable threshold for compaction trigger
    - Preserves recent messages and important tool results
    - Uses LLM to summarize older conversation
    """
    
    # Default model for token counting (affects tiktoken encoding)
    DEFAULT_MODEL = "gpt-4"
    
    # Approximate tokens per character for estimation
    CHARS_PER_TOKEN = 4
    
    def __init__(
        self,
        max_tokens: int = 128000,
        threshold: float = 0.8,
        preserve_recent: int = 10,
        preserve_system: bool = True,
        model: str = "",
    ):
        """
        Initialize the context guard.
        
        Args:
            max_tokens: Maximum context window size.
            threshold: Compaction trigger (0.0-1.0, e.g., 0.8 = 80%).
            preserve_recent: Number of recent messages to preserve.
            preserve_system: Whether to preserve system messages.
            model: Model name for token counting (affects encoding).
        """
        self.max_tokens = max_tokens
        self.threshold = threshold
        self.preserve_recent = preserve_recent
        self.preserve_system = preserve_system
        self.model = model or self.DEFAULT_MODEL
        
        # Token counting stats
        self._last_count = 0
        self._compaction_count = 0
        
        # Get tiktoken encoder if available
        self._encoder = None
        if TIKTOKEN_AVAILABLE:
            try:
                self._encoder = tiktoken.encoding_for_model(self.model)
            except KeyError:
                # Fall back to cl100k_base for unknown models
                self._encoder = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        Count tokens in a list of messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
        
        Returns:
            Estimated token count.
        """
        if self._encoder:
            return self._count_tokens_tiktoken(messages)
        return self._count_tokens_estimate(messages)
    
    def _count_tokens_tiktoken(self, messages: list[dict[str, Any]]) -> int:
        """Count tokens using tiktoken."""
        total = 0
        for message in messages:
            # Count message overhead (role, separators)
            total += 4  # Approximate overhead per message
            
            # Count content
            content = message.get("content", "")
            if content:
                total += len(self._encoder.encode(content))
            
            # Count tool calls if present
            tool_calls = message.get("tool_calls", [])
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    total += len(self._encoder.encode(func.get("name", "")))
                    total += len(self._encoder.encode(func.get("arguments", "")))
        
        return total
    
    def _count_tokens_estimate(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count without tiktoken."""
        total = 0
        for message in messages:
            content = message.get("content", "")
            if content:
                total += len(content) // self.CHARS_PER_TOKEN
            
            # Tool calls
            tool_calls = message.get("tool_calls", [])
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    total += len(func.get("name", "")) // self.CHARS_PER_TOKEN
                    total += len(func.get("arguments", "")) // self.CHARS_PER_TOKEN
            
            # Overhead per message
            total += 4
        
        return total
    
    def needs_compaction(self, messages: list[dict[str, Any]]) -> bool:
        """
        Check if compaction is needed.
        
        Args:
            messages: Current message list.
        
        Returns:
            True if token count exceeds threshold.
        """
        self._last_count = self.count_tokens(messages)
        threshold_tokens = int(self.max_tokens * self.threshold)
        return self._last_count > threshold_tokens
    
    async def compact(
        self,
        messages: list[dict[str, Any]],
        provider: Any,
    ) -> tuple[list[dict[str, Any]], CompactionResult]:
        """
        Compact messages by summarizing older content.
        
        Args:
            messages: Current message list.
            provider: LLM provider for summarization.
        
        Returns:
            Tuple of (compacted messages, result info).
        """
        original_count = self.count_tokens(messages)
        
        if not self.needs_compaction(messages):
            return messages, CompactionResult(
                original_tokens=original_count,
                compacted_tokens=original_count,
                messages_removed=0,
                summary_added=False,
            )
        
        logger.info(f"Context compaction triggered ({original_count} tokens)")
        
        # Separate messages to preserve vs. summarize
        system_messages = []
        to_summarize = []
        to_preserve = []
        
        for i, msg in enumerate(messages):
            if msg.get("role") == "system" and self.preserve_system:
                system_messages.append(msg)
            elif i >= len(messages) - self.preserve_recent:
                to_preserve.append(msg)
            else:
                to_summarize.append(msg)
        
        if not to_summarize:
            # Nothing to summarize
            return messages, CompactionResult(
                original_tokens=original_count,
                compacted_tokens=original_count,
                messages_removed=0,
                summary_added=False,
            )
        
        # Generate summary of older messages
        summary = await self._generate_summary(to_summarize, provider)
        
        # Build new message list
        new_messages = system_messages.copy()
        
        if summary:
            new_messages.append({
                "role": "system",
                "content": f"[Context Summary]\n{summary}\n[End Summary]",
            })
        
        new_messages.extend(to_preserve)
        
        # Count new tokens
        new_count = self.count_tokens(new_messages)
        self._compaction_count += 1
        
        logger.info(
            f"Compacted: {original_count} -> {new_count} tokens "
            f"(removed {len(to_summarize)} messages)"
        )
        
        return new_messages, CompactionResult(
            original_tokens=original_count,
            compacted_tokens=new_count,
            messages_removed=len(to_summarize),
            summary_added=bool(summary),
        )
    
    async def _generate_summary(
        self,
        messages: list[dict[str, Any]],
        provider: Any,
    ) -> str:
        """Generate a summary of messages."""
        if not messages:
            return ""
        
        # Build conversation text
        conversation = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if content:
                conversation.append(f"{role.upper()}: {content[:500]}")
            
            # Note tool calls
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        func = tc.get("function", {})
                        conversation.append(
                            f"[Tool: {func.get('name', 'unknown')}]"
                        )
        
        # Limit conversation text
        conversation_text = "\n".join(conversation)[:4000]
        
        prompt = f"""Summarize this conversation history concisely. Focus on:
1. Key topics discussed
2. Important decisions or conclusions
3. Any tasks or actions taken
4. Context needed for continuing the conversation

Conversation:
{conversation_text}

Provide a brief summary (max 300 words):"""

        try:
            response = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )
            return response.content or ""
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Fallback: simple truncation note
            return f"[Previous conversation: {len(messages)} messages truncated for context limits]"
    
    async def compact_if_needed(
        self,
        messages: list[dict[str, Any]],
        provider: Any,
    ) -> list[dict[str, Any]]:
        """
        Convenience method to compact only if needed.
        
        Args:
            messages: Current message list.
            provider: LLM provider for summarization.
        
        Returns:
            Original or compacted messages.
        """
        if self.needs_compaction(messages):
            new_messages, _ = await self.compact(messages, provider)
            return new_messages
        return messages
    
    def get_stats(self) -> dict[str, Any]:
        """Get context guard statistics."""
        return {
            "max_tokens": self.max_tokens,
            "threshold": self.threshold,
            "threshold_tokens": int(self.max_tokens * self.threshold),
            "last_count": self._last_count,
            "compaction_count": self._compaction_count,
            "tiktoken_available": TIKTOKEN_AVAILABLE,
        }


# Model context sizes for common models
MODEL_CONTEXT_SIZES = {
    # OpenAI
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 16384,
    # Anthropic
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-opus-4-5": 200000,
    "claude-sonnet-4-5": 200000,
    # Others
    "gemini-pro": 32000,
    "gemini-2.0-flash": 1048576,
    "gemini-2.0-pro": 2097152,
    "kimi-k2.5": 131072,
    "deepseek-chat": 64000,
    "qwen-turbo": 131072,
}


def get_context_size(model: str) -> int:
    """
    Get context size for a model.
    
    Args:
        model: Model name (with or without provider prefix).
    
    Returns:
        Context size in tokens (defaults to 128000).
    """
    # Remove provider prefix
    model_name = model.split("/")[-1].lower()
    
    # Check exact match
    if model_name in MODEL_CONTEXT_SIZES:
        return MODEL_CONTEXT_SIZES[model_name]
    
    # Check partial match
    for key, size in MODEL_CONTEXT_SIZES.items():
        if key in model_name or model_name in key:
            return size
    
    # Default
    return 128000


def create_context_guard(
    model: str = "",
    max_tokens: int | None = None,
    threshold: float = 0.8,
) -> ContextGuard:
    """
    Create a context guard with appropriate settings for a model.
    
    Args:
        model: Model name.
        max_tokens: Override max tokens (auto-detected if None).
        threshold: Compaction threshold (0.0-1.0).
    
    Returns:
        Configured ContextGuard instance.
    """
    if max_tokens is None:
        max_tokens = get_context_size(model)
    
    return ContextGuard(
        max_tokens=max_tokens,
        threshold=threshold,
        model=model,
    )
