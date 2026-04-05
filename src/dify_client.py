"""
Dify API client — handles chat messages and workflow runs.
"""

import requests
import time
from typing import Optional


class DifyClient:
    """Wrapper for Dify API calls."""

    def __init__(self, base_url: str, api_key: str, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, payload: dict, timeout: int = 60) -> dict:
        """Make an API request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=timeout,
                )
                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.HTTPError as e:
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    print(f"  ⏳ Rate limited. Waiting {wait}s (attempt {attempt}/{self.max_retries})")
                    time.sleep(wait)
                    continue
                raise
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    print(f"  ⏳ Timeout. Retrying (attempt {attempt}/{self.max_retries})")
                    time.sleep(2)
                    continue
                raise

        raise Exception(f"Failed after {self.max_retries} retries")

    def chat(
        self,
        query: str,
        user: str = "sim-user",
        conversation_id: str = "",
        inputs: Optional[dict] = None,
    ) -> dict:
        """Send a chat message to a Dify chatbot app."""
        payload = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "blocking",
            "conversation_id": conversation_id,
            "user": user,
        }
        data = self._request("POST", "/chat-messages", payload, timeout=60)
        return {
            "answer": data.get("answer", ""),
            "conversation_id": data.get("conversation_id", ""),
        }

    def run_workflow(self, inputs: dict, user: str = "sim-user") -> str:
        """Trigger a Dify workflow and return the final output text."""
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": user,
        }
        data = self._request("POST", "/workflows/run", payload, timeout=180)

        # Extract output from workflow response
        outputs = data.get("data", {}).get("outputs", {})

        # Try common output key names
        for key in ["text", "result", "output", "script"]:
            if key in outputs:
                return outputs[key]

        # Fallback: return first string value found
        for value in outputs.values():
            if isinstance(value, str):
                return value

        return str(outputs)