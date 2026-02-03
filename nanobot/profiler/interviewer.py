"""
Model Interviewer for GigaBot's Model Profiler.

Evaluates AI models through standardized tests, similar to how HR
interviews job candidates. Uses a high-reasoning model to conduct
evaluations and synthesize results into capability profiles.
"""

import asyncio
import json
import re
import time
from typing import Any, TYPE_CHECKING
from pathlib import Path

from loguru import logger

from nanobot.profiler.profile import (
    ModelProfile,
    CapabilityScores,
    GuardrailRecommendations,
    PROFILE_VERSION,
)
from nanobot.profiler.tests import (
    TestCase,
    TestResult,
    TestSuite,
    TestCategory,
    ValidationType,
)

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider


class ModelInterviewer:
    """
    Evaluates models like HR evaluates job candidates.
    
    Uses a high-reasoning model to conduct and evaluate tests,
    then synthesizes results into a comprehensive capability profile.
    """
    
    DEFAULT_INTERVIEWER = "anthropic/claude-opus-4-5"
    
    def __init__(
        self,
        provider: "LLMProvider",
        interviewer_model: str | None = None,
        workspace: Path | None = None,
    ):
        """
        Initialize the model interviewer.
        
        Args:
            provider: LLM provider for making API calls.
            interviewer_model: Model to use for evaluation (high-reasoning).
            workspace: Optional workspace path for logging.
        """
        self.provider = provider
        self.interviewer_model = interviewer_model or self.DEFAULT_INTERVIEWER
        self.workspace = workspace
        self.test_suite = TestSuite()
    
    async def interview(
        self,
        model_id: str,
        categories: list[TestCategory] | None = None,
        progress_callback: Any = None,
    ) -> ModelProfile:
        """
        Run comprehensive evaluation of a model.
        
        Args:
            model_id: The model to interview.
            categories: Specific categories to test (None = all).
            progress_callback: Optional callback for progress updates.
        
        Returns:
            Complete ModelProfile with scores and recommendations.
        """
        logger.info(f"Starting interview for model: {model_id}")
        logger.info(f"Interviewer: {self.interviewer_model}")
        
        # Get tests to run
        if categories:
            tests = []
            for cat in categories:
                tests.extend(self.test_suite.get_tests_by_category(cat))
        else:
            tests = self.test_suite.get_all_tests()
        
        logger.info(f"Running {len(tests)} tests...")
        
        # Run all tests
        results: list[TestResult] = []
        for i, test in enumerate(tests):
            if progress_callback:
                progress_callback(i + 1, len(tests), test.name)
            
            result = await self._run_test(model_id, test)
            results.append(result)
            
            status = "PASS" if result.passed else "FAIL"
            logger.debug(f"[{i+1}/{len(tests)}] {test.name}: {status} ({result.score:.2f})")
        
        # Synthesize into profile
        profile = await self._synthesize_profile(model_id, results)
        
        logger.info(f"Interview complete. Overall score: {profile.get_overall_score():.2f}")
        
        return profile
    
    async def quick_assessment(
        self,
        model_id: str,
        progress_callback: Any = None,
    ) -> ModelProfile:
        """
        Fast assessment using subset of critical tests.
        
        Args:
            model_id: The model to assess.
            progress_callback: Optional callback for progress updates.
        
        Returns:
            ModelProfile based on quick assessment.
        """
        logger.info(f"Quick assessment for model: {model_id}")
        
        tests = self.test_suite.get_quick_tests()
        logger.info(f"Running {len(tests)} quick tests...")
        
        results: list[TestResult] = []
        for i, test in enumerate(tests):
            if progress_callback:
                progress_callback(i + 1, len(tests), test.name)
            
            result = await self._run_test(model_id, test)
            results.append(result)
        
        # Synthesize with quick flag
        profile = await self._synthesize_profile(model_id, results, quick=True)
        
        return profile
    
    async def _run_test(
        self,
        model_id: str,
        test: TestCase,
    ) -> TestResult:
        """Run a single test against the candidate model."""
        start_time = time.time()
        
        try:
            # Build messages
            messages = []
            
            if test.system_prompt:
                messages.append({"role": "system", "content": test.system_prompt})
            
            # Add context if present
            prompt = test.prompt
            if test.context:
                prompt = f"Context:\n{test.context}\n\n{test.prompt}"
            
            messages.append({"role": "user", "content": prompt})
            
            # Call the candidate model
            response = await asyncio.wait_for(
                self.provider.chat(
                    messages=messages,
                    model=model_id,
                    tools=test.tools,
                    max_tokens=test.max_tokens,
                    temperature=0.7,
                ),
                timeout=test.timeout,
            )
            
            execution_time = time.time() - start_time
            
            # Extract output
            actual_output = response.content or ""
            tool_calls = []
            
            if response.tool_calls:
                tool_calls = [
                    {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                    for tc in response.tool_calls
                ]
            
            # Validate response
            score, notes, passed = await self._validate_response(
                test, actual_output, tool_calls
            )
            
            return TestResult(
                test_id=test.id,
                passed=passed,
                score=score,
                actual_output=actual_output[:1000],  # Truncate for storage
                evaluation_notes=notes,
                execution_time=execution_time,
                tool_calls_made=tool_calls,
            )
            
        except asyncio.TimeoutError:
            return TestResult(
                test_id=test.id,
                passed=False,
                score=0.0,
                actual_output="",
                evaluation_notes="Test timed out",
                execution_time=test.timeout,
                error="Timeout",
            )
            
        except Exception as e:
            logger.error(f"Test {test.id} failed with error: {e}")
            return TestResult(
                test_id=test.id,
                passed=False,
                score=0.0,
                actual_output="",
                evaluation_notes=f"Error: {str(e)}",
                execution_time=time.time() - start_time,
                error=str(e),
            )
    
    async def _validate_response(
        self,
        test: TestCase,
        output: str,
        tool_calls: list[dict],
    ) -> tuple[float, str, bool]:
        """
        Validate a response based on validation type.
        
        Returns:
            Tuple of (score, notes, passed).
        """
        vtype = test.validation_type
        expected = test.expected_output
        
        if vtype == ValidationType.EXACT:
            passed = output.strip() == expected
            return (1.0 if passed else 0.0, "Exact match" if passed else "No match", passed)
        
        elif vtype == ValidationType.CONTAINS:
            if isinstance(expected, str):
                passed = expected.lower() in output.lower()
                return (1.0 if passed else 0.0, f"Contains '{expected}'" if passed else f"Missing '{expected}'", passed)
            return (0.0, "Invalid expected output", False)
        
        elif vtype == ValidationType.NOT_CONTAINS:
            if isinstance(expected, str):
                passed = expected.lower() not in output.lower()
                return (1.0 if passed else 0.0, f"Correctly avoided '{expected}'" if passed else f"Contains forbidden '{expected}'", passed)
            return (0.0, "Invalid expected output", False)
        
        elif vtype == ValidationType.JSON_VALID:
            try:
                # Try to extract JSON from response
                json_match = re.search(r'[\[\{].*[\]\}]', output, re.DOTALL)
                if json_match:
                    json.loads(json_match.group())
                    return (1.0, "Valid JSON", True)
                else:
                    json.loads(output)
                    return (1.0, "Valid JSON", True)
            except json.JSONDecodeError:
                return (0.0, "Invalid JSON", False)
        
        elif vtype == ValidationType.TOOL_CALL:
            if not tool_calls:
                return (0.0, "No tool call made", False)
            
            if isinstance(expected, dict):
                expected_name = expected.get("name")
                expected_args = expected.get("args_contain", {})
                
                # Check if any tool call matches
                for tc in tool_calls:
                    if tc.get("name") == expected_name:
                        # Check arguments
                        args = tc.get("arguments", {})
                        args_match = all(
                            str(v).lower() in str(args.get(k, "")).lower()
                            for k, v in expected_args.items()
                        )
                        if args_match:
                            return (1.0, f"Correct tool call: {expected_name}", True)
                        else:
                            return (0.5, "Correct tool but missing/wrong arguments", False)
                
                # Wrong tool called
                called = [tc.get("name") for tc in tool_calls]
                return (0.2, f"Wrong tool(s): {called}, expected {expected_name}", False)
            
            return (0.5, "Tool called but validation unclear", True)
        
        elif vtype == ValidationType.EVALUATOR:
            # Use interviewer model to evaluate
            return await self._evaluate_with_interviewer(test, output, tool_calls)
        
        elif vtype == ValidationType.REGEX:
            if isinstance(expected, str):
                passed = bool(re.search(expected, output))
                return (1.0 if passed else 0.0, "Regex match" if passed else "No regex match", passed)
            return (0.0, "Invalid regex pattern", False)
        
        # Default
        return (0.5, "Unknown validation type", True)
    
    async def _evaluate_with_interviewer(
        self,
        test: TestCase,
        output: str,
        tool_calls: list[dict],
    ) -> tuple[float, str, bool]:
        """Use the interviewer model to evaluate a subjective response."""
        
        prompt = f"""You are evaluating an AI model's response to a test.

TEST NAME: {test.name}
TEST PROMPT: {test.prompt}
{f"SYSTEM PROMPT: {test.system_prompt}" if test.system_prompt else ""}
{f"CONTEXT PROVIDED: {test.context[:500]}..." if test.context else ""}

EXPECTED BEHAVIOR: {test.expected_behavior}
SPECIFIC CRITERIA: {test.expected_output or "N/A"}

MODEL'S RESPONSE:
{output[:2000]}

{f"TOOL CALLS MADE: {json.dumps(tool_calls)}" if tool_calls else "NO TOOL CALLS"}

Evaluate this response. Consider:
1. Did the model meet the expected behavior?
2. Did it follow the specific criteria?
3. Any notable strengths or weaknesses?

Respond with JSON only:
{{
    "score": <float 0.0-1.0>,
    "passed": <true/false>,
    "notes": "<brief evaluation notes>"
}}"""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.interviewer_model,
                max_tokens=500,
                temperature=0.3,
            )
            
            content = response.content or ""
            
            # Parse JSON from response (handles nested objects)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    # Try simpler extraction if nested parse fails
                    json_match = re.search(r'\{[^{}]*\}', content)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise
                score = float(result.get("score", 0.5))
                passed = result.get("passed", score >= 0.6)
                notes = result.get("notes", "Evaluated by interviewer")
                return (score, notes, passed)
            
            # Fallback parsing
            if "pass" in content.lower():
                return (0.8, "Evaluation indicates pass", True)
            elif "fail" in content.lower():
                return (0.3, "Evaluation indicates fail", False)
            
            return (0.5, "Could not parse evaluation", True)
            
        except Exception as e:
            logger.warning(f"Interviewer evaluation failed: {e}")
            return (0.5, f"Evaluation error: {str(e)}", True)
    
    async def _synthesize_profile(
        self,
        model_id: str,
        results: list[TestResult],
        quick: bool = False,
    ) -> ModelProfile:
        """Synthesize test results into a comprehensive profile."""
        
        # Calculate capability scores from test results
        category_scores: dict[str, list[float]] = {}
        category_weights: dict[str, list[float]] = {}
        
        for result in results:
            # Find the test to get its category
            test = self._find_test(result.test_id)
            if test:
                cat = test.category.value
                if cat not in category_scores:
                    category_scores[cat] = []
                    category_weights[cat] = []
                category_scores[cat].append(result.score)
                category_weights[cat].append(test.weight)
        
        # Calculate weighted averages per category
        capability_avgs = {}
        for cat, scores in category_scores.items():
            weights = category_weights[cat]
            weighted_sum = sum(s * w for s, w in zip(scores, weights))
            weight_sum = sum(weights)
            capability_avgs[cat] = weighted_sum / weight_sum if weight_sum > 0 else 0.0
        
        # Map to capability fields
        caps = CapabilityScores(
            tool_calling_accuracy=capability_avgs.get("tool_calling", 0.5),
            instruction_following=capability_avgs.get("instruction", 0.5),
            context_utilization=capability_avgs.get("context", 0.5),
            code_generation=capability_avgs.get("code", 0.5),
            reasoning_depth=capability_avgs.get("reasoning", 0.5),
            hallucination_resistance=capability_avgs.get("hallucination", 0.5),
            structured_output=capability_avgs.get("instruction", 0.5) * 0.9,  # Derived
            long_context_handling=capability_avgs.get("context", 0.5) * 0.9,  # Derived
        )
        
        # Use interviewer to synthesize qualitative assessment
        synthesis = await self._get_synthesis_from_interviewer(model_id, results, caps)
        
        # Build guardrail recommendations based on scores
        guardrails = self._determine_guardrails(caps, results)
        
        return ModelProfile(
            model_id=model_id,
            profile_version=PROFILE_VERSION,
            interviewer_model=self.interviewer_model,
            capabilities=caps,
            strengths=synthesis.get("strengths", []),
            weaknesses=synthesis.get("weaknesses", []),
            optimal_tasks=synthesis.get("optimal_tasks", []),
            avoid_tasks=synthesis.get("avoid_tasks", []),
            guardrails=guardrails,
            interview_notes=synthesis.get("notes", ""),
        )
    
    async def _get_synthesis_from_interviewer(
        self,
        model_id: str,
        results: list[TestResult],
        caps: CapabilityScores,
    ) -> dict[str, Any]:
        """Get qualitative synthesis from interviewer model."""
        
        # Build summary of results
        results_summary = []
        for result in results:
            test = self._find_test(result.test_id)
            if test:
                status = "PASS" if result.passed else "FAIL"
                results_summary.append(
                    f"- {test.category.value}/{test.name}: {status} ({result.score:.2f}) - {result.evaluation_notes}"
                )
        
        prompt = f"""You are synthesizing interview results for an AI model evaluation.

MODEL: {model_id}

CAPABILITY SCORES:
- Tool Calling: {caps.tool_calling_accuracy:.2f}
- Instruction Following: {caps.instruction_following:.2f}
- Context Utilization: {caps.context_utilization:.2f}
- Code Generation: {caps.code_generation:.2f}
- Reasoning: {caps.reasoning_depth:.2f}
- Hallucination Resistance: {caps.hallucination_resistance:.2f}

TEST RESULTS:
{chr(10).join(results_summary[:20])}

Based on these results, provide a synthesis. Respond with JSON only:
{{
    "strengths": ["strength1", "strength2", "strength3"],
    "weaknesses": ["weakness1", "weakness2"],
    "optimal_tasks": ["task1", "task2", "task3"],
    "avoid_tasks": ["task1", "task2"],
    "notes": "Brief overall assessment"
}}

Be specific and base conclusions on the actual test results."""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.interviewer_model,
                max_tokens=800,
                temperature=0.3,
            )
            
            content = response.content or ""
            json_match = re.search(r'\{[\s\S]*\}', content)
            
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            logger.warning(f"Synthesis failed: {e}")
        
        # Fallback based on scores
        return self._fallback_synthesis(caps)
    
    def _fallback_synthesis(self, caps: CapabilityScores) -> dict[str, Any]:
        """Generate fallback synthesis based on scores."""
        strengths = []
        weaknesses = []
        optimal_tasks = []
        avoid_tasks = []
        
        if caps.tool_calling_accuracy >= 0.8:
            strengths.append("Reliable tool calling")
            optimal_tasks.append("automated tasks")
        elif caps.tool_calling_accuracy < 0.6:
            weaknesses.append("Inconsistent tool calling")
            avoid_tasks.append("complex tool workflows")
        
        if caps.instruction_following >= 0.8:
            strengths.append("Strong instruction following")
        elif caps.instruction_following < 0.6:
            weaknesses.append("May deviate from instructions")
        
        if caps.code_generation >= 0.8:
            strengths.append("Quality code generation")
            optimal_tasks.extend(["coding", "implementation"])
        elif caps.code_generation < 0.6:
            weaknesses.append("Code quality issues")
            avoid_tasks.append("complex coding")
        
        if caps.reasoning_depth >= 0.8:
            strengths.append("Strong reasoning ability")
            optimal_tasks.extend(["analysis", "problem-solving"])
        elif caps.reasoning_depth < 0.6:
            weaknesses.append("Limited reasoning depth")
            avoid_tasks.append("complex analysis")
        
        if caps.hallucination_resistance >= 0.8:
            strengths.append("Factual accuracy")
            optimal_tasks.append("research")
        elif caps.hallucination_resistance < 0.6:
            weaknesses.append("Prone to hallucination")
            avoid_tasks.append("fact-critical tasks")
        
        return {
            "strengths": strengths[:5],
            "weaknesses": weaknesses[:5],
            "optimal_tasks": list(set(optimal_tasks))[:5],
            "avoid_tasks": list(set(avoid_tasks))[:5],
            "notes": "Profile synthesized from capability scores",
        }
    
    def _determine_guardrails(
        self,
        caps: CapabilityScores,
        results: list[TestResult],
    ) -> GuardrailRecommendations:
        """Determine recommended guardrails based on evaluation."""
        
        # Check for specific failure patterns
        tool_failures = sum(1 for r in results if "tool" in r.test_id.lower() and not r.passed)
        format_failures = sum(1 for r in results if "format" in r.test_id.lower() and not r.passed)
        
        return GuardrailRecommendations(
            needs_structured_output=caps.structured_output < 0.7 or format_failures > 0,
            needs_explicit_format=caps.instruction_following < 0.8,
            needs_tool_examples=caps.tool_calling_accuracy < 0.8 or tool_failures > 1,
            max_reliable_context=128000 if caps.long_context_handling >= 0.7 else 64000,
            recommended_temperature=0.5 if caps.hallucination_resistance < 0.7 else 0.7,
            tool_call_retry_limit=2 if caps.tool_calling_accuracy < 0.7 else 3,
            needs_step_by_step=caps.reasoning_depth < 0.7,
            avoid_parallel_tools=caps.tool_calling_accuracy < 0.6,
        )
    
    def _find_test(self, test_id: str) -> TestCase | None:
        """Find a test case by ID."""
        for test in self.test_suite.get_all_tests():
            if test.id == test_id:
                return test
        return None
