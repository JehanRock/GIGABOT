"""
Model Profiler system for GigaBot.

Evaluates AI models through standardized tests to create capability profiles
that inform role assignment, task routing, and guardrail strategies.

The profiler acts like an HR department - interviewing models to understand
their strengths, weaknesses, and optimal use cases.
"""

from nanobot.profiler.profile import (
    ModelProfile,
    CapabilityScores,
    GuardrailRecommendations,
    RuntimeStats,
    PROFILE_VERSION,
    ROLE_CAPABILITY_MAP,
    TASK_CAPABILITY_MAP,
)
from nanobot.profiler.tests import (
    TestCase,
    TestResult,
    TestSuite,
    TestCategory,
    ValidationType,
)
from nanobot.profiler.interviewer import ModelInterviewer
from nanobot.profiler.registry import ModelRegistry

__all__ = [
    # Profile
    "ModelProfile",
    "CapabilityScores",
    "GuardrailRecommendations",
    "RuntimeStats",
    "PROFILE_VERSION",
    "ROLE_CAPABILITY_MAP",
    "TASK_CAPABILITY_MAP",
    # Tests
    "TestCase",
    "TestResult",
    "TestSuite",
    "TestCategory",
    "ValidationType",
    # Interviewer
    "ModelInterviewer",
    # Registry
    "ModelRegistry",
]
