"""
Agentic Development Workflow for GigaBot.

Provides an autonomous development workflow that:
1. Makes code changes
2. Starts dev server
3. Takes screenshots
4. Validates visually
5. Fixes issues automatically

Inspired by Kimi K2.5's visual coding capabilities.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.agent.tools.process import ProcessTool
    from nanobot.agent.tools.browser import BrowserTool
    from nanobot.agent.validation import VisualValidator, ValidationResult
    from nanobot.providers.base import LLMProvider


@dataclass
class WorkflowStep:
    """A single step in the workflow."""
    name: str
    status: str = "pending"  # pending, running, success, failed, skipped
    output: str = ""
    duration_ms: int = 0
    error: str = ""


@dataclass
class WorkflowResult:
    """Result of a development workflow."""
    success: bool
    iterations: int
    steps: list[WorkflowStep] = field(default_factory=list)
    final_message: str = ""
    changes_made: list[str] = field(default_factory=list)
    validation_results: list["ValidationResult"] = field(default_factory=list)
    
    def get_summary(self) -> str:
        """Get a summary of the workflow execution."""
        lines = [
            f"Workflow {'succeeded' if self.success else 'failed'} after {self.iterations} iteration(s)",
            "",
            "Steps:"
        ]
        
        for step in self.steps:
            status_icon = {
                "success": "✓",
                "failed": "✗",
                "skipped": "○",
                "running": "→",
                "pending": "·"
            }.get(step.status, "?")
            
            lines.append(f"  {status_icon} {step.name}: {step.status}")
            if step.error:
                lines.append(f"      Error: {step.error}")
        
        if self.changes_made:
            lines.append("")
            lines.append(f"Changes: {len(self.changes_made)} files modified")
        
        return "\n".join(lines)


class AgenticDevWorkflow:
    """
    Autonomous development workflow with visual validation.
    
    This workflow manages the complete development cycle:
    1. Implement code changes (via agent)
    2. Start/restart dev server
    3. Wait for server ready
    4. Take screenshot and validate
    5. If issues found, create fix task and loop
    
    Inspired by Kimi K2.5's Agent Swarm for autonomous coding.
    """
    
    def __init__(
        self,
        process_tool: "ProcessTool",
        browser_tool: "BrowserTool",
        provider: "LLMProvider",
        workspace: Path,
        vision_model: str = "anthropic/claude-sonnet-4-5",
    ):
        """
        Initialize AgenticDevWorkflow.
        
        Args:
            process_tool: Process tool for dev server management.
            browser_tool: Browser tool for navigation and screenshots.
            provider: LLM provider for code generation and visual analysis.
            workspace: Workspace directory.
            vision_model: Model to use for visual validation.
        """
        self.process_tool = process_tool
        self.browser_tool = browser_tool
        self.provider = provider
        self.workspace = workspace
        self.vision_model = vision_model
        
        # Lazy import to avoid circular dependencies
        self._validator = None
    
    @property
    def validator(self) -> "VisualValidator":
        """Get or create the visual validator."""
        if self._validator is None:
            from nanobot.agent.validation import VisualValidator
            self._validator = VisualValidator(
                browser_tool=self.browser_tool,
                provider=self.provider,
                vision_model=self.vision_model,
            )
        return self._validator
    
    async def run(
        self,
        task: str,
        dev_command: str = "npm run dev",
        port: int = 3000,
        url: str | None = None,
        max_iterations: int = 5,
        implement_callback: Callable[[str], Any] | None = None,
        expected_elements: list[str] | None = None,
        visual_checks: list[str] | None = None,
        auto_fix: bool = True,
    ) -> WorkflowResult:
        """
        Execute the full development workflow with visual validation.
        
        Args:
            task: The development task description.
            dev_command: Command to start the dev server.
            port: Port the dev server runs on.
            url: URL to validate (defaults to http://localhost:{port}).
            max_iterations: Maximum fix iterations.
            implement_callback: Callback to implement code changes.
            expected_elements: Elements to verify in screenshots.
            visual_checks: Visual requirements to verify.
            auto_fix: Whether to automatically attempt fixes.
        
        Returns:
            WorkflowResult with success status and details.
        """
        url = url or f"http://localhost:{port}"
        expected_elements = expected_elements or []
        visual_checks = visual_checks or []
        
        steps: list[WorkflowStep] = []
        validation_results: list["ValidationResult"] = []
        changes_made: list[str] = []
        
        current_task = task
        
        for iteration in range(max_iterations):
            logger.info(f"Dev workflow iteration {iteration + 1}/{max_iterations}")
            
            # Step 1: Implement changes
            impl_step = WorkflowStep(name=f"implement_changes_{iteration + 1}")
            impl_step.status = "running"
            steps.append(impl_step)
            
            try:
                if implement_callback:
                    import time
                    start = time.time()
                    result = await implement_callback(current_task)
                    impl_step.duration_ms = int((time.time() - start) * 1000)
                    impl_step.output = str(result) if result else "Changes implemented"
                    impl_step.status = "success"
                    if result:
                        changes_made.append(f"Iteration {iteration + 1}: {current_task[:50]}")
                else:
                    impl_step.output = "No implementation callback provided"
                    impl_step.status = "skipped" if iteration == 0 else "skipped"
            except Exception as e:
                impl_step.status = "failed"
                impl_step.error = str(e)
                logger.error(f"Implementation failed: {e}")
                continue
            
            # Step 2: Start/restart dev server
            server_step = WorkflowStep(name=f"start_dev_server_{iteration + 1}")
            server_step.status = "running"
            steps.append(server_step)
            
            try:
                import time
                start = time.time()
                server_result = await self.process_tool.execute(
                    action="start_dev_server",
                    command=dev_command,
                    port=port,
                    working_dir=str(self.workspace),
                )
                server_step.duration_ms = int((time.time() - start) * 1000)
                server_step.output = server_result
                
                if "error" in server_result.lower():
                    server_step.status = "failed"
                    server_step.error = server_result
                else:
                    server_step.status = "success"
            except Exception as e:
                server_step.status = "failed"
                server_step.error = str(e)
                logger.error(f"Dev server start failed: {e}")
                continue
            
            # Step 3: Wait for server and stabilize
            await asyncio.sleep(2)  # Brief wait for server to stabilize
            
            # Step 4: Validate with screenshot
            validate_step = WorkflowStep(name=f"validate_ui_{iteration + 1}")
            validate_step.status = "running"
            steps.append(validate_step)
            
            try:
                import time
                start = time.time()
                validation = await self.validator.validate_ui(
                    url=url,
                    expected_elements=expected_elements,
                    visual_checks=visual_checks,
                    wait_ms=3000,
                )
                validate_step.duration_ms = int((time.time() - start) * 1000)
                validation_results.append(validation)
                
                if validation.passed:
                    validate_step.status = "success"
                    validate_step.output = "Validation passed"
                    
                    return WorkflowResult(
                        success=True,
                        iterations=iteration + 1,
                        steps=steps,
                        final_message="Workflow completed successfully!",
                        changes_made=changes_made,
                        validation_results=validation_results,
                    )
                else:
                    validate_step.status = "failed"
                    validate_step.output = validation.get_issues_summary()
                    validate_step.error = f"{validation.error_count} errors, {validation.warning_count} warnings"
                    
                    if not auto_fix:
                        return WorkflowResult(
                            success=False,
                            iterations=iteration + 1,
                            steps=steps,
                            final_message=f"Validation failed: {validate_step.error}",
                            changes_made=changes_made,
                            validation_results=validation_results,
                        )
                    
                    # Create fix task from validation issues
                    current_task = self._create_fix_task(validation)
                    logger.info(f"Creating fix task: {current_task[:100]}...")
                    
            except Exception as e:
                validate_step.status = "failed"
                validate_step.error = str(e)
                logger.error(f"Validation failed: {e}")
                
                if not auto_fix:
                    break
        
        return WorkflowResult(
            success=False,
            iterations=max_iterations,
            steps=steps,
            final_message=f"Workflow failed after {max_iterations} iterations",
            changes_made=changes_made,
            validation_results=validation_results,
        )
    
    def _create_fix_task(self, validation: "ValidationResult") -> str:
        """Create a fix task from validation issues."""
        issues = []
        for issue in validation.issues:
            issues.append(f"- {issue.description}")
            if issue.suggestion:
                issues.append(f"  Suggestion: {issue.suggestion}")
        
        issues_text = "\n".join(issues)
        
        return f"""Fix the following issues found during visual validation:

{issues_text}

Make the necessary code changes to resolve these issues."""
    
    async def validate_only(
        self,
        url: str,
        expected_elements: list[str] | None = None,
        visual_checks: list[str] | None = None,
    ) -> "ValidationResult":
        """
        Run only the validation step without the full workflow.
        
        Args:
            url: URL to validate.
            expected_elements: Elements to check for.
            visual_checks: Visual requirements.
        
        Returns:
            ValidationResult from the check.
        """
        return await self.validator.validate_ui(
            url=url,
            expected_elements=expected_elements or [],
            visual_checks=visual_checks or [],
        )
    
    async def start_server_only(
        self,
        command: str = "npm run dev",
        port: int = 3000,
    ) -> str:
        """
        Start dev server without full workflow.
        
        Args:
            command: Dev server command.
            port: Port to run on.
        
        Returns:
            Status message.
        """
        return await self.process_tool.execute(
            action="start_dev_server",
            command=command,
            port=port,
            working_dir=str(self.workspace),
        )
    
    async def cleanup(self) -> None:
        """Clean up resources (stop dev servers, close browser)."""
        try:
            await self.process_tool.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
