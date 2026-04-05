"""
Sales agent — delegates to Dify chatbot app.
"""

from src.dify_client import DifyClient


class SalesAgent:
    """Sales agent orchestrated through Dify."""

    def __init__(self, dify_client: DifyClient, current_script: str = ""):
        self.client = dify_client
        self.conversation_id = ""
        self.current_script = current_script

    def set_script(self, script: str):
        """Update the script for future calls."""
        self.current_script = script

    def reset(self):
        """Reset for a new call."""
        self.conversation_id = ""

    def open(self) -> str:
        """Generate the opening line of the call."""
        result = self.client.chat(
            query=(
                "[START CALL] The customer just picked up the phone. "
                "Deliver your opening — name, company, reason for calling, and a qualifying question."
            ),
            user="sales-agent",
            conversation_id="",
            inputs={"current_script": self.current_script},
        )
        self.conversation_id = result["conversation_id"]
        return result["answer"]

    def respond(self, customer_message: str) -> str:
        """Get the agent's next response."""
        result = self.client.chat(
            query=customer_message,
            user="sales-agent",
            conversation_id=self.conversation_id,
            inputs={"current_script": self.current_script},
        )
        self.conversation_id = result["conversation_id"]
        return result["answer"]