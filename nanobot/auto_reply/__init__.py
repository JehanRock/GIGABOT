"""
Auto-reply system for GigaBot.

Provides intelligent message handling:
- Command detection and parsing
- Message queuing with debounce
- Rate limiting
- Priority handling
"""

from nanobot.auto_reply.commands import (
    Command,
    CommandRegistry,
    parse_command,
    get_command_registry,
)
from nanobot.auto_reply.queue import (
    MessageQueue,
    QueuedMessage,
    QueueConfig,
)
from nanobot.auto_reply.dispatch import (
    ReplyDispatcher,
    DispatchConfig,
)

__all__ = [
    # Commands
    "Command",
    "CommandRegistry",
    "parse_command",
    "get_command_registry",
    # Queue
    "MessageQueue",
    "QueuedMessage",
    "QueueConfig",
    # Dispatch
    "ReplyDispatcher",
    "DispatchConfig",
]
