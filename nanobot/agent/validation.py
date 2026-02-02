"""
Visual validation for GigaBot.

Provides screenshot-based validation of UI changes.
Inspired by Kimi K2.5's visual coding capabilities.
"""

import base64
import re
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.agent.tools.browser import BrowserTool
    from nanobot.providers.base import LLMProvider


@dataclass
class ValidationIssue:
    """A single validation issue found."""
    severity: str  # "error", "warning", "info"
    description: str
    suggestion: str = ""
    element: str = ""  # CSS selector or description


@dataclass
class ValidationResult:
    """Result of visual validation."""
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    screenshot_taken: bool = False
    analysis: str = ""
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")
    
    def get_issues_summary(self) -> str:
        """Get a summary of issues for display."""
        if not self.issues:
            return "No issues found"
        
        lines = []
        for issue in self.issues:
            prefix = {"error": "[ERROR]", "warning": "[WARN]", "info": "[INFO]"}.get(
                issue.severity, "[?]"
            )
            lines.append(f"{prefix} {issue.description}")
            if issue.suggestion:
                lines.append(f"  Fix: {issue.suggestion}")
        
        return "\n".join(lines)


class VisualValidator:
    """
    Validates UI work by taking screenshots and analyzing them.
    
    Uses a vision-capable model to analyze screenshots and verify
    that expected elements are present and visual requirements are met.
    
    Inspired by Kimi K2.5's visual coding capabilities.
    """
    
    def __init__(
        self,
        browser_tool: "BrowserTool",
        provider: "LLMProvider",
        vision_model: str = "anthropic/claude-sonnet-4-5",
    ):
        """
        Initialize VisualValidator.
        
        Args:
            browser_tool: Browser tool for navigation and screenshots.
            provider: LLM provider for vision analysis.
            vision_model: Model to use for visual analysis (must support vision).
        """
        self.browser = browser_tool
        self.provider = provider
        self.vision_model = vision_model
    
    async def validate_ui(
        self,
        url: str,
        expected_elements: list[str] | None = None,
        visual_checks: list[str] | None = None,
        wait_ms: int = 2000,
    ) -> ValidationResult:
        """
        Navigate to a URL, take a screenshot, and analyze it.
        
        Args:
            url: URL to validate.
            expected_elements: CSS selectors or descriptions of elements that should exist.
            visual_checks: Natural language descriptions of expected visual properties.
            wait_ms: Time to wait after navigation before screenshot.
        
        Returns:
            ValidationResult with analysis and any issues found.
        """
        expected_elements = expected_elements or []
        visual_checks = visual_checks or []
        
        try:
            # Navigate to URL
            nav_result = await self.browser.execute(
                action="navigate",
                url=url,
                wait_ms=wait_ms
            )
            logger.debug(f"Navigation result: {nav_result}")
            
            # Take screenshot
            screenshot_result = await self.browser.execute(action="screenshot")
            
            # Extract base64 from result
            screenshot_b64 = self._extract_screenshot_b64(screenshot_result)
            
            if not screenshot_b64:
                return ValidationResult(
                    passed=False,
                    screenshot_taken=False,
                    analysis="Failed to capture screenshot",
                    issues=[ValidationIssue(
                        severity="error",
                        description="Screenshot capture failed",
                        suggestion="Check if browser tool is working correctly"
                    )]
                )
            
            # Analyze with vision model
            analysis_result = await self._analyze_screenshot(
                screenshot_b64,
                expected_elements,
                visual_checks,
                url
            )
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Visual validation error: {e}")
            return ValidationResult(
                passed=False,
                screenshot_taken=False,
                analysis=f"Validation error: {str(e)}",
                issues=[ValidationIssue(
                    severity="error",
                    description=str(e),
                )]
            )
    
    async def validate_screenshot(
        self,
        screenshot_b64: str,
        expected_elements: list[str] | None = None,
        visual_checks: list[str] | None = None,
    ) -> ValidationResult:
        """
        Analyze an existing screenshot.
        
        Args:
            screenshot_b64: Base64-encoded screenshot.
            expected_elements: Elements that should be present.
            visual_checks: Visual requirements to verify.
        
        Returns:
            ValidationResult with analysis.
        """
        expected_elements = expected_elements or []
        visual_checks = visual_checks or []
        
        return await self._analyze_screenshot(
            screenshot_b64,
            expected_elements,
            visual_checks,
            url="(provided screenshot)"
        )
    
    def _extract_screenshot_b64(self, screenshot_result: str) -> str | None:
        """Extract base64 data from screenshot result."""
        # The browser tool returns format like:
        # "Screenshot taken (N bytes). Base64 preview: <base64>..."
        
        # Try to find base64 data
        match = re.search(r'Base64[^:]*:\s*([A-Za-z0-9+/=]+)', screenshot_result)
        if match:
            b64 = match.group(1)
            # The preview might be truncated, so this won't work for analysis
            # We need the full screenshot
            
        # For now, try to get from the browser's internal state
        # This is a simplified approach - in production, we'd store the full screenshot
        if hasattr(self.browser, '_last_screenshot_b64'):
            return self.browser._last_screenshot_b64
        
        # Fallback: look for full base64 in result
        # Pattern for base64-encoded PNG
        match = re.search(r'([A-Za-z0-9+/]{100,}={0,2})', screenshot_result)
        if match:
            return match.group(1)
        
        return None
    
    async def _analyze_screenshot(
        self,
        screenshot_b64: str,
        expected_elements: list[str],
        visual_checks: list[str],
        url: str,
    ) -> ValidationResult:
        """
        Use vision model to analyze screenshot.
        
        Args:
            screenshot_b64: Base64-encoded screenshot.
            expected_elements: Elements to check for.
            visual_checks: Visual requirements.
            url: URL for context.
        
        Returns:
            ValidationResult with analysis.
        """
        # Build analysis prompt
        prompt_parts = [
            "Analyze this screenshot of a web page and provide a validation report.",
            f"\nURL: {url}",
        ]
        
        if expected_elements:
            prompt_parts.append("\n\nExpected elements (verify these are visible):")
            for el in expected_elements:
                prompt_parts.append(f"  - {el}")
        
        if visual_checks:
            prompt_parts.append("\n\nVisual requirements to verify:")
            for vc in visual_checks:
                prompt_parts.append(f"  - {vc}")
        
        prompt_parts.append("""

Provide your analysis in this format:
1. OVERALL: PASS or FAIL
2. ISSUES: List any problems found (prefix with [ERROR], [WARN], or [INFO])
3. SUGGESTIONS: How to fix any issues
4. SUMMARY: Brief description of what you see

Be specific about element locations and visual problems.""")
        
        prompt = "\n".join(prompt_parts)
        
        try:
            response = await self.provider.chat(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_b64}"
                            }
                        }
                    ]
                }],
                model=self.vision_model,
                max_tokens=2000,
            )
            
            analysis = response.content or ""
            
            # Parse the response
            return self._parse_analysis_response(analysis)
            
        except Exception as e:
            logger.error(f"Vision analysis error: {e}")
            return ValidationResult(
                passed=False,
                screenshot_taken=True,
                analysis=f"Analysis failed: {str(e)}",
                issues=[ValidationIssue(
                    severity="error",
                    description=f"Vision model error: {str(e)}",
                )]
            )
    
    def _parse_analysis_response(self, analysis: str) -> ValidationResult:
        """Parse the vision model's analysis response."""
        # Check for overall pass/fail
        passed = "PASS" in analysis.upper() and "FAIL" not in analysis.upper()
        
        # Also check for positive indicators
        if "no issues" in analysis.lower() or "looks good" in analysis.lower():
            passed = True
        
        # Extract issues
        issues = []
        
        # Find error lines
        error_pattern = r'\[ERROR\][:\s]*(.+?)(?=\n|$)'
        for match in re.finditer(error_pattern, analysis, re.IGNORECASE):
            issues.append(ValidationIssue(
                severity="error",
                description=match.group(1).strip()
            ))
        
        # Find warning lines
        warn_pattern = r'\[WARN(?:ING)?\][:\s]*(.+?)(?=\n|$)'
        for match in re.finditer(warn_pattern, analysis, re.IGNORECASE):
            issues.append(ValidationIssue(
                severity="warning",
                description=match.group(1).strip()
            ))
        
        # Find info lines
        info_pattern = r'\[INFO\][:\s]*(.+?)(?=\n|$)'
        for match in re.finditer(info_pattern, analysis, re.IGNORECASE):
            issues.append(ValidationIssue(
                severity="info",
                description=match.group(1).strip()
            ))
        
        # If we found errors, it's a fail
        if any(i.severity == "error" for i in issues):
            passed = False
        
        return ValidationResult(
            passed=passed,
            screenshot_taken=True,
            analysis=analysis,
            issues=issues,
        )
    
    async def quick_check(self, url: str, description: str = "") -> ValidationResult:
        """
        Quick visual check without specific requirements.
        
        Args:
            url: URL to check.
            description: Optional description of what to look for.
        
        Returns:
            ValidationResult with general analysis.
        """
        visual_checks = []
        if description:
            visual_checks.append(description)
        else:
            visual_checks.append("Page loads correctly without errors")
            visual_checks.append("Layout appears normal and usable")
            visual_checks.append("No obvious visual bugs or broken elements")
        
        return await self.validate_ui(
            url=url,
            visual_checks=visual_checks,
        )


class ValidationLoop:
    """
    Manages validation with automatic retry and fix suggestions.
    """
    
    def __init__(
        self,
        validator: VisualValidator,
        max_iterations: int = 5,
    ):
        self.validator = validator
        self.max_iterations = max_iterations
        self.history: list[ValidationResult] = []
    
    async def run(
        self,
        url: str,
        expected_elements: list[str] | None = None,
        visual_checks: list[str] | None = None,
        on_failure: Any = None,  # Callable to fix issues
    ) -> tuple[bool, list[ValidationResult]]:
        """
        Run validation loop with automatic retries.
        
        Args:
            url: URL to validate.
            expected_elements: Elements to check.
            visual_checks: Visual requirements.
            on_failure: Optional callback to fix issues between iterations.
        
        Returns:
            Tuple of (final_success, history_of_results).
        """
        self.history = []
        
        for iteration in range(self.max_iterations):
            logger.info(f"Validation iteration {iteration + 1}/{self.max_iterations}")
            
            result = await self.validator.validate_ui(
                url=url,
                expected_elements=expected_elements,
                visual_checks=visual_checks,
            )
            
            self.history.append(result)
            
            if result.passed:
                logger.info("Validation passed!")
                return True, self.history
            
            logger.warning(f"Validation failed: {result.error_count} errors")
            
            # Try to fix issues if callback provided
            if on_failure and callable(on_failure):
                try:
                    await on_failure(result)
                except Exception as e:
                    logger.error(f"Fix callback failed: {e}")
            else:
                # No fix callback, stop retrying
                break
        
        logger.error(f"Validation failed after {len(self.history)} iterations")
        return False, self.history
