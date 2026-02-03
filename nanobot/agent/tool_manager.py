"""
Tool Call Manager for GigaBot.

Manages tool execution with:
- Pre-execution validation
- Security policy enforcement
- Retry logic with exponential backoff
- Circuit breaker for failing tools
- Profile-aware retry limits
- Error classification and recovery
"""

import asyncio
import time
import random
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from enum import Enum

from loguru import logger

if TYPE_CHECKING:
    from nanobot.agent.tools.registry import ToolRegistry
    from nanobot.profiler.profile import ModelProfile
    from nanobot.security.policy import ToolPolicy


class ErrorType(str, Enum):
    """Classification of tool execution errors."""
    TRANSIENT = "transient"      # Network issues, timeouts - retry
    PERMANENT = "permanent"       # Invalid params, missing resources - don't retry
    RATE_LIMIT = "rate_limit"     # API limits - retry with backoff
    UNKNOWN = "unknown"           # Unclassified - retry once


@dataclass
class ToolHealth:
    """Health status of a tool."""
    name: str
    consecutive_failures: int = 0
    total_calls: int = 0
    total_failures: int = 0
    last_failure_time: float = 0.0
    circuit_open: bool = False
    circuit_open_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.total_failures) / self.total_calls
    
    def record_success(self) -> None:
        """Record a successful call."""
        self.total_calls += 1
        self.consecutive_failures = 0
        # Reset circuit if it was open
        if self.circuit_open:
            logger.info(f"Circuit closed for tool '{self.name}' after success")
            self.circuit_open = False
    
    def record_failure(self) -> None:
        """Record a failed call."""
        self.total_calls += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()


@dataclass
class ValidationResult:
    """Result of pre-execution validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def __bool__(self) -> bool:
        return self.valid


@dataclass
class PolicyCheckResult:
    """Result of security policy check."""
    allowed: bool
    decision: str = ""  # PolicyDecision value
    reason: str = ""


@dataclass
class ExecutionResult:
    """Result of a tool execution attempt."""
    success: bool
    result: str
    attempts: int
    total_time: float
    error_type: ErrorType | None = None
    circuit_breaker_triggered: bool = False
    validation_errors: list[str] = field(default_factory=list)
    policy_blocked: bool = False


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0          # Initial delay in seconds
    max_delay: float = 30.0          # Maximum delay
    exponential_base: float = 2.0    # Backoff multiplier
    jitter: float = 0.1              # Random jitter factor (0.1 = 10%)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5       # Failures before opening circuit
    reset_timeout: float = 300.0     # Seconds before attempting reset (5 min)
    half_open_max_calls: int = 1     # Calls to allow in half-open state


class ToolCallManager:
    """
    Manages tool execution with retry, validation, and recovery.
    
    Features:
    - Pre-execution parameter validation
    - Security policy enforcement
    - Profile-aware retry limits
    - Exponential backoff with jitter
    - Error classification (transient vs permanent)
    - Circuit breaker for repeatedly failing tools
    - Parameter adjustment on retry
    """
    
    def __init__(
        self,
        registry: "ToolRegistry",
        retry_config: RetryConfig | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        tool_policy: "ToolPolicy | None" = None,
        enable_validation: bool = True,
    ):
        """
        Initialize the tool call manager.
        
        Args:
            registry: Tool registry to execute tools from.
            retry_config: Retry behavior configuration.
            circuit_config: Circuit breaker configuration.
            tool_policy: Security policy for tool access control.
            enable_validation: Enable pre-execution parameter validation.
        """
        self.registry = registry
        self.retry_config = retry_config or RetryConfig()
        self.circuit_config = circuit_config or CircuitBreakerConfig()
        self.tool_policy = tool_policy
        self.enable_validation = enable_validation
        
        # Tool health tracking
        self._tool_health: dict[str, ToolHealth] = {}
    
    def _get_tool_health(self, tool_name: str) -> ToolHealth:
        """Get or create health tracker for a tool."""
        if tool_name not in self._tool_health:
            self._tool_health[tool_name] = ToolHealth(name=tool_name)
        return self._tool_health[tool_name]
    
    def _classify_error(self, error: str) -> ErrorType:
        """Classify an error to determine retry strategy."""
        error_lower = error.lower()
        
        # Transient errors - worth retrying
        transient_patterns = [
            "timeout", "timed out", "connection", "network",
            "temporary", "unavailable", "retry", "econnreset",
            "socket", "dns", "resolve",
        ]
        if any(p in error_lower for p in transient_patterns):
            return ErrorType.TRANSIENT
        
        # Rate limit errors - retry with longer backoff
        rate_limit_patterns = [
            "rate limit", "rate_limit", "too many requests",
            "429", "quota", "throttl",
        ]
        if any(p in error_lower for p in rate_limit_patterns):
            return ErrorType.RATE_LIMIT
        
        # Permanent errors - don't retry
        permanent_patterns = [
            "not found", "invalid", "missing", "required",
            "permission", "denied", "unauthorized", "forbidden",
            "400", "401", "403", "404", "422",
        ]
        if any(p in error_lower for p in permanent_patterns):
            return ErrorType.PERMANENT
        
        return ErrorType.UNKNOWN
    
    def _should_retry(self, error_type: ErrorType, attempt: int, max_retries: int) -> bool:
        """Determine if we should retry based on error type and attempt count."""
        if attempt >= max_retries:
            return False
        
        if error_type == ErrorType.PERMANENT:
            return False
        
        if error_type == ErrorType.TRANSIENT:
            return True
        
        if error_type == ErrorType.RATE_LIMIT:
            return True
        
        # Unknown errors - retry once
        return attempt < 1
    
    def _calculate_delay(
        self,
        attempt: int,
        error_type: ErrorType,
    ) -> float:
        """Calculate delay before next retry."""
        config = self.retry_config
        
        # Base exponential backoff
        delay = config.base_delay * (config.exponential_base ** attempt)
        
        # Rate limits get extra delay
        if error_type == ErrorType.RATE_LIMIT:
            delay *= 2
        
        # Cap at max delay
        delay = min(delay, config.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = delay * config.jitter * random.random()
        delay += jitter
        
        return delay
    
    def _check_circuit_breaker(self, tool_name: str) -> bool:
        """
        Check if circuit breaker allows execution.
        
        Returns:
            True if execution is allowed, False if circuit is open.
        """
        health = self._get_tool_health(tool_name)
        
        if not health.circuit_open:
            return True
        
        # Check if we should try half-open
        elapsed = time.time() - health.circuit_open_time
        if elapsed >= self.circuit_config.reset_timeout:
            logger.info(f"Circuit half-open for tool '{tool_name}', allowing test call")
            return True
        
        return False
    
    def _maybe_open_circuit(self, tool_name: str) -> bool:
        """
        Check if circuit should be opened after failure.
        
        Returns:
            True if circuit was opened.
        """
        health = self._get_tool_health(tool_name)
        
        if health.circuit_open:
            return False
        
        if health.consecutive_failures >= self.circuit_config.failure_threshold:
            health.circuit_open = True
            health.circuit_open_time = time.time()
            logger.warning(
                f"Circuit opened for tool '{tool_name}' after "
                f"{health.consecutive_failures} consecutive failures"
            )
            return True
        
        return False
    
    def validate_parameters(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ValidationResult:
        """
        Validate tool parameters against the tool's schema.
        
        Args:
            tool_name: Name of the tool.
            arguments: Arguments to validate.
        
        Returns:
            ValidationResult with validation status and any errors.
        """
        tool = self.registry.get(tool_name)
        if not tool:
            return ValidationResult(
                valid=False,
                errors=[f"Tool '{tool_name}' not found"],
            )
        
        errors = []
        warnings = []
        schema = tool.parameters
        
        # Check required parameters
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        for req in required:
            if req not in arguments:
                errors.append(f"Missing required parameter: '{req}'")
        
        # Type checking for provided parameters
        for param_name, param_value in arguments.items():
            if param_name not in properties:
                warnings.append(f"Unknown parameter: '{param_name}'")
                continue
            
            param_schema = properties[param_name]
            expected_type = param_schema.get("type")
            
            if expected_type:
                type_valid = self._check_type(param_value, expected_type)
                if not type_valid:
                    errors.append(
                        f"Parameter '{param_name}' should be {expected_type}, "
                        f"got {type(param_value).__name__}"
                    )
            
            # Check enum values
            if "enum" in param_schema:
                if param_value not in param_schema["enum"]:
                    errors.append(
                        f"Parameter '{param_name}' must be one of: {param_schema['enum']}"
                    )
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches the expected JSON schema type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, allow
        
        return isinstance(value, expected)
    
    def check_policy(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        call_id: str = "",
    ) -> PolicyCheckResult:
        """
        Check if tool call is allowed by security policy.
        
        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.
            call_id: Unique call identifier for approval tracking.
        
        Returns:
            PolicyCheckResult with decision.
        """
        if not self.tool_policy:
            return PolicyCheckResult(allowed=True, decision="allow", reason="No policy configured")
        
        from nanobot.security.policy import check_tool_access, PolicyDecision
        
        decision = check_tool_access(
            policy=self.tool_policy,
            tool_name=tool_name,
            call_id=call_id,
            arguments=arguments,
        )
        
        if decision == PolicyDecision.ALLOW:
            return PolicyCheckResult(
                allowed=True,
                decision=decision.value,
                reason="Allowed by policy",
            )
        elif decision == PolicyDecision.DENY:
            return PolicyCheckResult(
                allowed=False,
                decision=decision.value,
                reason=f"Tool '{tool_name}' is denied by security policy",
            )
        elif decision == PolicyDecision.REQUIRE_APPROVAL:
            return PolicyCheckResult(
                allowed=False,
                decision=decision.value,
                reason=f"Tool '{tool_name}' requires approval (call_id: {call_id})",
            )
        elif decision == PolicyDecision.REQUIRE_ELEVATED:
            return PolicyCheckResult(
                allowed=False,
                decision=decision.value,
                reason=f"Tool '{tool_name}' requires elevated mode",
            )
        
        return PolicyCheckResult(
            allowed=False,
            decision="unknown",
            reason="Unknown policy decision",
        )
    
    async def execute_with_retry(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        model_profile: "ModelProfile | None" = None,
        call_id: str = "",
    ) -> ExecutionResult:
        """
        Execute a tool with validation, policy check, and retry logic.
        
        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            model_profile: Optional model profile for retry limits.
            call_id: Unique call identifier for approval tracking.
        
        Returns:
            ExecutionResult with outcome details.
        """
        start_time = time.time()
        
        # 1. Pre-execution validation
        if self.enable_validation:
            validation = self.validate_parameters(tool_name, arguments)
            if not validation.valid:
                return ExecutionResult(
                    success=False,
                    result=f"Validation failed: {'; '.join(validation.errors)}",
                    attempts=0,
                    total_time=time.time() - start_time,
                    validation_errors=validation.errors,
                )
            
            # Log warnings but continue
            for warning in validation.warnings:
                logger.debug(f"Tool validation warning: {warning}")
        
        # 2. Security policy check
        policy_check = self.check_policy(tool_name, arguments, call_id)
        if not policy_check.allowed:
            return ExecutionResult(
                success=False,
                result=f"Policy blocked: {policy_check.reason}",
                attempts=0,
                total_time=time.time() - start_time,
                policy_blocked=True,
            )
        
        # 3. Check circuit breaker
        if not self._check_circuit_breaker(tool_name):
            return ExecutionResult(
                success=False,
                result=f"Error: Tool '{tool_name}' is temporarily disabled (circuit breaker open)",
                attempts=0,
                total_time=0.0,
                circuit_breaker_triggered=True,
            )
        
        # Determine max retries from profile or default
        max_retries = self.retry_config.max_retries
        if model_profile and model_profile.guardrails.tool_call_retry_limit:
            max_retries = model_profile.guardrails.tool_call_retry_limit
        
        health = self._get_tool_health(tool_name)
        last_error = ""
        last_error_type = None
        
        for attempt in range(max_retries + 1):
            try:
                # Execute the tool
                result = await self.registry.execute(tool_name, arguments)
                
                # Check if result indicates an error
                if result.startswith("Error:"):
                    error_type = self._classify_error(result)
                    last_error = result
                    last_error_type = error_type
                    
                    health.record_failure()
                    
                    if self._should_retry(error_type, attempt, max_retries):
                        delay = self._calculate_delay(attempt, error_type)
                        logger.debug(
                            f"Tool '{tool_name}' failed (attempt {attempt + 1}), "
                            f"retrying in {delay:.1f}s: {result[:100]}"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # No more retries
                        self._maybe_open_circuit(tool_name)
                        return ExecutionResult(
                            success=False,
                            result=result,
                            attempts=attempt + 1,
                            total_time=time.time() - start_time,
                            error_type=error_type,
                        )
                
                # Success
                health.record_success()
                return ExecutionResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_time=time.time() - start_time,
                )
                
            except asyncio.TimeoutError:
                health.record_failure()
                last_error = "Error: Tool execution timed out"
                last_error_type = ErrorType.TRANSIENT
                
                if self._should_retry(ErrorType.TRANSIENT, attempt, max_retries):
                    delay = self._calculate_delay(attempt, ErrorType.TRANSIENT)
                    logger.debug(f"Tool '{tool_name}' timed out, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
                
            except Exception as e:
                health.record_failure()
                last_error = f"Error: {str(e)}"
                last_error_type = self._classify_error(str(e))
                
                if self._should_retry(last_error_type, attempt, max_retries):
                    delay = self._calculate_delay(attempt, last_error_type)
                    logger.debug(f"Tool '{tool_name}' failed, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
        
        # All retries exhausted
        self._maybe_open_circuit(tool_name)
        return ExecutionResult(
            success=False,
            result=last_error or f"Error: Tool '{tool_name}' failed after {max_retries + 1} attempts",
            attempts=max_retries + 1,
            total_time=time.time() - start_time,
            error_type=last_error_type,
        )
    
    def get_tool_health(self, tool_name: str) -> dict[str, Any]:
        """Get health status for a tool."""
        health = self._get_tool_health(tool_name)
        return {
            "name": health.name,
            "total_calls": health.total_calls,
            "total_failures": health.total_failures,
            "success_rate": health.success_rate,
            "consecutive_failures": health.consecutive_failures,
            "circuit_open": health.circuit_open,
        }
    
    def get_all_tool_health(self) -> dict[str, dict[str, Any]]:
        """Get health status for all tracked tools."""
        return {
            name: self.get_tool_health(name)
            for name in self._tool_health.keys()
        }
    
    def reset_circuit(self, tool_name: str) -> bool:
        """Manually reset a tool's circuit breaker."""
        health = self._get_tool_health(tool_name)
        if health.circuit_open:
            health.circuit_open = False
            health.consecutive_failures = 0
            logger.info(f"Circuit manually reset for tool '{tool_name}'")
            return True
        return False
    
    def reset_all_circuits(self) -> int:
        """Reset all circuit breakers."""
        count = 0
        for health in self._tool_health.values():
            if health.circuit_open:
                health.circuit_open = False
                health.consecutive_failures = 0
                count += 1
        logger.info(f"Reset {count} circuit breakers")
        return count
