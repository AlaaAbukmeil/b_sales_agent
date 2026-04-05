"""
Outcome Evaluator: analyzes a completed call transcript
and produces a structured evaluation.
"""

import json
from src.llm_client import chat
from src.agent.prompts import get_evaluation_prompt


class OutcomeEvaluator:
    def evaluate(self, transcript: list, script_version: int) -> dict:
        """Evaluate a call transcript and return structured analysis."""
        transcript_text = self._format_transcript(transcript)
        prompt = get_evaluation_prompt(transcript_text, script_version)

        response = chat(
            messages=[
                {"role": "system", "content": "You are a sales performance analyst. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        return self._parse_json(response)

    def _format_transcript(self, transcript: list) -> str:
        lines = []
        for turn in transcript:
            label = "Sales Agent" if turn["role"] == "agent" else "Customer"
            lines.append(f"{label}: {turn['content']}")
        return "\n\n".join(lines)

    def _parse_json(self, text: str) -> dict:
        """Robustly extract JSON from LLM response."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try finding JSON object in text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        return {
            "outcome": "unknown",
            "outcome_detail": "Failed to parse evaluation",
            "customer_engagement_level": "unknown",
            "objections_raised": [],
            "failure_stage": None,
            "strengths": [],
            "weaknesses": [],
            "specific_improvements": [],
            "parse_error": True,
            "raw_response": text[:500],
        }