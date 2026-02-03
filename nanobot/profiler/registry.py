"""
Model Registry for GigaBot's Model Profiler.

Stores and retrieves model profiles, provides model recommendations
based on task requirements and role assignments.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.profiler.profile import (
    ModelProfile,
    ROLE_CAPABILITY_MAP,
    TASK_CAPABILITY_MAP,
)


# Storage format version
REGISTRY_VERSION = "1.0"


class ModelRegistry:
    """
    Stores and retrieves model profiles.
    Provides model recommendations based on task requirements.
    """
    
    DEFAULT_STORAGE_PATH = Path.home() / ".gigabot" / "profiles"
    PROFILES_FILE = "models.json"
    
    def __init__(self, storage_path: Path | str | None = None):
        """
        Initialize the model registry.
        
        Args:
            storage_path: Directory to store profile data.
        """
        if storage_path:
            self.storage_path = Path(storage_path).expanduser()
        else:
            self.storage_path = self.DEFAULT_STORAGE_PATH
        
        self._profiles: dict[str, ModelProfile] = {}
        self._ensure_storage()
        self._load_profiles()
    
    def _ensure_storage(self) -> None:
        """Ensure storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def _load_profiles(self) -> None:
        """Load profiles from storage."""
        profiles_file = self.storage_path / self.PROFILES_FILE
        
        if not profiles_file.exists():
            logger.debug("No existing profiles found")
            return
        
        try:
            with open(profiles_file, "r") as f:
                data = json.load(f)
            
            version = data.get("version", "1.0")
            profiles_data = data.get("profiles", {})
            
            for model_id, profile_data in profiles_data.items():
                try:
                    profile = ModelProfile.from_dict(profile_data)
                    self._profiles[model_id] = profile
                except Exception as e:
                    logger.warning(f"Failed to load profile for {model_id}: {e}")
            
            logger.info(f"Loaded {len(self._profiles)} model profiles")
            
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
    
    def _save_profiles(self) -> None:
        """Save all profiles to storage."""
        profiles_file = self.storage_path / self.PROFILES_FILE
        
        data = {
            "version": REGISTRY_VERSION,
            "last_updated": datetime.now().isoformat(),
            "profiles": {
                model_id: profile.to_dict()
                for model_id, profile in self._profiles.items()
            }
        }
        
        try:
            with open(profiles_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self._profiles)} profiles")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
    
    def get_profile(self, model_id: str) -> ModelProfile | None:
        """
        Get profile for a model.
        
        Args:
            model_id: The model identifier.
        
        Returns:
            ModelProfile if found, None otherwise.
        """
        return self._profiles.get(model_id)
    
    def save_profile(self, profile: ModelProfile) -> None:
        """
        Save or update a model profile.
        
        Args:
            profile: The profile to save.
        """
        self._profiles[profile.model_id] = profile
        self._save_profiles()
        logger.info(f"Saved profile for {profile.model_id}")
    
    def delete_profile(self, model_id: str) -> bool:
        """
        Delete a model profile.
        
        Args:
            model_id: The model to delete.
        
        Returns:
            True if deleted, False if not found.
        """
        if model_id in self._profiles:
            del self._profiles[model_id]
            self._save_profiles()
            logger.info(f"Deleted profile for {model_id}")
            return True
        return False
    
    def list_profiles(self) -> list[str]:
        """Get list of all profiled model IDs."""
        return list(self._profiles.keys())
    
    def get_all_profiles(self) -> dict[str, ModelProfile]:
        """Get all profiles."""
        return self._profiles.copy()
    
    def get_best_model_for_task(
        self,
        task_type: str,
        available_models: list[str] | None = None,
        min_score: float = 0.6,
    ) -> str | None:
        """
        Find the best model for a task from available options.
        
        Args:
            task_type: Type of task (e.g., "code", "research").
            available_models: Models to consider (None = all profiled).
            min_score: Minimum suitability score required.
        
        Returns:
            Best model ID or None if no suitable model found.
        """
        candidates = available_models or list(self._profiles.keys())
        
        best_model = None
        best_score = min_score
        
        for model_id in candidates:
            profile = self._profiles.get(model_id)
            if not profile:
                continue
            
            suitable, score, _ = profile.is_suitable_for_task(task_type)
            if suitable and score > best_score:
                best_score = score
                best_model = model_id
        
        return best_model
    
    def get_models_by_capability(
        self,
        capability: str,
        min_score: float = 0.7,
    ) -> list[tuple[str, float]]:
        """
        Get models sorted by a specific capability score.
        
        Args:
            capability: Capability name (e.g., "tool_calling_accuracy").
            min_score: Minimum score to include.
        
        Returns:
            List of (model_id, score) tuples, sorted descending.
        """
        results = []
        
        for model_id, profile in self._profiles.items():
            score = profile.capabilities.get_score(capability)
            if score >= min_score:
                results.append((model_id, score))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def get_role_recommendations(
        self,
        role_id: str,
        available_models: list[str] | None = None,
        top_n: int = 5,
    ) -> list[tuple[str, float, str]]:
        """
        Get model recommendations for a role.
        
        Args:
            role_id: The role to recommend for (e.g., "architect").
            available_models: Models to consider (None = all).
            top_n: Number of top recommendations.
        
        Returns:
            List of (model_id, suitability_score, reasoning) tuples.
        """
        candidates = available_models or list(self._profiles.keys())
        recommendations = []
        
        for model_id in candidates:
            profile = self._profiles.get(model_id)
            if not profile:
                continue
            
            score, reasoning = profile.get_role_suitability(role_id)
            recommendations.append((model_id, score, reasoning))
        
        # Sort by score descending
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        return recommendations[:top_n]
    
    def needs_reinterview(
        self,
        model_id: str,
        max_age_days: int = 30,
    ) -> bool:
        """
        Check if a model profile is stale and needs re-evaluation.
        
        Args:
            model_id: The model to check.
            max_age_days: Maximum age before reinterview needed.
        
        Returns:
            True if reinterview needed.
        """
        profile = self._profiles.get(model_id)
        
        if not profile:
            return True  # Not interviewed yet
        
        age = datetime.now() - profile.interviewed_at
        return age > timedelta(days=max_age_days)
    
    def get_stale_profiles(self, max_age_days: int = 30) -> list[str]:
        """
        Get list of models that need reinterview.
        
        Args:
            max_age_days: Maximum profile age.
        
        Returns:
            List of model IDs needing reinterview.
        """
        stale = []
        cutoff = datetime.now() - timedelta(days=max_age_days)
        
        for model_id, profile in self._profiles.items():
            if profile.interviewed_at < cutoff:
                stale.append(model_id)
        
        return stale
    
    def update_runtime_stats(
        self,
        model_id: str,
        success: bool,
        tool_success: bool | None = None,
        tokens: int = 0,
        latency_ms: float = 0.0,
        error_type: str | None = None,
    ) -> None:
        """
        Update runtime statistics for a model.
        
        Args:
            model_id: The model that was called.
            success: Whether the call succeeded.
            tool_success: Whether tool calls succeeded (if applicable).
            tokens: Tokens used in the call.
            latency_ms: Response latency.
            error_type: Type of error if failed.
        """
        profile = self._profiles.get(model_id)
        if not profile:
            return
        
        profile.runtime_stats.record_call(
            success=success,
            tool_success=tool_success,
            tokens=tokens,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        
        # Periodically save (every 100 calls)
        if profile.runtime_stats.total_calls % 100 == 0:
            self._save_profiles()
    
    def compare_models(
        self,
        model_ids: list[str],
    ) -> dict[str, Any]:
        """
        Compare multiple models across capabilities.
        
        Args:
            model_ids: Models to compare.
        
        Returns:
            Comparison data structure.
        """
        comparison = {
            "models": model_ids,
            "capabilities": {},
            "overall_scores": {},
            "strengths": {},
            "weaknesses": {},
        }
        
        capability_names = [
            "tool_calling_accuracy",
            "instruction_following",
            "context_utilization",
            "code_generation",
            "reasoning_depth",
            "hallucination_resistance",
            "structured_output",
            "long_context_handling",
        ]
        
        for cap in capability_names:
            comparison["capabilities"][cap] = {}
        
        for model_id in model_ids:
            profile = self._profiles.get(model_id)
            if not profile:
                continue
            
            comparison["overall_scores"][model_id] = profile.get_overall_score()
            comparison["strengths"][model_id] = profile.strengths
            comparison["weaknesses"][model_id] = profile.weaknesses
            
            for cap in capability_names:
                comparison["capabilities"][cap][model_id] = profile.capabilities.get_score(cap)
        
        return comparison
    
    def format_comparison(self, model_ids: list[str]) -> str:
        """
        Format a human-readable comparison of models.
        
        Args:
            model_ids: Models to compare.
        
        Returns:
            Formatted comparison string.
        """
        comparison = self.compare_models(model_ids)
        
        lines = ["Model Comparison", "=" * 60, ""]
        
        # Overall scores
        lines.append("Overall Scores:")
        for model_id in model_ids:
            score = comparison["overall_scores"].get(model_id, 0.0)
            lines.append(f"  {model_id}: {score:.2f}")
        lines.append("")
        
        # Capability comparison
        lines.append("Capabilities:")
        lines.append("-" * 60)
        
        cap_names = {
            "tool_calling_accuracy": "Tool Calling",
            "instruction_following": "Instructions",
            "context_utilization": "Context",
            "code_generation": "Code Gen",
            "reasoning_depth": "Reasoning",
            "hallucination_resistance": "Anti-Halluc.",
            "structured_output": "Structured",
            "long_context_handling": "Long Context",
        }
        
        for cap, display_name in cap_names.items():
            scores = comparison["capabilities"].get(cap, {})
            score_strs = [f"{scores.get(m, 0.0):.2f}" for m in model_ids]
            lines.append(f"  {display_name:15} | " + " | ".join(score_strs))
        
        lines.append("")
        
        # Strengths/Weaknesses
        for model_id in model_ids:
            lines.append(f"\n{model_id}:")
            strengths = comparison["strengths"].get(model_id, [])
            weaknesses = comparison["weaknesses"].get(model_id, [])
            
            if strengths:
                lines.append(f"  Strengths: {', '.join(strengths[:3])}")
            if weaknesses:
                lines.append(f"  Weaknesses: {', '.join(weaknesses[:3])}")
        
        return "\n".join(lines)
    
    def get_model_for_role_with_fallback(
        self,
        role_id: str,
        preferred_model: str,
        fallback_models: list[str],
        min_score: float = 0.5,
    ) -> tuple[str, str]:
        """
        Get the best model for a role with fallback options.
        
        Args:
            role_id: The role to assign.
            preferred_model: First choice model.
            fallback_models: Backup options.
            min_score: Minimum acceptable score.
        
        Returns:
            Tuple of (selected_model, reason).
        """
        # Check preferred model
        profile = self._profiles.get(preferred_model)
        if profile:
            score, reason = profile.get_role_suitability(role_id)
            if score >= min_score:
                return preferred_model, f"Preferred model suitable ({score:.2f})"
        
        # Check fallbacks
        for model_id in fallback_models:
            profile = self._profiles.get(model_id)
            if not profile:
                continue
            
            score, reason = profile.get_role_suitability(role_id)
            if score >= min_score:
                return model_id, f"Fallback selected: {reason}"
        
        # Return preferred even if not profiled
        return preferred_model, "No profile data - using preferred model"
