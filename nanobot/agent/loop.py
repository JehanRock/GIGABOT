"""Agent loop: the core processing engine."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.compaction import ContextGuard, create_context_guard
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.process import ProcessTool
from nanobot.agent.subagent import SubagentManager
from nanobot.session.manager import SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import Config
    from nanobot.routing.router import TieredRouter
    from nanobot.swarm.orchestrator import SwarmOrchestrator, TeamOrchestrator
    from nanobot.agent.validation import VisualValidator


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM (with tiered routing if enabled)
    4. Executes tool calls
    5. Sends responses back
    6. Optionally triggers swarm for complex tasks
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        config: "Config | None" = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        enable_context_guard: bool = True,
        context_threshold: float = 0.8,
    ):
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.config = config
        self.default_model = model or provider.get_default_model()
        self.model = self.default_model  # Keep for backward compatibility
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        
        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.default_model,
            brave_api_key=brave_api_key,
        )
        
        # Context window guard
        self.context_guard: ContextGuard | None = None
        if enable_context_guard:
            self.context_guard = create_context_guard(
                model=self.default_model,
                threshold=context_threshold,
            )
        
        # Tiered routing (if enabled in config)
        self.router: "TieredRouter | None" = None
        if config and config.agents.tiered_routing.enabled:
            from nanobot.routing.router import create_router_from_config
            self.router = create_router_from_config(config)
            logger.info(f"Tiered routing enabled with {len(self.router.tiers)} tiers")
        
        # Swarm orchestrator (if enabled in config)
        self.swarm_orchestrator: "SwarmOrchestrator | None" = None
        if config and config.agents.swarm.enabled:
            from nanobot.swarm.orchestrator import SwarmOrchestrator, SwarmConfig
            swarm_config = SwarmConfig(
                enabled=True,
                max_workers=config.agents.swarm.max_workers,
                worker_model=config.agents.swarm.worker_model,
                orchestrator_model=config.agents.swarm.orchestrator_model,
            )
            self.swarm_orchestrator = SwarmOrchestrator(
                config=swarm_config,
                provider=provider,
                workspace=workspace,
            )
            logger.info(f"Swarm orchestrator enabled with {swarm_config.max_workers} max workers")
        
        # Visual validator (if dev workflow enabled)
        self.visual_validator: "VisualValidator | None" = None
        self.process_tool: ProcessTool | None = None
        if config and config.agents.dev_workflow.enabled:
            self.process_tool = ProcessTool(working_dir=str(workspace))
            
            if config.agents.dev_workflow.visual_validation.enabled:
                # Lazy initialization - will be created when browser tool is available
                logger.info("Visual validation enabled (will initialize when browser available)")
        
        # Team orchestrator (persona-based hierarchy)
        self.team_orchestrator: "TeamOrchestrator | None" = None
        if config and config.agents.team.enabled:
            from nanobot.swarm.orchestrator import TeamOrchestrator
            self.team_orchestrator = TeamOrchestrator(
                provider=provider,
                workspace=workspace,
                config=config.agents.team,
            )
            logger.info("Team orchestrator enabled with persona-based hierarchy")
        
        self._running = False
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(EditFileTool())
        self.tools.register(ListDirTool())
        
        # Shell tool
        self.tools.register(ExecTool(working_dir=str(self.workspace)))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Process tool for dev server management
        if self.process_tool:
            self.tools.register(self.process_tool)
        else:
            # Register a default process tool
            self.tools.register(ProcessTool(working_dir=str(self.workspace)))
        
        # Swarm tool (if orchestrator available)
        if self.swarm_orchestrator:
            from nanobot.agent.tools.swarm import SwarmTool, SwarmStatusTool
            self.tools.register(SwarmTool(orchestrator=self.swarm_orchestrator))
            self.tools.register(SwarmStatusTool(orchestrator=self.swarm_orchestrator))
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")
        
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        # Check for team commands (/reach and /done)
        if self.team_orchestrator:
            team_result = await self._handle_team_commands(msg)
            if team_result:
                session.add_message("user", msg.content)
                session.add_message("assistant", team_result)
                self.sessions.save(session)
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=team_result
                )
        
        # Determine model via tiered routing (if enabled)
        model_to_use = self.default_model
        routing_decision = None
        
        if self.router:
            routing_decision = self.router.route(msg.content)
            model_to_use = routing_decision.model
            logger.info(
                f"Routing: {routing_decision.classification.task_type.value} -> "
                f"Tier: {routing_decision.tier} -> Model: {model_to_use}"
            )
        
        # Check if swarm should be used for complex tasks
        if self.swarm_orchestrator and routing_decision:
            from nanobot.agent.swarm_trigger import should_use_swarm, auto_select_pattern
            should_swarm, pattern = should_use_swarm(
                msg.content, 
                routing_decision.classification,
                self.config.agents.swarm if self.config else None
            )
            if should_swarm:
                logger.info(f"Triggering swarm execution with pattern: {pattern}")
                swarm_result = await self.swarm_orchestrator.execute(
                    objective=msg.content,
                    pattern=pattern,
                )
                # Use swarm result as the final content
                session.add_message("user", msg.content)
                session.add_message("assistant", swarm_result)
                self.sessions.save(session)
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=swarm_result
                )
        
        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Apply context compaction if needed
            if self.context_guard:
                messages = await self.context_guard.compact_if_needed(
                    messages, self.provider
                )
            
            # Call LLM with routed model
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model_to_use
            )
            
            # Track model health for routing
            if self.router:
                if response.content:
                    self.router.mark_model_success(model_to_use)
                else:
                    self.router.mark_model_failed(model_to_use)
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # Execute tools
                for tool_call in response.tool_calls:
                    logger.debug(f"Executing tool: {tool_call.name}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        
        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        # Determine model via tiered routing (if enabled)
        model_to_use = self.default_model
        if self.router:
            routing_decision = self.router.route(msg.content)
            model_to_use = routing_decision.model
            logger.debug(f"System message routed to: {model_to_use}")
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model_to_use
            )
            
            # Track model health
            if self.router:
                if response.content:
                    self.router.mark_model_success(model_to_use)
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                for tool_call in response.tool_calls:
                    logger.debug(f"Executing tool: {tool_call.name}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(self, content: str, session_key: str = "cli:direct") -> str:
        """
        Process a message directly (for CLI usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""
    
    def _is_ui_task(self, content: str) -> bool:
        """
        Detect if a task is UI-related and may benefit from visual validation.
        
        Args:
            content: The message content.
        
        Returns:
            True if the task appears to be UI-related.
        """
        ui_indicators = [
            r"\b(ui|ux|frontend|css|style|layout|design)\b",
            r"\b(component|button|form|input|modal|dialog)\b",
            r"\b(page|screen|view|interface)\b",
            r"\b(html|jsx|tsx|react|vue|angular|svelte)\b",
            r"\b(responsive|mobile|desktop|tablet)\b",
            r"\b(color|font|animation|transition)\b",
            r"\b(navbar|sidebar|footer|header)\b",
            r"localhost:\d+",
            r"http://.*:\d+",
        ]
        
        content_lower = content.lower()
        return any(re.search(pattern, content_lower) for pattern in ui_indicators)
    
    def get_routing_status(self) -> dict[str, Any]:
        """Get current routing status."""
        if not self.router:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "tiers": list(self.router.tiers.keys()),
            "fallback_tier": self.router.fallback_tier,
            "model_health": {
                model: health.to_dict()
                for model, health in self.router.model_health.items()
            },
        }
    
    def get_swarm_status(self) -> dict[str, Any]:
        """Get current swarm status."""
        if not self.swarm_orchestrator:
            return {"enabled": False}
        
        return self.swarm_orchestrator.get_status()
    
    def get_team_status(self) -> dict[str, Any]:
        """Get current team orchestrator status."""
        if not self.team_orchestrator:
            return {"enabled": False}
        
        return self.team_orchestrator.get_status()
    
    async def _handle_team_commands(self, msg: InboundMessage) -> str | None:
        """
        Handle team-specific commands (/reach, /done).
        
        Args:
            msg: The inbound message to check.
        
        Returns:
            Response string if handled, None otherwise.
        """
        content = msg.content.strip()
        
        # Check for /reach command (deliberation mode)
        if content.lower().startswith("/reach "):
            question = content[7:].strip()
            if question:
                logger.info(f"Team deliberation: {question[:50]}...")
                return await self.team_orchestrator.execute(
                    question, 
                    mode="deliberate"
                )
        
        # Check for /done command (execution mode)
        if content.lower().startswith("/done "):
            task = content[6:].strip()
            if task:
                logger.info(f"Team execution: {task[:50]}...")
                return await self.team_orchestrator.execute(
                    task, 
                    mode="execute"
                )
        
        # Check for /team command (team status/info)
        if content.lower() == "/team":
            status = self.team_orchestrator.get_status()
            lines = [
                "**Agent Team Status**",
                f"Team Size: {status['team_size']}",
                f"Available Roles: {', '.join(status['available_roles'])}",
                f"Active Tasks: {status['active_tasks']}",
                f"QA Gate: {'enabled' if status['qa_enabled'] else 'disabled'}",
                f"Audit Gate: {'enabled' if status['audit_enabled'] else 'disabled'}",
            ]
            return "\n".join(lines)
        
        return None
    
    async def cleanup(self) -> None:
        """Clean up agent resources."""
        logger.info("Cleaning up agent loop resources")
        
        # Clean up process tool (stop dev servers)
        if self.process_tool:
            await self.process_tool.cleanup()
        
        # Clean up subagents
        if self.subagents:
            await self.subagents.cleanup()
        
        # Clean up team orchestrator
        if self.team_orchestrator:
            self.team_orchestrator.reset()
