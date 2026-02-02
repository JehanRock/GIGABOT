"""
Hooks service for GigaBot.

Manages event hooks:
- Webhook delivery
- Script execution
- Agent prompting
"""

import asyncio
import json
import subprocess
from enum import Enum
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field

import httpx
from loguru import logger


class HookAction(str, Enum):
    """Types of hook actions."""
    WEBHOOK = "webhook"
    SCRIPT = "script"
    AGENT = "agent"
    CALLBACK = "callback"


class HookEvent(str, Enum):
    """Types of events that can trigger hooks."""
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    TOOL_EXECUTED = "tool.executed"
    SESSION_CREATED = "session.created"
    SESSION_ENDED = "session.ended"
    CRON_TRIGGERED = "cron.triggered"
    ERROR_OCCURRED = "error.occurred"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"


@dataclass
class Hook:
    """A hook configuration."""
    id: str
    event: str  # Event type to trigger on
    action: HookAction
    target: str  # URL, script path, or agent prompt
    filter: dict[str, Any] = field(default_factory=dict)  # Event filtering
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def matches_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        """Check if this hook should trigger for an event."""
        if not self.enabled:
            return False
        
        if self.event != event_type and self.event != "*":
            return False
        
        # Check filters
        for key, expected in self.filter.items():
            actual = payload.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        
        return True


@dataclass
class HookResult:
    """Result of hook execution."""
    hook_id: str
    success: bool
    response: str = ""
    error: str = ""
    duration_ms: float = 0.0


class HookService:
    """
    Manages and executes hooks.
    
    Features:
    - Async webhook delivery
    - Script execution
    - Agent prompt triggering
    - Error handling and retries
    """
    
    def __init__(
        self,
        webhook_timeout: float = 10.0,
        script_timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.webhook_timeout = webhook_timeout
        self.script_timeout = script_timeout
        self.max_retries = max_retries
        
        self._hooks: dict[str, Hook] = {}
        self._callbacks: dict[str, Callable[[dict], Awaitable[Any]]] = {}
        
        # HTTP client for webhooks
        self._client = httpx.AsyncClient(timeout=webhook_timeout)
        
        # Stats
        self._trigger_count = 0
        self._success_count = 0
        self._error_count = 0
    
    def add_hook(self, hook: Hook) -> None:
        """Add a hook."""
        self._hooks[hook.id] = hook
        logger.debug(f"Hook added: {hook.id} -> {hook.event}")
    
    def remove_hook(self, hook_id: str) -> bool:
        """Remove a hook."""
        if hook_id in self._hooks:
            del self._hooks[hook_id]
            return True
        return False
    
    def get_hook(self, hook_id: str) -> Hook | None:
        """Get a hook by ID."""
        return self._hooks.get(hook_id)
    
    def list_hooks(self, event: str | None = None) -> list[Hook]:
        """List hooks, optionally filtered by event."""
        hooks = list(self._hooks.values())
        if event:
            hooks = [h for h in hooks if h.event == event or h.event == "*"]
        return hooks
    
    def register_callback(
        self,
        name: str,
        callback: Callable[[dict], Awaitable[Any]],
    ) -> None:
        """Register a callback function for callback-type hooks."""
        self._callbacks[name] = callback
    
    async def trigger(
        self,
        event: str,
        payload: dict[str, Any],
    ) -> list[HookResult]:
        """
        Trigger all hooks matching an event.
        
        Args:
            event: Event type.
            payload: Event payload.
        
        Returns:
            List of results from triggered hooks.
        """
        self._trigger_count += 1
        results = []
        
        # Find matching hooks
        matching_hooks = [
            h for h in self._hooks.values()
            if h.matches_event(event, payload)
        ]
        
        if not matching_hooks:
            return results
        
        logger.debug(f"Event {event} matched {len(matching_hooks)} hooks")
        
        # Execute hooks (in parallel)
        tasks = [
            self._execute_hook(hook, event, payload)
            for hook in matching_hooks
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                self._error_count += 1
                processed_results.append(HookResult(
                    hook_id="unknown",
                    success=False,
                    error=str(result),
                ))
            else:
                if result.success:
                    self._success_count += 1
                else:
                    self._error_count += 1
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_hook(
        self,
        hook: Hook,
        event: str,
        payload: dict[str, Any],
    ) -> HookResult:
        """Execute a single hook."""
        import time
        start = time.time()
        
        try:
            if hook.action == HookAction.WEBHOOK:
                result = await self._execute_webhook(hook, event, payload)
            elif hook.action == HookAction.SCRIPT:
                result = await self._execute_script(hook, event, payload)
            elif hook.action == HookAction.CALLBACK:
                result = await self._execute_callback(hook, event, payload)
            elif hook.action == HookAction.AGENT:
                result = await self._execute_agent(hook, event, payload)
            else:
                result = f"Unknown action: {hook.action}"
            
            return HookResult(
                hook_id=hook.id,
                success=True,
                response=str(result) if result else "",
                duration_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            return HookResult(
                hook_id=hook.id,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    async def _execute_webhook(
        self,
        hook: Hook,
        event: str,
        payload: dict[str, Any],
    ) -> str:
        """Execute a webhook hook."""
        data = {
            "event": event,
            "payload": payload,
            "hook_id": hook.id,
        }
        
        headers = hook.metadata.get("headers", {})
        method = hook.metadata.get("method", "POST").upper()
        
        for attempt in range(self.max_retries):
            try:
                if method == "POST":
                    response = await self._client.post(
                        hook.target,
                        json=data,
                        headers=headers,
                    )
                elif method == "GET":
                    response = await self._client.get(
                        hook.target,
                        params={"event": event, "data": json.dumps(payload)},
                        headers=headers,
                    )
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.text
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)
        
        return ""
    
    async def _execute_script(
        self,
        hook: Hook,
        event: str,
        payload: dict[str, Any],
    ) -> str:
        """Execute a script hook."""
        # Prepare environment
        env = {
            "GIGABOT_EVENT": event,
            "GIGABOT_PAYLOAD": json.dumps(payload),
            "GIGABOT_HOOK_ID": hook.id,
        }
        env.update(hook.metadata.get("env", {}))
        
        # Run script
        import os
        full_env = {**os.environ, **env}
        
        process = await asyncio.create_subprocess_shell(
            hook.target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.script_timeout,
            )
            
            if process.returncode != 0:
                raise RuntimeError(f"Script failed: {stderr.decode()}")
            
            return stdout.decode()
            
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError("Script timed out")
    
    async def _execute_callback(
        self,
        hook: Hook,
        event: str,
        payload: dict[str, Any],
    ) -> Any:
        """Execute a callback hook."""
        callback = self._callbacks.get(hook.target)
        if not callback:
            raise ValueError(f"Callback not found: {hook.target}")
        
        return await callback({"event": event, "payload": payload, "hook": hook})
    
    async def _execute_agent(
        self,
        hook: Hook,
        event: str,
        payload: dict[str, Any],
    ) -> str:
        """Execute an agent hook (placeholder)."""
        # This would integrate with the agent loop to send a prompt
        # For now, just return a placeholder
        logger.info(f"Agent hook triggered: {hook.target}")
        return "Agent hook triggered (not implemented)"
    
    async def close(self) -> None:
        """Close the service."""
        await self._client.aclose()
    
    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "hook_count": len(self._hooks),
            "trigger_count": self._trigger_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
        }


# Global instance
_hook_service: HookService | None = None


def get_hook_service() -> HookService:
    """Get the global hook service."""
    global _hook_service
    if _hook_service is None:
        _hook_service = HookService()
    return _hook_service
