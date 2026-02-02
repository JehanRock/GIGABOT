"""
Reply dispatcher for GigaBot auto-reply.

Routes messages to appropriate handlers with:
- Error recovery
- Retry logic
- Acknowledgment via reactions
"""

import asyncio
import time
from typing import Any, Callable, Awaitable
from dataclasses import dataclass

from loguru import logger

from nanobot.auto_reply.commands import (
    parse_message,
    get_command_registry,
    ParsedMessage,
)
from nanobot.auto_reply.queue import MessageQueue, QueuedMessage


@dataclass
class DispatchConfig:
    """Configuration for the dispatcher."""
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    ack_with_reaction: bool = True
    processing_timeout_seconds: float = 300.0


# Type for message handlers
MessageHandler = Callable[[QueuedMessage, ParsedMessage], Awaitable[str | None]]


class ReplyDispatcher:
    """
    Dispatches messages to handlers with error recovery.
    
    Flow:
    1. Parse message for commands
    2. Handle commands first
    3. Route remaining content to agent
    4. Send response back
    """
    
    def __init__(
        self,
        queue: MessageQueue,
        config: DispatchConfig | None = None,
    ):
        self.queue = queue
        self.config = config or DispatchConfig()
        self.command_registry = get_command_registry()
        
        # Message handler (set by caller)
        self._message_handler: MessageHandler | None = None
        
        # Response sender (set by caller)
        self._response_sender: Callable[[str, str, str], Awaitable[None]] | None = None
        
        # Reaction sender (optional)
        self._reaction_sender: Callable[[str, str, str], Awaitable[None]] | None = None
        
        # Stats
        self._processed_count = 0
        self._error_count = 0
        self._running = False
    
    def set_message_handler(self, handler: MessageHandler) -> None:
        """Set the handler for non-command messages."""
        self._message_handler = handler
    
    def set_response_sender(
        self,
        sender: Callable[[str, str, str], Awaitable[None]],
    ) -> None:
        """
        Set the response sender.
        
        Args:
            sender: Async function(channel, chat_id, content).
        """
        self._response_sender = sender
    
    def set_reaction_sender(
        self,
        sender: Callable[[str, str, str], Awaitable[None]],
    ) -> None:
        """
        Set the reaction sender for acknowledgments.
        
        Args:
            sender: Async function(channel, chat_id, reaction).
        """
        self._reaction_sender = sender
    
    async def start(self) -> None:
        """Start the dispatch loop."""
        self._running = True
        logger.info("Reply dispatcher started")
        
        while self._running:
            try:
                # Get next message (with timeout for clean shutdown)
                try:
                    message = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the message
                await self._process_message(message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dispatcher error: {e}")
                self._error_count += 1
    
    def stop(self) -> None:
        """Stop the dispatch loop."""
        self._running = False
        logger.info("Reply dispatcher stopped")
    
    async def _process_message(self, message: QueuedMessage) -> None:
        """Process a single message."""
        self._processed_count += 1
        
        # Send acknowledgment reaction
        if self.config.ack_with_reaction and self._reaction_sender:
            try:
                await self._reaction_sender(message.channel, message.chat_id, "👀")
            except Exception:
                pass  # Ignore reaction errors
        
        # Parse message for commands
        parsed = parse_message(message.content)
        
        # Handle commands first
        command_responses = []
        for command in parsed.commands:
            try:
                response = await self.command_registry.execute(
                    command,
                    {"message": message, "parsed": parsed},
                )
                if response:
                    command_responses.append(response)
            except Exception as e:
                logger.error(f"Command error: {e}")
                command_responses.append(f"Error executing /{command.name}: {e}")
        
        # Send command responses
        if command_responses and self._response_sender:
            await self._response_sender(
                message.channel,
                message.chat_id,
                "\n".join(command_responses),
            )
        
        # Process remaining content through agent
        if parsed.clean_content and self._message_handler:
            response = await self._handle_with_retry(message, parsed)
            
            if response and self._response_sender:
                await self._response_sender(
                    message.channel,
                    message.chat_id,
                    response,
                )
        
        # Clear acknowledgment reaction
        if self.config.ack_with_reaction and self._reaction_sender:
            try:
                await self._reaction_sender(message.channel, message.chat_id, "✅")
            except Exception:
                pass
    
    async def _handle_with_retry(
        self,
        message: QueuedMessage,
        parsed: ParsedMessage,
    ) -> str | None:
        """Handle message with retry logic."""
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = await asyncio.wait_for(
                    self._message_handler(message, parsed),
                    timeout=self.config.processing_timeout_seconds,
                )
                return response
            
            except asyncio.TimeoutError:
                last_error = "Processing timed out"
                logger.warning(f"Message processing timeout (attempt {attempt + 1})")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Message processing error (attempt {attempt + 1}): {e}")
            
            # Wait before retry
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay_seconds)
        
        self._error_count += 1
        return f"Sorry, I encountered an error: {last_error}"
    
    def get_stats(self) -> dict[str, Any]:
        """Get dispatcher statistics."""
        return {
            "processed_count": self._processed_count,
            "error_count": self._error_count,
            "running": self._running,
            "queue_stats": self.queue.get_stats(),
        }
