"""
Conversation Runner: orchestrates a full simulated sales call
between the Sales Agent and Customer Simulator.
"""

from src.agent.sales_agent import SalesAgent
from src.agent.customer_simulator import CustomerSimulator


class ConversationRunner:
    CALL_END_MARKER = "[CALL_ENDED]"

    def __init__(self, sales_agent: SalesAgent, customer: CustomerSimulator, max_turns: int = 14):
        self.agent = sales_agent
        self.customer = customer
        self.max_turns = max_turns
        self.transcript = []

    def run(self) -> list:
        """
        Run the full conversation. Returns a list of transcript entries:
        [{"role": "agent"|"customer", "content": "..."}, ...]
        """
        # Agent opens the call
        opening = self.agent.get_opening(
            self.customer.persona["name"],
            self.customer.persona["company"],
        )
        self.transcript.append({"role": "agent", "content": opening})

        # Customer responds to opening
        customer_reply = self.customer.respond(opening)
        self.transcript.append({"role": "customer", "content": customer_reply})

        if self._call_ended(customer_reply):
            return self._clean_transcript()

        # Alternate turns
        for _ in range(self.max_turns - 1):
            # Agent responds
            agent_reply = self.agent.respond(self._strip_marker(customer_reply))
            self.transcript.append({"role": "agent", "content": agent_reply})

            # Check if agent ended the call
            if self._call_ended(agent_reply):
                break

            # Customer responds
            customer_reply = self.customer.respond(agent_reply)
            self.transcript.append({"role": "customer", "content": customer_reply})

            if self._call_ended(customer_reply):
                break

        return self._clean_transcript()

    def _call_ended(self, message: str) -> bool:
        return self.CALL_END_MARKER in message

    def _strip_marker(self, message: str) -> str:
        return message.replace(self.CALL_END_MARKER, "").strip()

    def _clean_transcript(self) -> list:
        """Remove [CALL_ENDED] markers from transcript for clean output."""
        cleaned = []
        for entry in self.transcript:
            cleaned.append({
                "role": entry["role"],
                "content": self._strip_marker(entry["content"]),
            })
        return cleaned