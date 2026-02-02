"""
Swarm patterns for GigaBot.

Predefined patterns for common multi-agent workflows:
- Research: Search, summarize, report
- Code: Implement, test, refactor
- Review: Analyze, critique, suggest
"""

from typing import Any
from dataclasses import dataclass, field

from nanobot.swarm.orchestrator import SwarmTask


@dataclass
class SwarmPattern:
    """Base class for swarm patterns."""
    name: str
    description: str
    default_tasks: list[SwarmTask] = field(default_factory=list)
    
    def generate_tasks(self, objective: str, context: str = "") -> list[SwarmTask]:
        """Generate tasks for this pattern."""
        return self.default_tasks


class ResearchPattern(SwarmPattern):
    """
    Pattern for research tasks.
    
    Flow:
    1. Search for information
    2. Summarize findings
    3. Generate report
    """
    
    name = "research"
    description = "Research and synthesize information on a topic"
    
    def generate_tasks(self, objective: str, context: str = "") -> list[SwarmTask]:
        return [
            SwarmTask(
                id="search",
                description="Search for relevant information",
                instructions=f"""Search for information related to:
{objective}

Find:
- Key facts and definitions
- Recent developments
- Multiple perspectives
- Credible sources

{f"Additional context: {context}" if context else ""}

Return a list of relevant findings with source references.""",
                dependencies=[],
            ),
            SwarmTask(
                id="analyze",
                description="Analyze and organize findings",
                instructions="""Analyze the search results and:
- Identify key themes
- Note contradictions or gaps
- Organize by relevance
- Highlight most important points

Create a structured analysis.""",
                dependencies=["search"],
            ),
            SwarmTask(
                id="summarize",
                description="Create comprehensive summary",
                instructions=f"""Create a comprehensive summary addressing:
{objective}

Include:
- Executive summary
- Key findings
- Supporting details
- Conclusions
- Recommendations if applicable

Make it clear, well-organized, and actionable.""",
                dependencies=["analyze"],
            ),
        ]


class CodePattern(SwarmPattern):
    """
    Pattern for coding tasks.
    
    Flow:
    1. Design/plan implementation
    2. Write code
    3. Review and refine
    """
    
    name = "code"
    description = "Implement, test, and refine code"
    
    def generate_tasks(self, objective: str, context: str = "") -> list[SwarmTask]:
        return [
            SwarmTask(
                id="design",
                description="Design the implementation",
                instructions=f"""Design the implementation for:
{objective}

Provide:
- Architecture overview
- Key components/modules
- Data structures
- API design if applicable
- Edge cases to consider

{f"Context: {context}" if context else ""}

Focus on clean, maintainable design.""",
                dependencies=[],
            ),
            SwarmTask(
                id="implement",
                description="Write the code",
                instructions="""Based on the design, implement the code.

Requirements:
- Clean, readable code
- Proper error handling
- Comments for complex logic
- Follow best practices
- Type hints if applicable

Return complete, working code.""",
                dependencies=["design"],
            ),
            SwarmTask(
                id="review",
                description="Review and improve",
                instructions="""Review the implementation:

Check for:
- Bugs or logical errors
- Performance issues
- Security concerns
- Code style consistency
- Missing edge cases

Provide:
- List of issues found
- Suggested fixes
- Improved version if needed""",
                dependencies=["implement"],
            ),
        ]


class ReviewPattern(SwarmPattern):
    """
    Pattern for review tasks.
    
    Flow:
    1. Analyze content
    2. Identify issues
    3. Suggest improvements
    """
    
    name = "review"
    description = "Analyze, critique, and improve content"
    
    def generate_tasks(self, objective: str, context: str = "") -> list[SwarmTask]:
        return [
            SwarmTask(
                id="analyze",
                description="Analyze the content",
                instructions=f"""Analyze:
{objective}

{f"Context: {context}" if context else ""}

Consider:
- Structure and organization
- Clarity and readability
- Accuracy and completeness
- Target audience fit
- Overall quality

Provide detailed analysis.""",
                dependencies=[],
            ),
            SwarmTask(
                id="critique",
                description="Identify issues and weaknesses",
                instructions="""Based on the analysis, identify:

Issues:
- Errors or inaccuracies
- Unclear sections
- Missing information
- Structural problems

Weaknesses:
- Areas that could be stronger
- Opportunities for improvement
- Potential misunderstandings

Be constructive and specific.""",
                dependencies=["analyze"],
            ),
            SwarmTask(
                id="suggest",
                description="Suggest improvements",
                instructions="""Provide improvement suggestions:

For each issue identified:
- Specific recommendation
- Example of improvement
- Priority (high/medium/low)

Also suggest:
- Structural changes
- Additional content
- Alternative approaches

Make suggestions actionable and clear.""",
                dependencies=["critique"],
            ),
        ]


class BrainstormPattern(SwarmPattern):
    """
    Pattern for brainstorming tasks.
    
    Flow:
    1. Generate ideas (divergent)
    2. Evaluate and filter
    3. Develop top ideas
    """
    
    name = "brainstorm"
    description = "Generate and develop creative ideas"
    
    def generate_tasks(self, objective: str, context: str = "") -> list[SwarmTask]:
        return [
            SwarmTask(
                id="generate",
                description="Generate diverse ideas",
                instructions=f"""Brainstorm ideas for:
{objective}

{f"Context: {context}" if context else ""}

Generate at least 10 diverse ideas:
- Include conventional approaches
- Include creative/unconventional ideas
- Don't filter at this stage
- Quantity over quality

List each idea with a brief description.""",
                dependencies=[],
            ),
            SwarmTask(
                id="evaluate",
                description="Evaluate and rank ideas",
                instructions="""Evaluate the generated ideas:

For each idea, rate on:
- Feasibility (1-5)
- Impact (1-5)
- Originality (1-5)

Identify:
- Top 3 most promising
- Most creative
- Easiest to implement

Provide reasoning for rankings.""",
                dependencies=["generate"],
            ),
            SwarmTask(
                id="develop",
                description="Develop top ideas",
                instructions="""For the top 3 ideas, develop each:

Include:
- Detailed description
- Implementation steps
- Required resources
- Potential challenges
- Success metrics

Make each idea actionable.""",
                dependencies=["evaluate"],
            ),
        ]


# Pattern registry
PATTERNS = {
    "research": ResearchPattern(),
    "code": CodePattern(),
    "review": ReviewPattern(),
    "brainstorm": BrainstormPattern(),
}


def get_pattern(name: str) -> SwarmPattern | None:
    """Get a pattern by name."""
    return PATTERNS.get(name)


def list_patterns() -> list[str]:
    """List available pattern names."""
    return list(PATTERNS.keys())
