import json
from src.dify_client import DifyClient


class ScriptRefiner:
    """Uses Dify workflow to refine the sales script."""

    def __init__(self, dify_client: DifyClient):
        self.client = dify_client

    def refine(self, current_script: str, transcripts: list, metrics: dict) -> str:
        """Send call data to Dify and get an improved script back."""
        result = self.client.completion(
            inputs={
                "current_script": current_script,
                "transcripts": json.dumps(transcripts, indent=2),
                "metrics": json.dumps(metrics, indent=2),
            },
            user="refiner",
        )
        return result