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
    from nanobot.profiler.registry import ModelRegistry
    from nanobot.profiler.interviewer import ModelInterviewer
    from nanobot.agent.tool_manager import ToolCallManager
    from nanobot.agent.tool_advisor import ToolAdvisor
    from nanobot.intent.tracker import IntentTracker, UserIntent
    from nanobot.tracking.cache import ResponseCache
    from nanobot.tracking.optimizer import CostOptimizer


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
        
        # Initialize context builder with memory settings
        enable_vector_search = False
        context_memories = 5
        if config and hasattr(config.agents, 'memory'):
            enable_vector_search = config.agents.memory.vector_search
            context_memories = config.agents.memory.context_memories
        
        self.context = ContextBuilder(
            workspace=workspace,
            enable_vector_search=enable_vector_search,
            context_memories=context_memories,
        )
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.default_model,
            brave_api_key=brave_api_key,
        )
        
        # Context window guard with memory-aware compaction
        self.context_guard: ContextGuard | None = None
        if enable_context_guard:
            # Enable memory-aware compaction if memory is enabled
            save_to_memory = False
            if config and hasattr(config.agents, 'memory'):
                save_to_memory = config.agents.memory.enabled
            
            self.context_guard = create_context_guard(
                model=self.default_model,
                threshold=context_threshold,
                save_to_memory=save_to_memory,
                memory_callback=self._save_summary_to_memory if save_to_memory else None,
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
        
        # Model Profiler registry (for profile-aware model selection)
        self.model_registry: "ModelRegistry | None" = None
        self.model_interviewer: "ModelInterviewer | None" = None
        if config and config.agents.profiler.enabled:
            from nanobot.profiler.registry import ModelRegistry
            from nanobot.profiler.interviewer import ModelInterviewer
            
            storage_path = Path(config.agents.profiler.storage_path).expanduser()
            self.model_registry = ModelRegistry(storage_path=storage_path)
            self.model_interviewer = ModelInterviewer(
                provider=provider,
                interviewer_model=config.agents.profiler.interviewer_model,
                workspace=workspace,
            )
            logger.info(f"Model profiler enabled, {len(self.model_registry.list_profiles())} profiles loaded")
        
        # Team orchestrator (persona-based hierarchy)
        self.team_orchestrator: "TeamOrchestrator | None" = None
        if config and config.agents.team.enabled:
            from nanobot.swarm.orchestrator import TeamOrchestrator
            self.team_orchestrator = TeamOrchestrator(
                provider=provider,
                workspace=workspace,
                config=config.agents.team,
                model_registry=self.model_registry,  # Pass registry for profile-aware assignment
            )
            logger.info("Team orchestrator enabled with persona-based hierarchy")
        
        # Tool call manager (self-heal controls)
        self.tool_manager: "ToolCallManager | None" = None
        self.tool_advisor: "ToolAdvisor | None" = None
        if config and hasattr(config.agents, 'self_heal') and config.agents.self_heal.enabled:
            from nanobot.agent.tool_manager import ToolCallManager, RetryConfig, CircuitBreakerConfig
            from nanobot.agent.tool_advisor import ToolAdvisor, AdvisorConfig
            
            # Build retry config from settings
            retry_config = RetryConfig(
                max_retries=config.agents.self_heal.max_tool_retries,
                base_delay=config.agents.self_heal.retry_base_delay,
                max_delay=config.agents.self_heal.retry_max_delay,
                exponential_base=config.agents.self_heal.retry_exponential_base,
            )
            
            # Build circuit breaker config
            circuit_config = CircuitBreakerConfig(
                failure_threshold=config.agents.self_heal.circuit_breaker_threshold,
                reset_timeout=float(config.agents.self_heal.circuit_breaker_cooldown),
            )
            
            # Build tool policy if security is configured
            tool_policy = None
            if config.agents.tool_reinforcement.enforce_security_policy:
                from nanobot.security.policy import create_policy_from_config
                tool_policy = create_policy_from_config({
                    "allow": config.security.tool_policy.allow,
                    "deny": config.security.tool_policy.deny,
                    "require_approval": config.security.tool_policy.require_approval,
                    "require_elevated": config.security.tool_policy.require_elevated,
                })
            
            self.tool_manager = ToolCallManager(
                registry=self.tools,
                retry_config=retry_config,
                circuit_config=circuit_config,
                tool_policy=tool_policy,
                enable_validation=config.agents.tool_reinforcement.pre_validation,
            )
            logger.info("Tool call manager enabled with retry and circuit breaker")
            
            # Initialize tool advisor if adaptive selection enabled
            if config.agents.tool_reinforcement.adaptive_selection:
                advisor_config = AdvisorConfig(
                    min_calls_for_confidence=config.agents.tool_reinforcement.min_calls_for_confidence,
                    default_confidence=config.agents.tool_reinforcement.default_confidence,
                    error_warning_threshold=config.agents.tool_reinforcement.error_warning_threshold,
                    suggest_alternative_threshold=config.agents.tool_reinforcement.suggest_alternative_threshold,
                )
                advisor_path = Path(config.agents.tool_reinforcement.advisor_storage_path).expanduser()
                self.tool_advisor = ToolAdvisor(
                    storage_path=advisor_path,
                    config=advisor_config,
                )
                logger.info("Tool advisor enabled for adaptive tool selection")
        
        # Intent tracker (proactive AI)
        self.intent_tracker: "IntentTracker | None" = None
        self.current_intent: "UserIntent | None" = None
        if config and hasattr(config.agents, 'intent_tracking') and config.agents.intent_tracking.enabled:
            from nanobot.intent.tracker import IntentTracker
            self.intent_tracker = IntentTracker(
                workspace=workspace,
                provider=provider,
                model=config.agents.intent_tracking.analysis_model,
            )
            logger.info("Intent tracker enabled for proactive AI")
        
        # Response cache and cost optimizer (Phase 5B)
        self.response_cache: "ResponseCache | None" = None
        self.cost_optimizer: "CostOptimizer | None" = None
        if config and hasattr(config.agents, 'cost_optimization') and config.agents.cost_optimization.enabled:
            from nanobot.tracking.cache import ResponseCache
            from nanobot.tracking.optimizer import CostOptimizer
            from nanobot.tracking.tokens import TokenTracker
            
            cost_config = config.agents.cost_optimization
            
            if cost_config.response_caching:
                cache_path = Path(cost_config.cache_storage_path).expanduser()
                self.response_cache = ResponseCache(
                    max_size=cost_config.cache_max_size,
                    default_ttl=cost_config.cache_ttl_seconds,
                    storage_path=cache_path,
                )
                logger.info(f"Response cache enabled (max {cost_config.cache_max_size} entries)")
            
            # Initialize cost optimizer (needs token tracker)
            # The token tracker might be shared with the provider
            tracker = getattr(provider, 'token_tracker', None)
            if tracker is None:
                # Create a standalone tracker
                tracker = TokenTracker(
                    daily_budget_usd=cost_config.daily_budget_usd,
                    weekly_budget_usd=cost_config.weekly_budget_usd,
                )
            
            self.cost_optimizer = CostOptimizer(
                tracker=tracker,
                cache=self.response_cache,
                daily_budget_usd=cost_config.daily_budget_usd,
                weekly_budget_usd=cost_config.weekly_budget_usd,
            )
            logger.info("Cost optimizer enabled")
        
        self._running = False
        self._auto_interview_pending: set[str] = set()  # Models pending interview
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
        
        # Memory tool (for explicit memory operations)
        enable_memory_tool = True
        if self.config and hasattr(self.config.agents, 'memory'):
            enable_memory_tool = self.config.agents.memory.enabled
        
        if enable_memory_tool:
            from nanobot.agent.tools.memory import MemoryToolWrapper
            memory_tool = MemoryToolWrapper(workspace=self.workspace)
            self.tools.register(memory_tool)
    
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
    
    async def _process_message(
        self, 
        msg: InboundMessage,
        model_override: str | None = None,
        thinking_level: str = "medium",
    ) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
            model_override: Optional model to use (bypasses tiered routing).
            thinking_level: Reasoning depth - 'low', 'medium', or 'high'.
        
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
        
        # Capture intent (proactive AI - non-blocking)
        if self.intent_tracker:
            try:
                self.current_intent = await self.intent_tracker.capture_intent(
                    message=msg.content,
                    session_id=msg.session_key,
                    user_id=msg.sender_id or "default",
                )
                logger.debug(
                    f"Intent captured: {self.current_intent.category} - "
                    f"{self.current_intent.inferred_goal[:50]}..."
                )
            except Exception as e:
                logger.warning(f"Intent capture failed: {e}")
                self.current_intent = None
        
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
        
        # Determine model via tiered routing (if enabled) or use override
        model_to_use = self.default_model
        routing_decision = None
        
        if model_override:
            # User-selected model override - bypass tiered routing
            model_to_use = model_override
            logger.info(f"Using user-selected model override: {model_to_use}")
        elif self.router:
            routing_decision = self.router.route(msg.content)
            model_to_use = routing_decision.model
            logger.info(
                f"Routing: {routing_decision.classification.task_type.value} -> "
                f"Tier: {routing_decision.tier} -> Model: {model_to_use}"
            )
        
        # Check if model needs profiling (auto-interview)
        if self.model_registry and not self.model_registry.get_profile(model_to_use):
            # Schedule background auto-interview (non-blocking)
            asyncio.create_task(self._auto_interview_model(model_to_use))
        
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
        cache_hit = False
        
        # Check cache before starting iteration (for simple text-only queries)
        if self.response_cache and self.cost_optimizer:
            task_type = routing_decision.classification.task_type.value if routing_decision else ""
            if self.cost_optimizer.should_cache(msg.content, task_type):
                cached_response = self.response_cache.get(msg.content, model_to_use)
                if cached_response:
                    logger.info(f"Cache hit for query (saved tokens)")
                    cache_hit = True
                    # Return cached response directly
                    session.add_message("user", msg.content)
                    session.add_message("assistant", cached_response)
                    self.sessions.save(session)
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=cached_response
                    )
        
        # Map thinking level to temperature
        thinking_temps = {"low": 0.9, "medium": 0.7, "high": 0.3}
        temperature = thinking_temps.get(thinking_level, 0.7)
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Apply context compaction if needed (with memory-aware saving)
            if self.context_guard:
                messages = await self.context_guard.compact_if_needed(
                    messages, self.provider, session_id=msg.session_key
                )
            
            # Call LLM with routed model and thinking-adjusted temperature
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model_to_use,
                temperature=temperature,
            )
            
            # Track model health for routing
            success = bool(response.content)
            if self.router:
                if success:
                    self.router.mark_model_success(model_to_use)
                else:
                    self.router.mark_model_failed(model_to_use)
            
            # Update runtime stats in model registry
            if self.model_registry:
                tool_success = None
                if response.has_tool_calls:
                    # We'll track tool success as None here since we haven't executed yet
                    tool_success = True  # Optimistic; will be corrected if tools fail
                self.model_registry.update_runtime_stats(
                    model_id=model_to_use,
                    success=success,
                    tool_success=tool_success,
                )
                
                # Check for high failure rate and trigger re-assessment
                if not success:
                    asyncio.create_task(self._quick_assess_on_failure(model_to_use))
            
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
                
                # Execute tools (with retry/circuit breaker if tool_manager available)
                for tool_call in response.tool_calls:
                    logger.debug(f"Executing tool: {tool_call.name}")
                    
                    tool_success = True
                    start_time = asyncio.get_event_loop().time()
                    
                    if self.tool_manager:
                        # Use tool manager with retry and circuit breaker
                        exec_result = await self.tool_manager.execute_with_retry(
                            tool_name=tool_call.name,
                            arguments=tool_call.arguments,
                            model_profile=self.model_registry.get_profile(model_to_use) if self.model_registry else None,
                            call_id=tool_call.id,
                        )
                        result = exec_result.result
                        tool_success = exec_result.success
                    else:
                        # Direct execution (fallback)
                        result = await self.tools.execute(tool_call.name, tool_call.arguments)
                        tool_success = not result.startswith("Error:")
                    
                    # Track tool usage in advisor
                    if self.tool_advisor:
                        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                        self.tool_advisor.record_tool_call(
                            model_id=model_to_use,
                            tool_name=tool_call.name,
                            success=tool_success,
                            latency_ms=latency_ms,
                            error=result if not tool_success else "",
                        )
                    
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        
        # Cache response if it was a simple single-turn response (no tools used)
        if self.response_cache and self.cost_optimizer and iteration == 1:
            task_type = routing_decision.classification.task_type.value if routing_decision else ""
            if self.cost_optimizer.should_cache(msg.content, task_type):
                self.response_cache.set(msg.content, final_content, model_to_use)
                logger.debug(f"Cached response for query")
        
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
    
    async def process_direct(
        self, 
        content: str, 
        session_key: str = "cli:direct",
        model: str | None = None,
        thinking_level: str = "medium",
    ) -> str:
        """
        Process a message directly (for CLI/WebUI usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
            model: Optional model override (bypasses tiered routing).
            thinking_level: Reasoning depth - 'low', 'medium', or 'high'.
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content=content
        )
        
        response = await self._process_message(
            msg, 
            model_override=model,
            thinking_level=thinking_level,
        )
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
    
    def get_tool_status(self) -> dict[str, Any]:
        """Get current tool health and advisor status."""
        status: dict[str, Any] = {
            "tool_manager_enabled": self.tool_manager is not None,
            "tool_advisor_enabled": self.tool_advisor is not None,
        }
        
        if self.tool_manager:
            status["tool_health"] = self.tool_manager.get_all_tool_health()
        
        if self.tool_advisor:
            status["advisor_summary"] = self.tool_advisor.get_summary()
            status["problematic_combinations"] = [
                {"model": m, "tool": t, "success_rate": r, "calls": c}
                for m, t, r, c in self.tool_advisor.get_problematic_combinations(min_calls=5)
            ]
        
        return status
    
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
    
    async def _save_summary_to_memory(self, summary: str, session_id: str = "") -> None:
        """
        Save a conversation summary to memory.
        
        Called by ContextGuard when compacting conversation history.
        
        Args:
            summary: The generated summary.
            session_id: Session identifier for context.
        """
        try:
            # Use enhanced memory if available
            session_note = f" (session: {session_id})" if session_id else ""
            content = f"## Conversation Summary{session_note}\n\n{summary}"
            
            success = self.context.add_memory(
                content=content,
                to_long_term=False,  # Add to daily notes
            )
            
            if success:
                logger.debug(f"Saved conversation summary to memory")
            else:
                # Fallback: write directly to simple memory
                from datetime import datetime
                self.context.simple_memory.append_today(
                    f"### Conversation Summary ({datetime.now().strftime('%H:%M')})\n\n{summary}"
                )
                
        except Exception as e:
            logger.warning(f"Failed to save summary to memory: {e}")
    
    async def _auto_interview_model(self, model_id: str) -> None:
        """
        Auto-interview a model if profiler is enabled and model has no profile.
        
        This runs in the background to avoid blocking the main loop.
        
        Args:
            model_id: The model identifier to interview.
        """
        if not self.config or not self.config.agents.profiler.auto_interview:
            return
        
        if not self.model_registry or not self.model_interviewer:
            return
        
        # Skip if already interviewed or pending
        if self.model_registry.get_profile(model_id):
            return
        
        if model_id in self._auto_interview_pending:
            return
        
        self._auto_interview_pending.add(model_id)
        logger.info(f"Auto-interviewing model: {model_id}")
        
        try:
            # Run quick assessment (faster than full interview)
            profile = await self.model_interviewer.quick_assessment(model_id)
            self.model_registry.save_profile(profile)
            logger.info(f"Auto-interview complete for {model_id}, overall score: {profile.get_overall_score():.2f}")
        except Exception as e:
            logger.warning(f"Auto-interview failed for {model_id}: {e}")
        finally:
            self._auto_interview_pending.discard(model_id)
    
    async def _quick_assess_on_failure(self, model_id: str) -> None:
        """
        Re-assess a model after repeated failures.
        
        This can help identify if a model's capabilities have degraded
        or if it needs updated guardrails.
        
        Args:
            model_id: The model identifier to re-assess.
        """
        if not self.config or not self.config.agents.profiler.quick_assess_on_failure:
            return
        
        if not self.model_registry or not self.model_interviewer:
            return
        
        # Check if model has a profile and has high failure rate
        profile = self.model_registry.get_profile(model_id)
        if not profile:
            return
        
        stats = profile.runtime_stats
        if stats.total_requests < 10:
            return  # Not enough data
        
        failure_rate = 1 - stats.success_rate
        if failure_rate > 0.3:  # More than 30% failure rate
            if model_id not in self._auto_interview_pending:
                logger.warning(f"High failure rate ({failure_rate:.1%}) for {model_id}, triggering re-assessment")
                await self._auto_interview_model(model_id)
