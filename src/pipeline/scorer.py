"""
Call scorer — evaluates call transcripts using rule-based heuristics.
No LLM needed. Fast and deterministic.
"""

import re
from typing import List, Dict


class CallScorer:
    """Scores simulated sales calls on multiple dimensions."""

    # Keywords / phrases that indicate positive signals
    BUYING_SIGNALS = [
        "tell me more", "how much", "what's the price", "pricing",
        "send me", "send info", "demo", "trial", "free trial",
        "sounds interesting", "sounds good", "that's interesting",
        "how does it work", "implementation", "onboarding",
        "how long does it take", "timeline", "integrate",
        "let's schedule", "let's set up", "next steps",
        "tuesday", "wednesday", "thursday", "friday", "monday",
        "my email", "here's my email", "calendar",
    ]

    NEGATIVE_SIGNALS = [
        "not interested", "no thanks", "no thank you",
        "don't call", "stop calling", "take me off",
        "hang up", "goodbye", "gotta go", "too busy",
        "waste of time", "not for us", "can't help you",
    ]

    DISCOVERY_QUESTIONS = [
        "?",  # any question from agent counts
    ]

    OBJECTION_PHRASES = [
        "too expensive", "no budget", "already have", "already use",
        "not the right time", "talk to my boss", "send me an email",
        "think about it", "not sure", "don't need", "competitor",
        "google drive", "dropbox", "sharepoint", "box",
        "budget cuts", "frozen", "can't buy",
    ]

    def score(self, transcript: List[Dict]) -> Dict:
        """
        Score a single call transcript.

        Returns a dict of scores (0-10) and boolean flags.
        """
        if not transcript:
            return self._empty_score()

        agent_messages = [t["message"] for t in transcript if t["role"] == "agent"]
        customer_messages = [t["message"] for t in transcript if t["role"] == "customer"]

        all_customer_text = " ".join(customer_messages).lower()
        all_agent_text = " ".join(agent_messages).lower()

        scores = {}

        # 1. Engagement Score (0-10)
        scores["engagement"] = self._score_engagement(
            agent_messages, customer_messages, all_customer_text
        )

        # 2. Objection Handling Score (0-10)
        scores["objection_handling"] = self._score_objection_handling(
            transcript, all_customer_text
        )

        # 3. Discovery Score (0-10)
        scores["discovery"] = self._score_discovery(agent_messages, customer_messages)

        # 4. Closing Score (0-10)
        scores["closing"] = self._score_closing(
            agent_messages, customer_messages, all_customer_text
        )

        # 5. Appointment / Next Step
        scores["got_appointment"] = self._detected_appointment(all_customer_text)

        # 6. Overall (weighted average)
        scores["overall"] = round(
            scores["engagement"] * 0.25
            + scores["objection_handling"] * 0.25
            + scores["discovery"] * 0.25
            + scores["closing"] * 0.25,
            2,
        )

        # 7. Metadata
        scores["total_turns"] = len(transcript)
        scores["agent_turns"] = len(agent_messages)
        scores["customer_turns"] = len(customer_messages)

        return scores

    def _score_engagement(
        self,
        agent_messages: List[str],
        customer_messages: List[str],
        all_customer_text: str,
    ) -> float:
        """How engaged was the customer?"""
        score = 5.0  # baseline

        # Longer customer responses = more engaged
        avg_cust_len = (
            sum(len(m.split()) for m in customer_messages) / max(len(customer_messages), 1)
        )
        if avg_cust_len > 30:
            score += 2.0
        elif avg_cust_len > 15:
            score += 1.0
        elif avg_cust_len < 5:
            score -= 2.0

        # Buying signals
        buy_signals = sum(
            1 for signal in self.BUYING_SIGNALS if signal in all_customer_text
        )
        score += min(buy_signals * 0.5, 3.0)

        # Negative signals
        neg_signals = sum(
            1 for signal in self.NEGATIVE_SIGNALS if signal in all_customer_text
        )
        score -= min(neg_signals * 1.0, 4.0)

        # Conversation length (longer = more engaged, up to a point)
        if len(customer_messages) >= 6:
            score += 1.0
        elif len(customer_messages) <= 2:
            score -= 2.0

        return round(max(0.0, min(10.0, score)), 2)

    def _score_objection_handling(
        self, transcript: List[Dict], all_customer_text: str
    ) -> float:
        """How well did the agent handle objections?"""
        # Find objections in customer messages
        objections_found = []
        for i, turn in enumerate(transcript):
            if turn["role"] == "customer":
                text = turn["message"].lower()
                for phrase in self.OBJECTION_PHRASES:
                    if phrase in text:
                        objections_found.append(i)
                        break

        if not objections_found:
            return 7.0  # no objections = neutral/good

        score = 5.0
        handled_well = 0

        for obj_idx in objections_found:
            # Check if agent responded (next message exists and is agent)
            if obj_idx + 1 < len(transcript) and transcript[obj_idx + 1]["role"] == "agent":
                agent_response = transcript[obj_idx + 1]["message"].lower()

                # Good signs in agent response
                if any(
                    w in agent_response
                    for w in ["understand", "appreciate", "great question", "fair point", "makes sense"]
                ):
                    handled_well += 1

                # Check if customer continued positively after
                if obj_idx + 2 < len(transcript):
                    next_cust = transcript[obj_idx + 2]["message"].lower()
                    if any(s in next_cust for s in self.BUYING_SIGNALS):
                        handled_well += 1
                    elif any(s in next_cust for s in self.NEGATIVE_SIGNALS):
                        handled_well -= 1

        ratio = handled_well / max(len(objections_found), 1)
        score += ratio * 4.0

        return round(max(0.0, min(10.0, score)), 2)

    def _score_discovery(
        self, agent_messages: List[str], customer_messages: List[str]
    ) -> float:
        """How well did the agent discover customer needs?"""
        score = 3.0

        # Count questions asked by agent
        questions = sum(1 for m in agent_messages if "?" in m)
        if questions >= 4:
            score += 3.0
        elif questions >= 2:
            score += 1.5
        elif questions == 0:
            score -= 2.0

        # Open-ended question quality
        good_question_words = ["how", "what", "tell me", "walk me through", "describe"]
        good_qs = sum(
            1
            for m in agent_messages
            if any(w in m.lower() for w in good_question_words) and "?" in m
        )
        score += min(good_qs * 0.75, 3.0)

        # Did agent reference customer's answers later? (basic check)
        # If agent messages get longer over time, they're probably building on info
        if len(agent_messages) >= 4:
            early_len = sum(len(m.split()) for m in agent_messages[:2]) / 2
            late_len = sum(len(m.split()) for m in agent_messages[-2:]) / 2
            if late_len > early_len:
                score += 1.0

        return round(max(0.0, min(10.0, score)), 2)

    def _score_closing(
        self,
        agent_messages: List[str],
        customer_messages: List[str],
        all_customer_text: str,
    ) -> float:
        """Did the agent attempt to close and was it successful?"""
        score = 3.0

        close_attempts = [
            "demo", "trial", "schedule", "set up", "calendar",
            "next step", "follow up", "send you", "tuesday",
            "wednesday", "thursday", "friday", "monday",
        ]

        # Check if agent attempted to close
        all_agent_text = " ".join(agent_messages).lower()
        attempts = sum(1 for phrase in close_attempts if phrase in all_agent_text)

        if attempts >= 2:
            score += 2.0
        elif attempts >= 1:
            score += 1.0

        # Did customer agree to a next step?
        if self._detected_appointment(all_customer_text):
            score += 5.0
        elif any(
            phrase in all_customer_text
            for phrase in ["send me info", "send info", "send me more", "email me"]
        ):
            score += 2.0

        return round(max(0.0, min(10.0, score)), 2)

    def _detected_appointment(self, all_customer_text: str) -> bool:
        """Did the customer agree to a demo, trial, or meeting?"""
        positive_outcomes = [
            "let's do", "let's schedule", "schedule a demo", "book a demo",
            "sign me up", "i'll try", "start a trial", "set up a trial",
            "sounds good, let's", "i'm in", "count me in",
            "send me the trial", "send the link", "send me the link",
            "yes, please", "yes please", "sure, let's", "absolutely",
        ]

        # Check exact phrases
        if any(phrase in all_customer_text for phrase in positive_outcomes):
            return True

        # Check if customer agreed to a specific day/time
        days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        agreement_words = ["works", "good", "great", "perfect", "fine", "ok", "sure"]
        for day in days:
            if day in all_customer_text:
                if any(w in all_customer_text for w in agreement_words):
                    return True

        # Check if customer gave their email (strong commitment signal)
        if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", all_customer_text):
            return True

        return False

    def _empty_score(self) -> Dict:
        return {
            "engagement": 0,
            "objection_handling": 0,
            "discovery": 0,
            "closing": 0,
            "overall": 0,
            "got_appointment": False,
            "total_turns": 0,
            "agent_turns": 0,
            "customer_turns": 0,
        }

    def aggregate(self, scores: List[Dict]) -> Dict:
        """Compute average metrics across multiple calls."""
        if not scores:
            return self._empty_score()

        n = len(scores)
        agg = {
            "engagement": sum(s["engagement"] for s in scores) / n,
            "objection_handling": sum(s["objection_handling"] for s in scores) / n,
            "discovery": sum(s["discovery"] for s in scores) / n,
            "closing": sum(s["closing"] for s in scores) / n,
            "overall": sum(s["overall"] for s in scores) / n,
            "appointment_rate": sum(1 for s in scores if s["got_appointment"]) / n,
            "avg_turns": sum(s["total_turns"] for s in scores) / n,
            "total_calls": n,
        }
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in agg.items()}