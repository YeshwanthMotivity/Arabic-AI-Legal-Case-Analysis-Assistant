"""
Router Layer Map
Decouples intent-based routing to dedicated handler methods.
"""
from typing import Callable, Dict, Any

class ChatRouter:
    def __init__(self, engine_instance: Any):
        self.engine = engine_instance
        # Map intents to the corresponding handler methods on the ChatEngine
        self.routes: Dict[str, Callable] = {
            "case_summary": self.engine._handle_case_summary,
            "case_type": self.engine._handle_case_type,
            "similar_cases": self.engine._handle_similar_cases,
            "legal_principles": self.engine._handle_legal_principles,
            "trends": self.engine._handle_trends,
            "recommendation": self.engine._handle_recommendation,
            "full_analysis": self.engine._handle_full_analysis,
            "draft": getattr(self.engine, "_handle_draft_request", self.engine._handle_general_inquiry),
            "draft_claim": getattr(self.engine, "_handle_draft_claim", self.engine._handle_general_inquiry),
            "draft_defense": getattr(self.engine, "_handle_draft_defense", self.engine._handle_general_inquiry),
            "draft_enforcement": getattr(self.engine, "_handle_draft_enforcement", self.engine._handle_general_inquiry),
            "draft_appeal": getattr(self.engine, "_handle_draft_appeal", self.engine._handle_general_inquiry),
            "outcome": getattr(self.engine, "_handle_outcome", self.engine._handle_general_inquiry),
            "compensation": getattr(self.engine, "_handle_compensation", self.engine._handle_general_inquiry),
            "entities": getattr(self.engine, "_handle_entities", self.engine._handle_general_inquiry),
            "bench_memo": getattr(self.engine, "_handle_bench_memo", self.engine._handle_general_inquiry),
        }

    def get_handler(self, intent: str) -> Callable:
        return self.routes.get(intent, self.engine._handle_general_inquiry)
