"""Context builder for assembling agent prompts."""

from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

from nanobot.agent.memory import MemoryStore as SimpleMemoryStore
from nanobot.agent.skills import SkillsLoader

if TYPE_CHECKING:
    from nanobot.memory.store import MemoryStore as EnhancedMemoryStore
    from nanobot.memory.vector import VectorStore
    from nanobot.memory.search import HybridSearch


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    
    Supports two memory modes:
    - Simple: File-based daily notes + long-term memory (default)
    - Enhanced: Vector search + hybrid retrieval (when enabled)
    """
    
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    
    def __init__(
        self,
        workspace: Path,
        enable_vector_search: bool = False,
        context_memories: int = 5,
    ):
        """
        Initialize the context builder.
        
        Args:
            workspace: Path to the workspace directory.
            enable_vector_search: Enable semantic memory retrieval.
            context_memories: Number of memories to include from semantic search.
        """
        self.workspace = workspace
        self.simple_memory = SimpleMemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
        
        # Enhanced memory components (lazy initialized)
        self._enable_vector_search = enable_vector_search
        self._context_memories = context_memories
        self._enhanced_memory: "EnhancedMemoryStore | None" = None
        self._vector_store: "VectorStore | None" = None
        self._hybrid_search: "HybridSearch | None" = None
        
        if enable_vector_search:
            self._init_enhanced_memory()
    
    def _init_enhanced_memory(self) -> None:
        """Initialize enhanced memory components."""
        try:
            from nanobot.memory.store import MemoryStore as EnhancedMemoryStore
            from nanobot.memory.vector import VectorStore
            from nanobot.memory.search import HybridSearch
            
            self._enhanced_memory = EnhancedMemoryStore(self.workspace)
            self._vector_store = VectorStore(
                storage_path=self.workspace / "memory" / "vectors.json"
            )
            self._hybrid_search = HybridSearch(
                memory_store=self._enhanced_memory,
                vector_store=self._vector_store,
            )
            
            # Index existing memories if vector store is empty
            if self._vector_store.size == 0:
                entries = self._enhanced_memory.get_all_entries()
                if entries:
                    self._vector_store.add_batch(entries)
                    self._vector_store.save()
                    logger.info(f"Indexed {len(entries)} memories to vector store")
            
            logger.info("Enhanced memory system initialized")
            
        except Exception as e:
            logger.warning(f"Failed to initialize enhanced memory: {e}")
            self._enable_vector_search = False
    
    @property
    def memory(self) -> SimpleMemoryStore:
        """Get simple memory store (backward compatibility)."""
        return self.simple_memory
    
    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        current_query: str | None = None,
    ) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.
        
        Args:
            skill_names: Optional list of skills to include.
            current_query: Current user query for semantic memory retrieval.
        
        Returns:
            Complete system prompt.
        """
        parts = []
        
        # Core identity
        parts.append(self._get_identity())
        
        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context - use enhanced search if available and query provided
        if self._enable_vector_search and current_query and self._hybrid_search:
            memory = self._get_semantic_memory_context(current_query)
        else:
            memory = self.simple_memory.get_memory_context()
        
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        
        return f"""# nanobot 🐈

You are nanobot, a helpful AI assistant. You have access to tools that allow you to:
- Read, write, and edit files
- Execute shell commands
- Search the web and fetch web pages
- Send messages to users on chat channels
- Spawn subagents for complex background tasks

## Current Time
{now}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

IMPORTANT: When responding to direct questions or conversations, reply directly with your text response.
Only use the 'message' tool when you need to send a message to a specific chat channel (like WhatsApp).
For normal conversation, just respond with text - do not call the message tool.

Always be helpful, accurate, and concise. When using tools, explain what you're doing.
When remembering something, write to {workspace_path}/memory/MEMORY.md"""
    
    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []
        
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _get_semantic_memory_context(self, query: str) -> str:
        """
        Get memory context using semantic search.
        
        Args:
            query: Current user query for relevance scoring.
        
        Returns:
            Formatted memory context with relevant memories.
        """
        parts = []
        
        # Always include long-term memory (important persistent info)
        long_term = self.simple_memory.read_long_term()
        if long_term:
            parts.append("## Long-term Memory\n" + long_term)
        
        # Semantic search for relevant memories
        if self._hybrid_search:
            try:
                results = self._hybrid_search.search(
                    query=query,
                    k=self._context_memories,
                    recency_days=30,
                )
                
                if results:
                    relevant_parts = ["## Relevant Memories"]
                    for i, result in enumerate(results, 1):
                        source_label = result.entry.source.replace("_", " ").title()
                        relevant_parts.append(
                            f"\n### [{source_label}] (relevance: {result.combined_score:.2f})\n"
                            f"{result.entry.content}"
                        )
                    parts.append("\n".join(relevant_parts))
                    
            except Exception as e:
                logger.debug(f"Semantic memory search failed: {e}")
                # Fallback to simple memory
                today = self.simple_memory.read_today()
                if today:
                    parts.append("## Today's Notes\n" + today)
        
        # Include today's notes if not covered by semantic search
        if not parts or len(parts) == 1:  # Only long-term
            today = self.simple_memory.read_today()
            if today:
                parts.append("## Today's Notes\n" + today)
        
        return "\n\n".join(parts) if parts else ""
    
    def search_memories(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """
        Search memories semantically.
        
        Args:
            query: Search query.
            k: Number of results.
        
        Returns:
            List of memory results with scores.
        """
        if not self._hybrid_search:
            return []
        
        try:
            results = self._hybrid_search.search(query, k=k)
            return [
                {
                    "content": r.entry.content,
                    "source": r.entry.source,
                    "score": r.combined_score,
                    "timestamp": r.entry.timestamp.isoformat(),
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
            return []
    
    def add_memory(
        self,
        content: str,
        to_long_term: bool = False,
        section: str = "",
    ) -> bool:
        """
        Add a memory and update the vector index.
        
        Args:
            content: Memory content.
            to_long_term: Add to long-term memory if True, daily notes if False.
            section: Section name for long-term memory.
        
        Returns:
            True if successful.
        """
        try:
            if to_long_term:
                if self._enhanced_memory:
                    self._enhanced_memory.add_to_long_term(content, section)
                else:
                    # Append to simple memory
                    existing = self.simple_memory.read_long_term()
                    self.simple_memory.write_long_term(existing + f"\n\n{content}")
            else:
                if self._enhanced_memory:
                    self._enhanced_memory.add_to_daily(content)
                else:
                    self.simple_memory.append_today(content)
            
            # Update vector index
            if self._vector_store and self._enhanced_memory:
                from datetime import datetime
                from nanobot.memory.store import MemoryEntry
                
                entry = MemoryEntry(
                    id=f"{'long_term' if to_long_term else 'daily'}:{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    content=content,
                    source="long_term" if to_long_term else "daily",
                    timestamp=datetime.now(),
                    metadata={"section": section} if section else {},
                )
                self._vector_store.add(entry)
                self._vector_store.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False
    
    def reindex_memories(self) -> int:
        """
        Reindex all memories to the vector store.
        
        Returns:
            Number of entries indexed.
        """
        if not self._hybrid_search:
            return 0
        
        try:
            count = self._hybrid_search.index_all_memories()
            if self._vector_store:
                self._vector_store.save()
            logger.info(f"Reindexed {count} memories")
            return count
        except Exception as e:
            logger.error(f"Failed to reindex memories: {e}")
            return 0
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        use_semantic_memory: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.
        
        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            use_semantic_memory: Use current message for semantic memory retrieval.
        
        Returns:
            List of messages including system prompt.
        """
        messages = []
        
        # System prompt - pass current message for semantic memory if enabled
        query_for_memory = current_message if use_semantic_memory else None
        system_prompt = self.build_system_prompt(skill_names, query_for_memory)
        messages.append({"role": "system", "content": system_prompt})
        
        # History
        messages.extend(history)
        
        # Current message
        messages.append({"role": "user", "content": current_message})
        
        return messages
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        messages.append(msg)
        return messages
