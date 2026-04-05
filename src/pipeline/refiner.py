import json
from src.dify_client import DifyClient


class ScriptRefiner:
    """Uses Dify workflow to refine the sales script."""

    def __init__(self, dify_client: DifyClient):
        self.client = dify_client

    def _summarize_transcripts(self, transcripts: list, max_chars: int = 6000) -> str:
        """
        Trim transcripts to stay within token limits.
        Keeps the most recent / relevant exchanges.
        """
        full_text = json.dumps(transcripts, indent=2)

        if len(full_text) <= max_chars:
            return full_text

        trimmed = []
        total = 0
        for t in reversed(transcripts):
            t_str = json.dumps(t, indent=2)
            if total + len(t_str) > max_chars:
                break
            trimmed.insert(0, t)
            total += len(t_str)

        if not trimmed:
            return json.dumps(transcripts[-1], indent=2)[:max_chars]

        return json.dumps(trimmed, indent=2)

    def refine(self, current_script: str, transcripts: list, metrics: dict) -> str:
        """Send call data to Dify workflow and get an improved script back."""

        inputs = {
            "current_script": current_script,
            "transcripts": self._summarize_transcripts(transcripts),
            "metrics": json.dumps(metrics, indent=2),
        }

        result = self.client.run_workflow(inputs=inputs)

        if isinstance(result, dict):
            text = result.get("text", "")
            if text:
                return text

            for key in ("improved_script", "refined_script", "output", "result"):
                if result.get(key):
                    print(f"  📝 Using workflow output key: '{key}'")
                    return result[key]

            for key, value in result.items():
                if value and isinstance(value, str):
                    print(f"  📝 Using workflow output key: '{key}'")
                    return value

        if isinstance(result, str) and result:
            return result

        raise ValueError(f"Unexpected workflow output: {result}")