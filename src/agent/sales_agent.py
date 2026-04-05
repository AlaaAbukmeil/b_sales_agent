"""
Sales Agent: conducts the sales call using the active script.
"""

from src.llm_client import chat
from src.agent.prompts import get_sales_agent_system_prompt


class SalesAgent:
    def __init__(self, script: dict, product_config: dict):
        self.script = script
        self.product = product_config
        self.system_prompt = get_sales_agent_system_prompt(script, product_config)
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def get_opening(self, customer_name: str, company: str) -> str:
        """Generate the opening line of the call."""
        user_msg = (
            f"You are calling {customer_name} at {company}. "
            f"They just picked up the phone and said 'Hello?'. "
            f"Deliver your opening."
        )
        self.messages.append({"role": "user", "content": user_msg})
        response = chat(self.messages, temperature=0.8)
        self.messages.append({"role": "assistant", "content": response})
        return response

    def respond(self, customer_message: str) -> str:
        """Respond to what the customer just said."""
        self.messages.append({"role": "user", "content": customer_message})
        response = chat(self.messages, temperature=0.7)
        self.messages.append({"role": "assistant", "content": response})
        return response