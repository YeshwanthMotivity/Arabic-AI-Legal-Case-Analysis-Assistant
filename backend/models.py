from pydantic import BaseModel
from typing import List, Optional, Dict, Any


# ── Existing Models ────────────────────────────────────────────────────

class Case(BaseModel):
    case_id: str
    court: str
    facts: str
    legal_reasoning: str
    judgment: str
    source: str
    language: str
    is_real: bool

class SimilarityRequest(BaseModel):
    text: str
    top_k: int = 3
    include_augmented: bool = False

class SimilarCaseResult(BaseModel):
    case_id: str
    similarity_score: float
    preview: str

class SummarizeRequest(BaseModel):
    text: str

class SummarizeResponse(BaseModel):
    summary: str
    facts_summary: Optional[str] = None
    reasoning_summary: Optional[str] = None
    verdict_summary: Optional[str] = None
    confidence: float = 0.0


# ── New Intelligence Layer Models ──────────────────────────────────────

class AnalyzeRequest(BaseModel):
    text: str
    top_k: int = 5  # Number of similar cases to analyze for trends

class SubType(BaseModel):
    case_type: str
    name_ar: str
    name_en: str
    relevance: float

class CaseClassification(BaseModel):
    case_type: str
    name_ar: str
    name_en: str
    confidence: float
    matched_keywords: List[str]
    sub_types: List[SubType] = []

class LegalPrinciple(BaseModel):
    id: str
    name_ar: str
    name_en: str
    description_ar: str
    source_section: str
    evidence: str
    relevance: float
    match_count: int
    url: Optional[str] = None

class TrendStats(BaseModel):
    outcomes: Dict[str, int]
    plaintiff_win_rate: float
    average_compensation: float
    median_compensation: float
    compensation_range: Dict[str, float]
    compensation_count: int
    sample_size: int
    decided_cases: int
    reliability: str

class SupportingPrinciple(BaseModel):
    name_ar: str
    name_en: str
    relevance: float

class Recommendation(BaseModel):
    recommendation_ar: str
    recommendation_en: str
    direction: str
    confidence: float
    disclaimer_ar: str
    disclaimer_en: str
    supporting_principles: List[SupportingPrinciple] = []
    based_on_sample_size: int
    reliability: str

class RelatedCase(BaseModel):
    case: Case
    similarity_score: float
    preview: str

class AnalyzeResponse(BaseModel):
    classification: CaseClassification
    legal_principles: List[LegalPrinciple]
    trends: Optional[TrendStats] = None
    recommendation: Optional[Recommendation] = None
    entities: Optional[Dict[str, Any]] = None
    text: Optional[str] = None  # Added to return original text
    related_cases: List[RelatedCase] = []
    case_strength: Optional[str] = None
    appeal_risk: Optional[str] = None
    contradictions: List[str] = []

class DraftRequest(BaseModel):
    case_type: str
    classification_confidence: float = 0.0
    legal_principles: List[LegalPrinciple] = []
    recommendation: Recommendation
    party_role: str = "plaintiff"  # 'plaintiff' or 'defendant'
    entities: Optional[Dict[str, Any]] = None

class DraftResponse(BaseModel):
    title: str
    content: str
    type: str
    metadata: Dict[str, Any]

class QueryRequest(BaseModel):
    query_type: str  # 'outcome', 'principles', 'similar_cases', 'compensation', 'confidence'
    analysis_data: AnalyzeResponse

class QueryResponse(BaseModel):
    answer: str
    type: str  # 'text', 'list', 'stats'
    source: str # 'recommendation_engine', 'trend_analyzer', etc.
    data: Optional[Dict[str, Any]] = None


# ── Chat Models (NEW - Chatbot Interface) ──────────────────────────────

class SuggestedAction(BaseModel):
    label: str
    action: str

class ChatMessage(BaseModel):
    timestamp: str
    role: str  # "user" or "assistant"
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    message: str
    analysis_data: Optional[AnalyzeResponse] = None
    case_text: Optional[str] = None
    conversation_history: Optional[List[ChatMessage]] = None
    language: Optional[str] = "ar"

class ChatResponse(BaseModel):
    text: str
    intent: str
    suggested_actions: List[SuggestedAction] = []
    timestamp: str
    user_translation: Optional[str] = None
    assistant_translation: Optional[str] = None
    citations: List[Dict[str, Any]] = []
    metadata: Optional[Dict[str, Any]] = None
    analysis_data: Optional[AnalyzeResponse] = None
    error: Optional[str] = None

class ClearChatRequest(BaseModel):
    confirm: bool = True

class ConversationSummary(BaseModel):
    has_analysis: bool
    message_count: int
    analysis_keys: List[str] = []

class ArchiveRequest(BaseModel):
    conversation_id: str
    title: str
    preview: Optional[str] = None
    timestamp: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None

class SaveConversationRequest(BaseModel):
    id: str
    title: str
    preview: str
    messages: List[Dict[str, Any]]
    analysis: Optional[Dict[str, Any]] = None

