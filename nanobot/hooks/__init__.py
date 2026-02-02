"""
Hooks system for GigaBot.

Event-driven automation:
- Webhooks for external integrations
- Script execution on events
- Agent triggers
"""

from nanobot.hooks.service import (
    Hook,
    HookAction,
    HookService,
    get_hook_service,
)

__all__ = [
    "Hook",
    "HookAction",
    "HookService",
    "get_hook_service",
]
