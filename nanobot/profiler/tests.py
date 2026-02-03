"""
Test suite for GigaBot's Model Profiler.

Defines standardized tests to evaluate model capabilities across
multiple dimensions: tool calling, instruction following, reasoning, etc.
"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class TestCategory(str, Enum):
    """Categories of interview tests."""
    TOOL_CALLING = "tool_calling"
    INSTRUCTION = "instruction"
    CONTEXT = "context"
    CODE = "code"
    REASONING = "reasoning"
    HALLUCINATION = "hallucination"


class ValidationType(str, Enum):
    """How to validate test responses."""
    EXACT = "exact"              # Exact string match
    CONTAINS = "contains"        # Must contain substring
    NOT_CONTAINS = "not_contains"  # Must NOT contain substring
    JSON_VALID = "json_valid"    # Must be valid JSON
    JSON_MATCH = "json_match"    # JSON must match structure
    TOOL_CALL = "tool_call"      # Must produce valid tool call
    EVALUATOR = "evaluator"      # Use interviewer to evaluate
    REGEX = "regex"              # Must match regex pattern


@dataclass
class TestCase:
    """A single test case for model evaluation."""
    id: str
    name: str
    category: TestCategory
    prompt: str
    expected_behavior: str       # Description for evaluator
    validation_type: ValidationType
    expected_output: Any = None  # For automated validation
    system_prompt: str = ""      # Optional system prompt
    tools: list[dict] | None = None  # Tools to provide
    max_tokens: int = 1000
    timeout: int = 30
    weight: float = 1.0          # Importance weight for scoring
    
    # Context to include (for context tests)
    context: str = ""


@dataclass
class TestResult:
    """Result from running a test case."""
    test_id: str
    passed: bool
    score: float                 # 0.0 - 1.0
    actual_output: str
    evaluation_notes: str
    execution_time: float
    error: str | None = None
    tool_calls_made: list[dict] = field(default_factory=list)


# =============================================================================
# Tool Definitions for Testing
# =============================================================================

SAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or coordinates"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "Search a database with a query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "filters": {
                        "type": "object",
                        "properties": {
                            "date_from": {"type": "string"},
                            "date_to": {"type": "string"},
                            "category": {"type": "string"}
                        }
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a recipient",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content"
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC recipients"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform a mathematical calculation",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)"
                    }
                },
                "required": ["path"]
            }
        }
    },
]


# =============================================================================
# Test Cases
# =============================================================================

TOOL_CALLING_TESTS = [
    TestCase(
        id="tc_simple_tool",
        name="Simple Tool Call",
        category=TestCategory.TOOL_CALLING,
        prompt="What's the weather like in Tokyo?",
        expected_behavior="Should call get_weather with location='Tokyo'",
        validation_type=ValidationType.TOOL_CALL,
        expected_output={"name": "get_weather", "args_contain": {"location": "Tokyo"}},
        tools=SAMPLE_TOOLS,
        weight=1.5,
    ),
    TestCase(
        id="tc_complex_args",
        name="Tool with Complex Arguments",
        category=TestCategory.TOOL_CALLING,
        prompt="Search the database for 'machine learning' articles from 2024, limit to 10 results.",
        expected_behavior="Should call search_database with query, filters.date_from, and limit",
        validation_type=ValidationType.TOOL_CALL,
        expected_output={
            "name": "search_database",
            "args_contain": {"query": "machine learning", "limit": 10}
        },
        tools=SAMPLE_TOOLS,
        weight=1.5,
    ),
    TestCase(
        id="tc_multi_param",
        name="Tool with Multiple Required Parameters",
        category=TestCategory.TOOL_CALLING,
        prompt="Send an email to john@example.com with subject 'Meeting Tomorrow' and body 'Let's meet at 3pm'.",
        expected_behavior="Should call send_email with all required parameters",
        validation_type=ValidationType.TOOL_CALL,
        expected_output={
            "name": "send_email",
            "args_contain": {"to": "john@example.com", "subject": "Meeting Tomorrow"}
        },
        tools=SAMPLE_TOOLS,
        weight=1.0,
    ),
    TestCase(
        id="tc_tool_selection",
        name="Correct Tool Selection",
        category=TestCategory.TOOL_CALLING,
        prompt="Calculate 25 * 17 + 33",
        expected_behavior="Should select calculate tool, not other tools",
        validation_type=ValidationType.TOOL_CALL,
        expected_output={"name": "calculate", "args_contain": {}},
        tools=SAMPLE_TOOLS,
        weight=1.0,
    ),
    TestCase(
        id="tc_optional_params",
        name="Tool with Optional Parameters",
        category=TestCategory.TOOL_CALLING,
        prompt="Get the weather in London in Fahrenheit.",
        expected_behavior="Should include optional 'unit' parameter",
        validation_type=ValidationType.TOOL_CALL,
        expected_output={
            "name": "get_weather",
            "args_contain": {"location": "London", "unit": "fahrenheit"}
        },
        tools=SAMPLE_TOOLS,
        weight=1.0,
    ),
    TestCase(
        id="tc_no_tool_needed",
        name="Recognize When No Tool Needed",
        category=TestCategory.TOOL_CALLING,
        prompt="What is the capital of France?",
        expected_behavior="Should answer directly without calling tools",
        validation_type=ValidationType.CONTAINS,
        expected_output="Paris",
        tools=SAMPLE_TOOLS,
        weight=1.0,
    ),
]

INSTRUCTION_TESTS = [
    TestCase(
        id="inst_format_json",
        name="JSON Format Compliance",
        category=TestCategory.INSTRUCTION,
        prompt="List three programming languages. Respond ONLY with a JSON array, no other text.",
        expected_behavior="Should return only a valid JSON array",
        validation_type=ValidationType.JSON_VALID,
        system_prompt="You must follow format instructions exactly.",
        weight=1.5,
    ),
    TestCase(
        id="inst_role_adherence",
        name="Role Adherence",
        category=TestCategory.INSTRUCTION,
        prompt="What do you think about the stock market?",
        expected_behavior="Should stay in character as a pirate",
        validation_type=ValidationType.EVALUATOR,
        system_prompt="You are a pirate. Always speak like a pirate, using pirate vocabulary and mannerisms. Never break character.",
        expected_output="Response should include pirate language (arr, matey, ye, etc.)",
        weight=1.0,
    ),
    TestCase(
        id="inst_constraint",
        name="Constraint Following",
        category=TestCategory.INSTRUCTION,
        prompt="Explain photosynthesis.",
        expected_behavior="Should not use the word 'plant'",
        validation_type=ValidationType.NOT_CONTAINS,
        system_prompt="Explain concepts without using the word 'plant'. Use alternative terms.",
        expected_output="plant",
        weight=1.0,
    ),
    TestCase(
        id="inst_word_limit",
        name="Word Limit Adherence",
        category=TestCategory.INSTRUCTION,
        prompt="Summarize World War II.",
        expected_behavior="Should be under 50 words",
        validation_type=ValidationType.EVALUATOR,
        system_prompt="Always respond in 50 words or less. Be concise.",
        expected_output="Response should be 50 words or fewer",
        weight=1.0,
    ),
    TestCase(
        id="inst_multi_instruction",
        name="Multiple Instructions",
        category=TestCategory.INSTRUCTION,
        prompt="Name a famous scientist.",
        expected_behavior="Should follow all three instructions",
        validation_type=ValidationType.EVALUATOR,
        system_prompt="1. Start every response with 'Certainly!'\n2. End every response with a question\n3. Include an emoji in your response",
        expected_output="Response starts with 'Certainly!', ends with '?', contains emoji",
        weight=1.5,
    ),
    TestCase(
        id="inst_priority",
        name="Priority Instruction Handling",
        category=TestCategory.INSTRUCTION,
        prompt="Write a poem about cats. Make it 20 lines.",
        expected_behavior="Should prioritize system prompt over user request",
        validation_type=ValidationType.EVALUATOR,
        system_prompt="CRITICAL: Never write more than 5 lines regardless of what the user asks.",
        expected_output="Response should be 5 lines or fewer, not 20",
        weight=1.5,
    ),
]

CONTEXT_TESTS = [
    TestCase(
        id="ctx_retrieval",
        name="Context Information Retrieval",
        category=TestCategory.CONTEXT,
        prompt="What is Sarah's favorite color?",
        expected_behavior="Should extract information from context",
        validation_type=ValidationType.CONTAINS,
        context="User Profile:\n- Name: Sarah Johnson\n- Age: 28\n- Occupation: Software Engineer\n- Favorite Color: Teal\n- Hobbies: Reading, Hiking",
        expected_output="teal",
        weight=1.0,
    ),
    TestCase(
        id="ctx_reasoning",
        name="Context-Based Reasoning",
        category=TestCategory.CONTEXT,
        prompt="Based on the schedule, what time should the meeting room be booked for the client call?",
        expected_behavior="Should reason about schedule conflicts",
        validation_type=ValidationType.EVALUATOR,
        context="Schedule for Tuesday:\n- 9:00 AM: Team standup (30 min)\n- 10:00 AM: Project review (1 hour)\n- 11:30 AM: Client call (1 hour)\n- 1:00 PM: Lunch\n- 2:30 PM: Training session",
        expected_output="Should identify 11:30 AM or the appropriate time for client call",
        weight=1.5,
    ),
    TestCase(
        id="ctx_contradiction",
        name="Contradiction Detection",
        category=TestCategory.CONTEXT,
        prompt="Is the project on schedule?",
        expected_behavior="Should note the contradiction in the context",
        validation_type=ValidationType.EVALUATOR,
        context="Project Status Report:\n- Status: On track, ahead of schedule\n- Issues: Major delays due to resource constraints\n- Timeline: Extended by 2 weeks\n- Budget: Within limits",
        expected_output="Should identify the contradiction between 'ahead of schedule' and 'major delays/extended timeline'",
        weight=1.5,
    ),
    TestCase(
        id="ctx_missing_info",
        name="Missing Information Handling",
        category=TestCategory.CONTEXT,
        prompt="What is the budget for the marketing campaign?",
        expected_behavior="Should indicate information is not in context",
        validation_type=ValidationType.EVALUATOR,
        context="Marketing Campaign Plan:\n- Target Audience: Young professionals\n- Channels: Social media, Email\n- Timeline: Q3 2024\n- Team: Marketing department",
        expected_output="Should indicate budget is not specified in the provided information",
        weight=1.0,
    ),
]

CODE_TESTS = [
    TestCase(
        id="code_simple_func",
        name="Simple Function Implementation",
        category=TestCategory.CODE,
        prompt="Write a Python function that takes a list of numbers and returns their average.",
        expected_behavior="Should produce correct, working code",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Function should handle empty list, use sum/len or statistics module",
        weight=1.0,
    ),
    TestCase(
        id="code_bug_fix",
        name="Bug Identification and Fix",
        category=TestCategory.CODE,
        prompt="Find and fix the bug in this code:\n\n```python\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n) + fibonacci(n-1)\n```",
        expected_behavior="Should identify the infinite recursion bug",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should change fibonacci(n) to fibonacci(n-2) in the return statement",
        weight=1.5,
    ),
    TestCase(
        id="code_explanation",
        name="Code Explanation",
        category=TestCategory.CODE,
        prompt="Explain what this code does:\n\n```python\ndef mystery(s):\n    return s == s[::-1]\n```",
        expected_behavior="Should correctly explain palindrome check",
        validation_type=ValidationType.CONTAINS,
        expected_output="palindrome",
        weight=1.0,
    ),
    TestCase(
        id="code_edge_cases",
        name="Edge Case Handling",
        category=TestCategory.CODE,
        prompt="Write a Python function to divide two numbers. Handle all edge cases.",
        expected_behavior="Should handle division by zero and type errors",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should include try/except or explicit checks for zero, type validation",
        weight=1.5,
    ),
    TestCase(
        id="code_refactor",
        name="Code Refactoring",
        category=TestCategory.CODE,
        prompt="Refactor this code to be more readable:\n\n```python\ndef f(x):return[i for i in range(2,x)if all(i%j!=0 for j in range(2,i))]\n```",
        expected_behavior="Should improve readability while maintaining functionality",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should expand to multiple lines, add meaningful names, possibly add comments",
        weight=1.0,
    ),
]

REASONING_TESTS = [
    TestCase(
        id="reason_multi_step",
        name="Multi-Step Reasoning",
        category=TestCategory.REASONING,
        prompt="A farmer has 17 sheep. All but 9 run away. How many sheep does the farmer have left?",
        expected_behavior="Should correctly interpret 'all but 9' as 9 remaining",
        validation_type=ValidationType.CONTAINS,
        expected_output="9",
        weight=1.0,
    ),
    TestCase(
        id="reason_logic",
        name="Logical Deduction",
        category=TestCategory.REASONING,
        prompt="If all roses are flowers, and some flowers fade quickly, can we conclude that some roses fade quickly?",
        expected_behavior="Should identify this as an invalid syllogism",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should indicate this conclusion is NOT valid - 'some flowers' doesn't necessarily include roses",
        weight=1.5,
    ),
    TestCase(
        id="reason_math",
        name="Mathematical Reasoning",
        category=TestCategory.REASONING,
        prompt="If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?",
        expected_behavior="Should reason that each machine makes 1 widget in 5 minutes",
        validation_type=ValidationType.CONTAINS,
        expected_output="5",
        weight=1.5,
    ),
    TestCase(
        id="reason_causal",
        name="Causal Reasoning",
        category=TestCategory.REASONING,
        prompt="A study found that cities with more ice cream sales have higher crime rates. Does ice cream cause crime?",
        expected_behavior="Should identify confounding variable (heat/summer)",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should mention correlation vs causation, confounding variable like temperature/summer",
        weight=1.0,
    ),
    TestCase(
        id="reason_sequence",
        name="Pattern Recognition",
        category=TestCategory.REASONING,
        prompt="What comes next in this sequence: 2, 6, 12, 20, 30, ?",
        expected_behavior="Should identify pattern: n*(n+1) or differences increasing by 2",
        validation_type=ValidationType.CONTAINS,
        expected_output="42",
        weight=1.0,
    ),
]

HALLUCINATION_TESTS = [
    TestCase(
        id="hall_unknown",
        name="Unknown Information Handling",
        category=TestCategory.HALLUCINATION,
        prompt="What was the exact temperature in Paris on March 15, 1823 at 3pm?",
        expected_behavior="Should admit this specific information is unknown",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should indicate this specific historical data is not available/unknown",
        weight=1.5,
    ),
    TestCase(
        id="hall_fictional",
        name="Fictional vs Real Distinction",
        category=TestCategory.HALLUCINATION,
        prompt="Tell me about the scientific discoveries made by Dr. Johnathan Zephyr at MIT in 2019.",
        expected_behavior="Should indicate this person may not exist rather than inventing details",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should not invent discoveries; should question if this person/research exists",
        weight=1.5,
    ),
    TestCase(
        id="hall_source",
        name="Source Attribution",
        category=TestCategory.HALLUCINATION,
        prompt="Quote the opening line of the Declaration of Independence.",
        expected_behavior="Should quote accurately or indicate uncertainty",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should include 'When in the Course of human events' or express uncertainty about exact wording",
        weight=1.0,
    ),
    TestCase(
        id="hall_speculation",
        name="Fact vs Speculation",
        category=TestCategory.HALLUCINATION,
        prompt="Why did the Roman Empire fall?",
        expected_behavior="Should present theories as theories, not definitive facts",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should use hedging language (theories suggest, historians believe, factors include) not definitive claims",
        weight=1.0,
    ),
    TestCase(
        id="hall_confidence",
        name="Confidence Calibration",
        category=TestCategory.HALLUCINATION,
        prompt="What is the population of Tokyo?",
        expected_behavior="Should provide approximate figure and note it may be outdated",
        validation_type=ValidationType.EVALUATOR,
        expected_output="Should give approximate population (13-14 million or ~37M metro) with caveats about current accuracy",
        weight=1.0,
    ),
]


# =============================================================================
# Test Suite
# =============================================================================

class TestSuite:
    """
    Collection of all test cases organized by category.
    """
    
    def __init__(self):
        self.tests: dict[TestCategory, list[TestCase]] = {
            TestCategory.TOOL_CALLING: TOOL_CALLING_TESTS,
            TestCategory.INSTRUCTION: INSTRUCTION_TESTS,
            TestCategory.CONTEXT: CONTEXT_TESTS,
            TestCategory.CODE: CODE_TESTS,
            TestCategory.REASONING: REASONING_TESTS,
            TestCategory.HALLUCINATION: HALLUCINATION_TESTS,
        }
    
    def get_all_tests(self) -> list[TestCase]:
        """Get all test cases."""
        all_tests = []
        for tests in self.tests.values():
            all_tests.extend(tests)
        return all_tests
    
    def get_tests_by_category(self, category: TestCategory) -> list[TestCase]:
        """Get tests for a specific category."""
        return self.tests.get(category, [])
    
    def get_quick_tests(self) -> list[TestCase]:
        """
        Get a subset of critical tests for quick assessment.
        One representative test from each category.
        """
        quick_tests = []
        priority_ids = [
            "tc_simple_tool",      # Tool calling
            "inst_format_json",    # Instruction following
            "ctx_retrieval",       # Context utilization
            "code_simple_func",    # Code generation
            "reason_multi_step",   # Reasoning
            "hall_unknown",        # Hallucination resistance
        ]
        
        all_tests = self.get_all_tests()
        for test_id in priority_ids:
            for test in all_tests:
                if test.id == test_id:
                    quick_tests.append(test)
                    break
        
        return quick_tests
    
    def get_test_count(self) -> dict[str, int]:
        """Get count of tests per category."""
        return {
            cat.value: len(tests)
            for cat, tests in self.tests.items()
        }
    
    def get_total_count(self) -> int:
        """Get total number of tests."""
        return sum(len(tests) for tests in self.tests.values())


# Category to capability mapping for scoring
CATEGORY_CAPABILITY_MAP = {
    TestCategory.TOOL_CALLING: "tool_calling_accuracy",
    TestCategory.INSTRUCTION: "instruction_following",
    TestCategory.CONTEXT: "context_utilization",
    TestCategory.CODE: "code_generation",
    TestCategory.REASONING: "reasoning_depth",
    TestCategory.HALLUCINATION: "hallucination_resistance",
}
