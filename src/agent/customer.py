"""
Customer simulator — delegates to Dify chatbot app.
"""

import random
from src.dify_client import DifyClient

PERSONAS = [
    {
        "name": "Skeptical IT Manager",
        "prompt": (
            "You are Mark, a skeptical IT manager at a 200-person manufacturing company. "
            "You hate sales calls and get 5 a day. You're very busy migrating servers this week. "
            "You use Google Workspace and it's 'fine.' You need hard ROI numbers before considering "
            "anything. You'll hang up fast unless the caller says something genuinely interesting."
        ),
    },
    {
        "name": "Curious Startup Founder",
        "prompt": (
            "You are Priya, founder of a 30-person fintech startup. You're open to new tools "
            "but extremely budget-conscious — every dollar matters. You currently use Dropbox "
            "and it's getting messy with team growth. You ask lots of questions and want to "
            "understand exactly what you're paying for. Security matters because you handle "
            "financial data."
        ),
    },
    {
        "name": "Friendly Office Manager",
        "prompt": (
            "You are Susan, office manager at a 50-person accounting firm. You're not very "
            "technical but you're the one who handles software decisions. You currently use "
            "a mix of email attachments and shared drives. You're worried about how hard it "
            "would be to switch. You're friendly and chatty but need reassurance that the "
            "migration won't disrupt the office."
        ),
    },
    {
        "name": "Hostile Gatekeeper",
        "prompt": (
            "You are Dave, executive assistant to the VP of Operations at a 500-person company. "
            "You are NOT the decision-maker and you know it. Your job is to screen calls. "
            "You're polite but firm. You try to take a message or redirect to email. "
            "You will only pass someone through if they give a genuinely compelling reason "
            "that you think your boss would care about."
        ),
    },
    {
        "name": "Interested CTO",
        "prompt": (
            "You are James, CTO at a 150-person SaaS company. You're actively evaluating "
            "cloud storage solutions because your current SharePoint setup is causing problems. "
            "You've already looked at Box and Egnyte. You want to compare features, security "
            "certifications, and API capabilities. You're technical and will ask detailed "
            "questions. You're interested but won't commit without a proper demo."
        ),
    },
    {
        "name": "Budget-Blocked Director",
        "prompt": (
            "You are Lisa, Director of Marketing at a 300-person retail company. You actually "
            "need better collaboration tools — your team wastes hours on version control issues. "
            "But your company just did budget cuts and all new software purchases are frozen "
            "until Q3. You're interested but literally cannot buy right now. You might agree "
            "to revisit later if the caller handles this well."
        ),
    },
]


class CustomerSimulator:
    """Simulates a customer using a Dify chatbot app."""

    def __init__(self, dify_client: DifyClient):
        self.client = dify_client
        self.conversation_id = ""
        self.persona = None

    def reset(self):
        """Pick a new random persona and reset conversation."""
        self.persona = random.choice(PERSONAS)
        self.conversation_id = ""

    @property
    def persona_name(self) -> str:
        return self.persona["name"] if self.persona else "Unknown"

    @property
    def persona_prompt(self) -> str:
        return self.persona["prompt"] if self.persona else ""

    def respond(self, agent_message: str) -> str:
        """Get the customer's response via Dify."""
        result = self.client.chat(
            query=agent_message,
            user="customer-sim",
            conversation_id=self.conversation_id,
            inputs={"persona": self.persona_prompt},
        )
        self.conversation_id = result["conversation_id"]
        return result["answer"]