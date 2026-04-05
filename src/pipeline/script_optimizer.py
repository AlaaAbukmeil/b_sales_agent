"""
Script Optimizer: takes evaluation data from a batch of calls
and generates an improved script version.
"""

import json
import yaml
from src.llm_client import chat
from src.agent.prompts import get_optimization_prompt


class ScriptOptimizer:
    def optimize(self, current_script: dict, evaluations: list) -> dict:
        """Generate an improved script based on call evaluations."""
        metrics = self._compute_metrics(evaluations)
        failure_patterns = self._extract_failure_patterns(evaluations)

        prompt = get_optimization_prompt(
            current_script, metrics, evaluations, failure_patterns,
        )

        response = chat(
            messages=[
                {"role": "system", "content": "You are a sales script optimization expert. Return only valid YAML."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=3000,
        )

        new_script = self._parse_yaml(response, current_script)
        return new_script

    def _compute_metrics(self, evaluations: list) -> dict:
        total = len(evaluations)
        if total == 0:
            return {"total_calls": 0, "success_rate": 0, "partial_rate": 0}

        successes = sum(1 for e in evaluations if e.get("outcome") == "success")
        partials = sum(1 for e in evaluations if e.get("outcome") == "partial")
        return {
            "total_calls": total,
            "success_rate": round(successes / total * 100),
            "partial_rate": round(partials / total * 100),
        }

    def _extract_failure_patterns(self, evaluations: list) -> dict:
        patterns = {}
        for ev in evaluations:
            if ev.get("outcome") in ("failed", "partial"):
                for obj in ev.get("objections_raised", []):
                    obj_type = obj.get("type", "unknown")
                    if obj_type not in patterns:
                        patterns[obj_type] = {
                            "count": 0,
                            "times_effective": 0,
                            "suggestions": [],
                        }
                    patterns[obj_type]["count"] += 1
                    if obj.get("effective"):
                        patterns[obj_type]["times_effective"] += 1
                    if obj.get("suggestion"):
                        patterns[obj_type]["suggestions"].append(obj["suggestion"])
        return patterns

    def _parse_yaml(self, text: str, fallback_script: dict) -> dict:
        """Robustly extract YAML from LLM response."""
        yaml_text = text

        # Strip markdown fences if present
        if "```yaml" in text:
            yaml_text = text.split("```yaml")[1].split("```")[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                yaml_text = parts[1]

        try:
            parsed = yaml.safe_load(yaml_text.strip())
            if isinstance(parsed, dict) and "script" in parsed:
                return parsed
        except yaml.YAMLError:
            pass

        # Fallback: return bumped version of current script
        print("  [Warning: Could not parse optimized script YAML. Using previous script.]")
        fallback = dict(fallback_script)
        fallback["version"] = fallback_script.get("version", 1) + 1
        fallback["changes_from_previous"] = "Optimization parse failed — carried forward previous script"
        return fallback