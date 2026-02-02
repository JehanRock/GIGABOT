"""
Deliberation system for GigaBot's persona-based hierarchy.

Implements board-style discussions where team members provide
opinions on complex decisions, which are then synthesized into
actionable options for the user.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.swarm.team import AgentTeam
    from nanobot.swarm.team_agent import AgentResponse
    from nanobot.providers.base import LLMProvider


@dataclass
class Opinion:
    """An opinion from a team member."""
    role_id: str
    role_title: str
    position: str
    reasoning: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.8
    
    def format(self) -> str:
        """Format opinion for display."""
        lines = [f"**{self.role_title}**"]
        lines.append(f"\n{self.position}")
        
        if self.reasoning:
            lines.append("\n*Key Points:*")
            for point in self.reasoning[:3]:
                lines.append(f"- {point}")
        
        if self.concerns:
            lines.append("\n*Concerns:*")
            for concern in self.concerns[:2]:
                lines.append(f"- {concern}")
        
        if self.recommendation:
            lines.append(f"\n*Recommendation:* {self.recommendation}")
        
        return "\n".join(lines)


@dataclass
class Option:
    """An option synthesized from team opinions."""
    id: str
    title: str
    description: str
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    supporters: list[str] = field(default_factory=list)
    concerns_from: list[str] = field(default_factory=list)
    effort_estimate: str = ""
    risk_level: str = "medium"
    
    def format(self) -> str:
        """Format option for display."""
        lines = [f"### Option {self.id}: {self.title}"]
        lines.append(f"\n{self.description}")
        
        if self.pros:
            lines.append("\n**Pros:**")
            for pro in self.pros:
                lines.append(f"- {pro}")
        
        if self.cons:
            lines.append("\n**Cons:**")
            for con in self.cons:
                lines.append(f"- {con}")
        
        if self.effort_estimate:
            lines.append(f"\n*Effort:* {self.effort_estimate}")
        
        lines.append(f"*Risk:* {self.risk_level}")
        
        if self.supporters:
            lines.append(f"\n*Supported by:* {', '.join(self.supporters)}")
        
        return "\n".join(lines)


@dataclass
class DeliberationResult:
    """Result of a deliberation session."""
    question: str
    opinions: dict[str, Opinion] = field(default_factory=dict)
    options: list[Option] = field(default_factory=list)
    summary: str = ""
    recommendation: str = ""
    
    def format_for_user(self) -> str:
        """Format the deliberation result for user presentation."""
        lines = ["## Team Deliberation\n"]
        
        # Show question
        lines.append(f"**Question:** {self.question}\n")
        
        # Show opinions
        if self.opinions:
            lines.append("---\n### Team Perspectives\n")
            for opinion in self.opinions.values():
                lines.append(opinion.format())
                lines.append("")
        
        # Show options
        if self.options:
            lines.append("---\n### Options for Your Consideration\n")
            for option in self.options:
                lines.append(option.format())
                lines.append("")
        
        # Show recommendation if available
        if self.recommendation:
            lines.append("---\n### Team Recommendation\n")
            lines.append(self.recommendation)
        
        lines.append("\n---\n*Which direction would you like to pursue?*")
        
        return "\n".join(lines)


class DeliberationSession:
    """
    Board-style discussion for complex decisions.
    
    Flow:
    1. Present question to relevant team members
    2. Collect all opinions in parallel
    3. Synthesize into options with pros/cons
    4. Present to user for decision
    
    This enables the "Reach this goal" interaction mode where
    the team discusses and presents options rather than just executing.
    """
    
    def __init__(
        self,
        team: "AgentTeam",
        synthesizer_model: str = "anthropic/claude-sonnet-4-5",
        provider: "LLMProvider | None" = None,
        timeout: int = 120,
        min_opinions: int = 3,
    ):
        """
        Initialize a deliberation session.
        
        Args:
            team: The agent team.
            synthesizer_model: Model for synthesizing opinions.
            provider: LLM provider for synthesis.
            timeout: Timeout for gathering opinions.
            min_opinions: Minimum number of opinions to gather.
        """
        self.team = team
        self.synthesizer_model = synthesizer_model
        self.provider = provider or team.provider
        self.timeout = timeout
        self.min_opinions = min_opinions
    
    async def run(
        self,
        question: str,
        participants: list[str] | None = None,
        context: str = "",
    ) -> DeliberationResult:
        """
        Run a deliberation session.
        
        Args:
            question: The question to deliberate on.
            participants: Specific roles to include (or None for auto).
            context: Additional context for the discussion.
        
        Returns:
            DeliberationResult with opinions and options.
        """
        logger.info(f"Starting deliberation: {question[:50]}...")
        
        # Determine participants
        if not participants:
            participants = self._select_participants(question)
        
        # Ensure minimum participation
        participants = self._ensure_minimum_participants(participants)
        
        # Gather opinions
        opinions = await self._gather_opinions(question, participants, context)
        
        if not opinions:
            return DeliberationResult(
                question=question,
                summary="No opinions gathered from team members.",
            )
        
        # Synthesize into options
        options, recommendation = await self._synthesize_options(
            question, opinions, context
        )
        
        return DeliberationResult(
            question=question,
            opinions=opinions,
            options=options,
            recommendation=recommendation,
        )
    
    async def _gather_opinions(
        self,
        question: str,
        participants: list[str],
        context: str,
    ) -> dict[str, Opinion]:
        """Gather opinions from all participants in parallel."""
        logger.debug(f"Gathering opinions from: {participants}")
        
        # Create tasks for each participant
        tasks = []
        for role_id in participants:
            agent = self.team.get_agent(role_id)
            if agent:
                tasks.append((role_id, agent.give_opinion(question, context)))
        
        # Execute in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[t[1] for t in tasks], return_exceptions=True),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Opinion gathering timed out")
            results = []
        
        # Parse responses into opinions
        opinions: dict[str, Opinion] = {}
        for (role_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to get opinion from {role_id}: {result}")
                continue
            
            if isinstance(result, dict):
                # Handle dict response (shouldn't happen but safety)
                continue
            
            response: "AgentResponse" = result
            if response.success:
                opinion = self._parse_opinion(role_id, response)
                if opinion:
                    opinions[role_id] = opinion
        
        return opinions
    
    def _parse_opinion(
        self,
        role_id: str,
        response: "AgentResponse",
    ) -> Opinion | None:
        """Parse an agent response into a structured opinion."""
        import re
        
        content = response.content
        if not content:
            return None
        
        # Extract position (first paragraph or until numbered list)
        position_match = re.match(r'^(.+?)(?=\n\d\.|\n\*|\n-|\n\n)', content, re.DOTALL)
        position = position_match.group(1).strip() if position_match else content[:200]
        
        # Extract reasoning points
        reasoning = []
        reasoning_match = re.findall(r'(?:reasoning|points?|because).*?(?:\n[-*\d]\.?\s*(.+))+', 
                                     content, re.IGNORECASE)
        if reasoning_match:
            for match in reasoning_match[:3]:
                reasoning.append(match.strip())
        
        # Try to find bullet points as reasoning
        if not reasoning:
            bullets = re.findall(r'^[-*]\s*(.+)$', content, re.MULTILINE)
            reasoning = bullets[:3]
        
        # Extract concerns
        concerns = []
        concerns_match = re.search(r'(?:concern|risk|caveat|warning)s?[:\s]+(.+?)(?=\n\n|recommendation|$)',
                                   content, re.IGNORECASE | re.DOTALL)
        if concerns_match:
            concern_text = concerns_match.group(1)
            concerns = [c.strip() for c in re.split(r'\n[-*]', concern_text) if c.strip()][:2]
        
        # Extract recommendation
        recommendation = ""
        rec_match = re.search(r'(?:recommend|suggest|advise)[:\s]+(.+?)(?=\n\n|$)',
                              content, re.IGNORECASE | re.DOTALL)
        if rec_match:
            recommendation = rec_match.group(1).strip()
        
        return Opinion(
            role_id=role_id,
            role_title=response.role_title,
            position=position,
            reasoning=reasoning,
            concerns=concerns,
            recommendation=recommendation,
        )
    
    async def _synthesize_options(
        self,
        question: str,
        opinions: dict[str, Opinion],
        context: str,
    ) -> tuple[list[Option], str]:
        """Synthesize opinions into actionable options."""
        # Build synthesis prompt
        opinions_text = "\n\n".join([
            f"**{op.role_title}**: {op.position}\nKey points: {', '.join(op.reasoning)}\nConcerns: {', '.join(op.concerns)}"
            for op in opinions.values()
        ])
        
        prompt = f"""You are synthesizing team opinions into actionable options.

**Question:** {question}

{f"**Context:** {context}" if context else ""}

**Team Opinions:**
{opinions_text}

Synthesize these opinions into 2-4 distinct options for the user.
For each option:
1. Give it a short title
2. Describe the approach
3. List pros and cons
4. Estimate effort (e.g., "2-3 days", "1 week")
5. Rate risk level (low/medium/high)

Also provide an overall team recommendation.

Format as JSON:
{{
    "options": [
        {{
            "id": "1",
            "title": "Option title",
            "description": "Brief description",
            "pros": ["pro 1", "pro 2"],
            "cons": ["con 1", "con 2"],
            "effort": "estimate",
            "risk": "low/medium/high"
        }}
    ],
    "recommendation": "Overall team recommendation"
}}

Return ONLY the JSON."""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.synthesizer_model,
                max_tokens=2000,
                temperature=0.5,
            )
            
            content = response.content or ""
            
            # Parse JSON
            import json
            import re
            
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                
                options = []
                for opt_data in data.get("options", []):
                    options.append(Option(
                        id=str(opt_data.get("id", len(options) + 1)),
                        title=opt_data.get("title", "Option"),
                        description=opt_data.get("description", ""),
                        pros=opt_data.get("pros", []),
                        cons=opt_data.get("cons", []),
                        effort_estimate=opt_data.get("effort", ""),
                        risk_level=opt_data.get("risk", "medium"),
                    ))
                
                recommendation = data.get("recommendation", "")
                return options, recommendation
                
        except Exception as e:
            logger.error(f"Option synthesis failed: {e}")
        
        # Fallback: create simple options from opinions
        return self._fallback_options(opinions), ""
    
    def _fallback_options(self, opinions: dict[str, Opinion]) -> list[Option]:
        """Create fallback options if synthesis fails."""
        options = []
        
        # Group by recommendation similarity
        seen_positions = set()
        for op in opinions.values():
            pos_key = op.position[:50].lower()
            if pos_key not in seen_positions:
                seen_positions.add(pos_key)
                options.append(Option(
                    id=str(len(options) + 1),
                    title=f"{op.role_title}'s Approach",
                    description=op.position[:200],
                    pros=op.reasoning,
                    cons=op.concerns,
                    supporters=[op.role_title],
                ))
        
        return options[:4]  # Max 4 options
    
    def _select_participants(self, question: str) -> list[str]:
        """Auto-select participants based on question."""
        question_lower = question.lower()
        participants = []
        
        # Technical/architecture questions
        if any(kw in question_lower for kw in ["architect", "design", "system", "scale"]):
            participants.append("architect")
        
        # Implementation questions
        if any(kw in question_lower for kw in ["implement", "build", "develop", "code"]):
            participants.extend(["lead_dev", "senior_dev"])
        
        # Security questions
        if any(kw in question_lower for kw in ["security", "safe", "risk", "protect"]):
            participants.append("auditor")
        
        # Quality questions
        if any(kw in question_lower for kw in ["quality", "test", "reliable", "bug"]):
            participants.append("qa_engineer")
        
        # Research questions
        if any(kw in question_lower for kw in ["research", "compare", "evaluate", "option"]):
            participants.append("researcher")
        
        # Default: key stakeholders
        if not participants:
            participants = ["architect", "lead_dev", "qa_engineer"]
        
        return list(set(participants))
    
    def _ensure_minimum_participants(self, participants: list[str]) -> list[str]:
        """Ensure minimum number of participants."""
        available = self.team.get_available_roles()
        participants = [p for p in participants if p in available]
        
        # Add more if needed
        priority_roles = ["architect", "lead_dev", "qa_engineer", "auditor", "researcher"]
        for role in priority_roles:
            if len(participants) >= self.min_opinions:
                break
            if role in available and role not in participants:
                participants.append(role)
        
        return participants


async def quick_deliberate(
    team: "AgentTeam",
    question: str,
    context: str = "",
) -> str:
    """
    Quick deliberation helper function.
    
    Args:
        team: The agent team.
        question: Question to deliberate.
        context: Optional context.
    
    Returns:
        Formatted deliberation result.
    """
    session = DeliberationSession(team)
    result = await session.run(question, context=context)
    return result.format_for_user()
