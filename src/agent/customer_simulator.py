"""
Customer Simulator: role-plays as a customer persona during simulated calls.
"""

from src.llm_client import chat
from src.agent.prompts import get_customer_system_prompt


class CustomerSimulator:
    def __init__(self, persona: dict):
        self.persona = persona
        self.system_prompt = get_customer_system_prompt(persona)
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def respond(self, agent_message: str) -> str:
        """Respond to what the sales agent just said."""
        self.messages.append({"role": "user", "content": agent_message})
        response = chat(self.messages, temperature=0.8)
        self.messages.append({"role": "assistant", "content": response})
        return response