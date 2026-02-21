# -*- coding: utf-8 -*-
"""
Chat Engine: Manages conversational interactions with the legal analysis system.
Maintains context and routes user messages to appropriate analysis engines.
"""

import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import re
from data_availability_validator import DataAvailabilityValidator
from response_cache import response_cache
from router import ChatRouter

logger = logging.getLogger(__name__)

# Try to import deep-translator for user message translation
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False
    logger.warning("deep-translator not found. Install it for translation features: pip install deep-translator")

# Try to import LocalLLM
try:
    from llm_local import LocalLLM
    HAS_LLM = True
except ImportError:
    HAS_LLM = False
    logger.warning("LocalLLM module not found or failed to import.")

try:
    from research_engine import LegalResearchEngine
    HAS_RESEARCH = True
except ImportError:
    HAS_RESEARCH = False
    logger.warning("LegalResearchEngine module not found.")


class ConversationContext:
    """Manages conversation history and context."""
    
    def __init__(self, max_history: int = 20):
        self.messages: List[Dict[str, Any]] = []
        self.analysis_data: Optional[Dict] = None  # Stores current case analysis
        self.case_text: Optional[str] = None  # Stores current case text
        self.max_history = max_history
        
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to the conversation history."""
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,  # "user" or "assistant"
            "content": content,
            "metadata": metadata or {}
        }
        self.messages.append(message)
        
        # Keep only recent messages
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
    
    def set_analysis(self, analysis_data: Optional[Dict], case_text: Optional[str] = None):
        """Store or clear the current case analysis data."""
        self.analysis_data = analysis_data
        self.case_text = case_text
    
    def get_last_n_messages(self, n: int) -> List[Dict]:
        """Get last n messages for context."""
        return self.messages[-n:] if self.messages else []
    
    def clear(self):
        """Clear conversation history."""
        self.messages = []
        self.analysis_data = None
        self.case_text = None


class ChatEngine:
    """
    Handles conversational interactions with the legal analysis system.
    Routes user queries to appropriate analysis engines based on intent detection.
    """
    
    def __init__(self):
        self.context = ConversationContext()
        self.intent_keywords = self._initialize_intents()
        # Initialize Local LLM (lazy loading inside the class)
        self.llm = LocalLLM() if HAS_LLM else None
        # Initialize Legal Research Engine
        self.research_engine = LegalResearchEngine() if HAS_RESEARCH else None
        # Shared analyzer logic
        self.analyzer = None
        # Initialize Router
        self.router = ChatRouter(self)
        
    def set_analyzer(self, analyzer_func):
        """Inject the full analysis pipeline function."""
        self.analyzer = analyzer_func

    def _stats_flags(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Centralized statistical visibility rules to avoid low-sample hallucinations."""
        sample_size = int(trends.get("sample_size", 0) or 0)
        decided_cases = int(trends.get("decided_cases", 0) or 0)
        compensation_count = int(trends.get("compensation_count", 0) or 0)
        return {
            "sample_size": sample_size,
            "decided_cases": decided_cases,
            "compensation_count": compensation_count,
            "can_show_win_rate": sample_size >= 3 and decided_cases >= 3,
            "can_show_compensation": compensation_count >= 3,
            "can_show_trend_analysis": sample_size >= 5,
        }
    
    def _clean_draft(self, text: str, facts: Dict[str, Any]) -> str:
        """Substitute template placeholders with actual facts."""
        cleaned = text
        for key, value in facts.items():
            placeholder = "{" + key + "}"
            cleaned = cleaned.replace(placeholder, str(value))
        return cleaned
        
    def _initialize_intents(self) -> Dict[str, List[str]]:
        """Define intent detection keywords in Arabic and English."""
        return {
            "case_summary": ["ملخص", "summary", "ملخص القضية", "summarize", "اختصار", "case_summary", "show_details", "summary", "summaries"],
            "case_type": ["النوع", "type", "classification", "التصنيف", "نوع القضية"],
            "similar_cases": ["حالات مشابهة", "similar", "precedent", "similar cases", "قضايا شبيهة", "قضايا مشابهة", "مشابهة", "search_similar"],
            "legal_principles": ["المبادئ", "principles", "قواعد قانونية", "legal_principles"],
            "trends": ["الاتجاهات", "trends", "statistics", "إحصائيات", "معدلات"],
            "recommendation": ["توصية", "advice", "رأي", "اقتراح", "recommendations", "recommendation"],
            "full_analysis": ["تحليل", "analyze", "analysis", "تحليل شامل", "اشرح", "full_analysis"],
            "draft": ["مسودة", "draft", "نماذج"],
            "draft_claim": ["لائحة دعوى", "plaintiff claim", "صحيفة دعوى", "claim draft", "تقديم دعوى", "plaintiff_claim"],
            "draft_defense": ["مذكرة دفاع", "defense memo", "defense draft", "مذكرة جوابية", "رد على دعوى", "defense_memo"],
            "draft_appeal": ["draft_appeal", "appeal draft", "appeal memo", "memo appeal"],
            "draft_enforcement": ["draft_enforcement", "enforcement draft", "enforcement petition"],
            "outcome": ["النتيجة", "outcome", "result", "probability", "احتمالية"],
            "compensation": ["تعويض", "compensation", "damages", "amount", "مبلغ"],
            "entities": ["الأطراف", "parties", "entities", "من", "شخصيات"],
            "bench_memo": ["bench memo", "مذكرة القاضي", "قاضي", "مذكرة", "bench_memo"]
        }

    def _get_legal_context(self, query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Retrieve relevant legal articles for the query."""
        if not self.research_engine:
            return "", []
        
        results = self.research_engine.search(query, top_k=2)
        if not results:
            return "", []
            
        context_parts = []
        citations = []

        for res in results:
            article = res['article']
            score = res['score']
            if score > 50: # Only include relevant articles
                context_parts.append(f"Article {article['article_number']} ({article['source']}):\n{article['text_ar']}")
                citations.append({
                    "source": article['source'],
                    "article_number": article['article_number'],
                    "text": article['text_ar'],
                    "confidence": score
                })
        
        context_str = ""
        if context_parts:
            context_str = "المواد النظامية ذات الصلة:\n" + "\n---\n".join(context_parts)
            
        return context_str, citations
    
    def _format_case_citations(self, cases: List[Dict]) -> List[Dict[str, Any]]:
        """Format a list of case objects into standard citations."""
        citations = []
        if not cases:
            return []
            
        for case in cases[:3]: # Limit to top 3 for brevity
            citations.append({
                "source": case.get("case_id", "Precedent"),
                "text": case.get("facts", "")[:300] + "...",
                "article": f"المحكمة: {case.get('court', 'N/A')}",
                "metadata": {
                    "judgment": case.get("judgment", ""),
                    "reasoning": case.get("legal_reasoning", "")
                }
            })
        return citations

    def _is_likely_case(self, text: str) -> bool:
        """Detect if text is likely a legal case description."""
        if len(text) < 100:
            return False
            
        case_markers = [
            "الوقائع", "الأسباب", "منطوق الحكم", "حكمت المحكمة", 
            "المدعي", "المدعى عليه", "قضية رقم", "بناءً على",
            "facts", "reasoning", "judgment", "ruling", "plaintiff", "defendant", "case no", "based on"
        ]
        
        # Count how many markers are present
        matches = sum(1 for marker in case_markers if marker.lower() in text.lower())
        
        # If it's long and has legal terms, it's likely a case description
        return matches >= 2 or (len(text) > 400 and matches >= 1)

    def detect_intent(self, query: str) -> str:
        """Detect user's intent from their message with priority for specific actions."""
        query_lower = query.lower().strip()

        # Direct action commands from UI
        if query_lower in {"draft_claim", "draft_defense", "draft_appeal", "draft_enforcement"}:
            return query_lower

        # Normalize common short command variants to avoid falling into slow general inquiry flow.
        if query_lower in {"summarise", "summarize", "summary", "case_summary"}:
            return "case_summary"
        if query_lower in {"draft claim", "claim draft", "plaintiff claim"}:
            return "draft_claim"
        if query_lower in {"draft defense", "draft defence", "defense memo", "defence memo"}:
            return "draft_defense"
        if query_lower in {"draft appeal", "appeal memo", "appeal draft"}:
            return "draft_appeal"
        if query_lower in {"draft enforcement", "enforcement petition", "enforcement draft"}:
            return "draft_enforcement"
        if query_lower in {"bench_memo", "bench memo"}:
            return "bench_memo"
        
        # 1. Check for EXACT action matches first (highest priority)
        for intent in self.intent_keywords.keys():
            if query_lower == intent:
                return intent
        
        # 2. Score each intent based on keyword presence
        intent_scores = {}
        for intent, keywords in self.intent_keywords.items():
            score = 0
            for kw in keywords:
                if any(char.isalpha() for char in kw):
                    if re.search(rf"\b{re.escape(kw)}\b", query_lower):
                        score += 5 
                else:
                    if kw in query_lower:
                        score += 1
            
            if score > 0:
                intent_scores[intent] = score
        
        # 3. Custom logic: If text is long and looks like a case, default to case_summary
        if self._is_likely_case(query):
            return "case_summary"

        if intent_scores:
            return max(intent_scores, key=intent_scores.get)
        return "general_inquiry"
    
    def _detect_language(self, text: str) -> str:
        """Detect if the input text is primarily Arabic or English."""
        if not text:
            return "ar"
        arabic_chars = len([c for c in text if '\u0600' <= c <= '\u06FF'])
        english_chars = len([c for c in text if 'a' <= c.lower() <= 'z'])
        return "ar" if arabic_chars >= english_chars else "en"

    async def process_message(
        self,
        user_message: str,
        analysis_data: Optional[Dict] = None,
        case_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a user message and generate an appropriate response."""
        try:
                # Sync analysis data from frontend ONLY if provided (not None)
            if analysis_data is not None:
                 self.context.set_analysis(analysis_data, case_text)
            
            source_language = self._detect_language(user_message)
            processed_user_message = user_message
            user_translation = None

            # Keep core chat processing Arabic-first for intent handling and LLM context.
            if HAS_TRANSLATOR:
                try:
                    text_to_translate = user_message[:2000]
                    if source_language == "en":
                        arabic_text = GoogleTranslator(source='auto', target='ar').translate(text_to_translate)
                        if arabic_text:
                            processed_user_message = arabic_text
                            # Used by UI to render Arabic when Arabic mode is selected.
                            user_translation = arabic_text
                    elif source_language == "ar":
                        english_text = GoogleTranslator(source='auto', target='en').translate(text_to_translate)
                        if english_text:
                            # Used by UI to render English when English mode is selected.
                            user_translation = english_text
                except Exception as e:
                    logger.warning(f"User message translation failed: {e}")

            self.context.add_message("user", processed_user_message)
            intent = self.detect_intent(processed_user_message)
            
            # Detect if this is a NEW case description requiring re-analysis
            is_new_case_input = False
            # Fix: Only treat as new case if text is sufficiently long (> 50 chars)
            # This prevents short commands like "case_summary" from being analyzed as a case
            if intent == "case_summary" and self.analyzer and len(processed_user_message) > 50:
                if not self.context.analysis_data:
                    is_new_case_input = True
                elif len(processed_user_message) > 400:
                    # Check if text is significantly different from current context
                    current_text = self.context.case_text or ""
                    if processed_user_message[:100].lower() != current_text[:100].lower():
                        is_new_case_input = True

            # Caching Layer (Skip LLM if already processed)
            analysis_hash = hash(str(self.context.analysis_data)) if self.context.analysis_data else 0
            cache_key = f"{intent}:{hash(processed_user_message)}:{analysis_hash}"
            if not is_new_case_input:
                cached_response = response_cache.get(cache_key)
                if cached_response:
                    logger.info(f"Serving response for intent '{intent}' from cache")
                    self.context.add_message("assistant", cached_response["text"], metadata={"intent": intent})
                    return cached_response

            if is_new_case_input:
                try:
                    logger.info("New case input detected. Triggering re-analysis...")
                    analysis_result = await self.analyzer(processed_user_message)
                    analysis_dict = analysis_result.dict()
                    self.context.set_analysis(analysis_dict, processed_user_message)
                except Exception as e:
                    logger.error(f"Auto-analysis failed: {e}")

            response = await self._generate_response(processed_user_message, intent)
            
            # Include the current analysis in the response so the frontend stays synced
            response["analysis_data"] = self.context.analysis_data
            
            assistant_text = response.get("text", "")
            if HAS_TRANSLATOR and assistant_text and any('\u0600' <= char <= '\u06FF' for char in assistant_text):
                try:
                    # Always provide English translation for Arabic assistant replies
                    # so frontend EN mode can consistently render English content.
                    translated_text = GoogleTranslator(source='auto', target='en').translate(assistant_text[:4500])
                    if translated_text and translated_text.lower() != assistant_text.lower():
                        response["assistant_translation"] = translated_text
                except Exception as e:
                    logger.warning(f"Assistant translation failed: {e}")

            self.context.add_message("assistant", response["text"], metadata={"intent": intent})
            
            if user_translation:
                response["user_translation"] = user_translation

            if "text" in response:
                current_analysis = self.context.analysis_data or analysis_data or {}
                amount = current_analysis.get("recommendation", {}).get("award_amount") or "[قيد التقدير]"
                facts = {"amount": amount, "المبلغ": amount}
                response["text"] = self._clean_draft(response["text"], facts)

            if not is_new_case_input:
                response_cache.set(cache_key, response)

            # --- PHASE 3: Feature Injection (Clickable Laws) ---
            if "text" in response:
                response["text"] = self._link_law_citations(response["text"])

            return response
            
        except Exception as e:
            logger.error(f"Chat processing error: {e}", exc_info=True)
            return {
                "text": "عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة مجدداً.\nSorry, an error occurred. Please try again.",
                "intent": "error",
                "suggested_actions": [],
                "error": str(e)
            }
    
    async def _generate_response(self, user_message: str, intent: str) -> Dict[str, Any]:
        """Generate response based on detected intent."""
        analysis = self.context.analysis_data
        
        handler = self.router.get_handler(intent)
        
        if intent != "general_inquiry" and intent in self.router.routes and not analysis:
            return await self._handle_no_analysis(user_message)
        
        if analysis or intent == "general_inquiry":
            return await handler(user_message, analysis)
        
        return await self._handle_general_inquiry(user_message, {})
    
    async def _handle_no_analysis(self, user_message: str) -> Dict[str, Any]:
        """Handle case when no analysis has been performed yet."""
        return {
            "text": """مرحباً! أنا مساعدك القانوني الذكي المتخصص في تحليل القضايا السعودية.

لتحليل قضيتك، يمكنك:
1. رفع مستند - PDF, DOCX, أو ملف نصي
2. لصق نص القضية - مباشرة في مربع المدخل

كيف أستطيع مساعدتك اليوم؟

---

Hello! I'm your AI Legal Assistant specializing in Saudi legal case analysis.

To analyze your case, you can:
1. Upload a document - PDF, DOCX, or text file
2. Paste case text - directly in the input field

How can I help you today?""",
            "intent": "greeting",
            "suggested_actions": [
                {"label": "Upload Document | رفع مستند", "action": "upload"},
                {"label": "Paste Text | لصق نص", "action": "paste_text"},
                {"label": "Learn More | اعرف المزيد", "action": "learn_more"}
            ]
        }
    
    async def _handle_case_summary(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond with domain-sensitive case summary (Arabic First)."""
        clf = analysis.get("classification", {})
        principles = analysis.get("legal_principles", [])
        recommendation = analysis.get("recommendation", {})
        trends = analysis.get("trends", {})
        case_type_en = clf.get('name_en', '').lower()
        
        # Domain-Sensitive Principle Selection
        if "traffic" in case_type_en or "accident" in case_type_en or "injury" in case_type_en:
            domain_principles_ar = [
                "• المسؤولية عن الضرر - كل خطأ سبب ضرراً للغير يلزم من ارتكبه بالتعويض.",
                "• الضمان - المتسبب في الضرر ضامن وإن لم يتعمد."
            ]
            domain_principles_en = [
                "• Liability for Harm - Any fault causing harm to others obligates compensation.",
                "• Tort Liability - The cause of harm is liable regardless of intent."
            ]
        else:
            domain_principles_ar = [f"• [{p.get('name_ar', '')}]({p.get('url')}) - {p.get('description_ar', '')}" if p.get('url') else f"• {p.get('name_ar', '')} - {p.get('description_ar', '')}" for p in principles[:3]] if principles else ["• بناءً على المعطيات المتاحة، لم يتم استخراج مبادئ قانونية محددة. يرجى تزويدنا بتفاصيل إضافية."]
            domain_principles_en = [f"• [{p.get('name_en', '')}]({p.get('url')})" if p.get('url') else f"• {p.get('name_en', '')}" for p in principles[:3]] if principles else ["• Based on the provided data, no specific legal principles could be extracted. Please provide more details."]

        principles_text_ar = "\n".join(domain_principles_ar)
        principles_text_en = "\n".join(domain_principles_en)
        
        rec_text_ar = recommendation.get("recommendation_ar", "لم تتوفر توصيات")
        rec_text_en = recommendation.get("recommendation_en", "No recommendations available")
        
        # Currency Scrub
        rec_text_en = rec_text_en.replace("Rs.", "SAR").replace("rupees", "SAR").replace("Rupees", "SAR")
        
        flags = self._stats_flags(trends)
        win_rate = trends.get("plaintiff_win_rate", 0)
        sample_size = flags["sample_size"]
        if flags["can_show_win_rate"]:
            legal_position_ar = f"بناءً على {sample_size} سوابق قضائية مماثلة، تبلغ نسبة فوز المدعي حوالي {win_rate}%."
            legal_position_en = f"Based on {sample_size} historical precedents, the plaintiff win rate is approximately {win_rate}%."
        else:
            legal_position_ar = f"تم العثور على {sample_size} سوابق، لكن حجم العينة غير كافٍ لإخراج نسبة فوز موثوقة."
            legal_position_en = f"{sample_size} precedents were found, but this sample is too small for a reliable win-rate statistic."
        
        response_ar = f"""### ملخص التحليل الاستشاري
 
**نوع القضية:** {clf.get('name_ar', 'N/A')}
**الموقف القانوني:** {legal_position_ar}
 
**المبادئ القانونية المستند إليها:**
{principles_text_ar}
 
**التوصية القانونية:**
{rec_text_ar}"""
 
        response_en = f"""### Consultative Analysis Summary
 
**Case Type:** {clf.get('name_en', 'N/A')}
**Legal Position:** {legal_position_en}
 
**Applicable Legal Principles:**
{principles_text_en}
 
**Professional Recommendation:**
{rec_text_en}"""

        final_text = response_ar if analysis.get("language", "ar") == "ar" else response_en
        return {
            "text": final_text,
            "intent": "case_summary",
            "suggested_actions": [
                {"label": "Full Details | عرض التفاصيل الكاملة", "action": "full_analysis"},
                {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"},
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ],
            "citations": self._format_case_citations(analysis.get("related_cases", []))
        }
    
    async def _handle_case_type(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond with case classification (Arabic First)."""
        clf = analysis.get("classification", {})
            
        ar_text = f"""تصنيف القضية:

**النوع الرئيسي:** {clf.get('name_ar', 'غير معروف')}
**النوع الإنجليزي:** {clf.get('name_en', 'Unknown')}"""

        en_text = f"""Case Classification:

**Main Type:** {clf.get('name_ar', 'Unknown')}
**Type (English):** {clf.get('name_en', 'Unknown')}"""

        final_text = ar_text if analysis.get("language", "ar") == "ar" else en_text
        return {
            "text": final_text,
            "intent": "case_type",
            "suggested_actions": [
                {"label": "Legal Principles | المبادئ القانونية", "action": "legal_principles"},
                {"label": "Precedent Cases | قضايا سابقة", "action": "similar_cases"}
            ]
        }
    
    async def _handle_similar_cases(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Provide similar cases (Arabic First)."""
        trends = analysis.get("trends", {})
        classification = analysis.get("classification", {})
        rec = analysis.get("recommendation", {})
        flags = self._stats_flags(trends)
        direction = rec.get("direction", "").lower()
        is_judgement = direction == "decided_judgement" or "حكم" in str(rec.get("recommendation_ar", "")).lower()

        win_rate = trends.get("plaintiff_win_rate", 0)
        avg_compensation = trends.get("average_compensation", 0)
        ar_comp = (
            f"{avg_compensation} ريال"
            if flags["can_show_compensation"] and avg_compensation
            else "بيانات التعويض غير كافية حالياً"
        )
        en_comp = (
            f"{avg_compensation} SAR"
            if flags["can_show_compensation"] and avg_compensation
            else "Insufficient historical compensation data available"
        )
        
        case_type_ar = classification.get('name_ar', 'قضيتك')
        case_type_en = classification.get('name_en', 'your case')
        sample_size = flags["sample_size"]

        if is_judgement:
            case_status_ar = "تم الحكم فيها"
            case_status_en = "Already Judged"
        elif flags["can_show_win_rate"]:
            case_status_ar = f"نسبة فوز المدعي: {win_rate}%"
            case_status_en = f"Plaintiff Win Rate: {win_rate}%"
        else:
            case_status_ar = "حجم العينة غير كافٍ لعرض نسبة فوز موثوقة"
            case_status_en = "Sample size is insufficient for a reliable win-rate statistic"

        ar_text = f"نتائج البحث عن قضايا مشابهة:\n\nلقد وجدنا قضايا مرتبطة بنوع: **{case_type_ar}**. (إجمالي العينة: {sample_size} قضايا)\n\n**الإحصائيات المستخلصة من السوابق:**\n• حالة القضية: {case_status_ar}\n• متوسط التعويض: {ar_comp}\n\n**السوابق والقرارات القضائية (مرفقة أدناه):**\nتم اختيار أهم السوابق القضائية المشابهة لحالتك والمبنية على مبادئ محاكمنا."
        en_text = f"**Similar Case Results:**\n\nWe found precedents related to: **{case_type_en}**. (Total sample: {sample_size} cases)\n\n**Extracted Trend Data:**\n• Case Status: {case_status_en}\n• Average Compensation: {en_comp}\n\n**Detailed Precedents (Listed Below):**\nWe have identified the most relevant historical decisions matching your case context."

        final_text = ar_text if analysis.get("language", "ar") == "ar" else en_text
        return {
            "text": final_text,
            "intent": "similar_cases",
            "suggested_actions": [
                {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"},
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ],
            "citations": self._format_case_citations(analysis.get("related_cases", []))
        }
    
    async def _handle_legal_principles(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond with legal principles (Arabic First)."""
        principles = analysis.get("legal_principles", [])[:5]
        if not principles:
            ar_text = "⚖️ بناءً على المعطيات المتاحة، لم يتم استخراج مبادئ قانونية محددة مرتبطة بهذه الحالة. يرجى تزويدنا بتفاصيل إضافية للحصول على أدق تحليل."
            en_text = "⚖️ Based on the provided data, no specific legal principles could be extracted. Please provide more details for a more accurate analysis."
        else:
            principles_text_ar = "\n".join([f"  • **[{p.get('name_ar', 'N/A')}]({p.get('url')})** - {p.get('description_ar', '')}" if p.get('url') else f"  • **{p.get('name_ar', 'N/A')}** - {p.get('description_ar', '')}" for p in principles])
            principles_text_en = "\n".join([f"  • **[{p.get('name_en', 'N/A')}]({p.get('url')})**" if p.get('url') else f"  • **{p.get('name_en', 'N/A')}**" for p in principles])
            ar_text = f"⚖️ المبادئ القانونية ذات الصلة:\n\n{principles_text_ar}"
            en_text = f"⚖️ Relevant Legal Principles:\n\n{principles_text_en}"
            
        final_text = ar_text if analysis.get("language", "ar") == "ar" else en_text
        return {
            "text": final_text,
            "intent": "legal_principles",
            "suggested_actions": [
                {"label": "Recommendations | التوصيات", "action": "recommendations"},
                {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"}
            ]
        }
    
    async def _handle_trends(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond with trend statistics (Arabic First)."""
        trends = analysis.get("trends", {})
        flags = self._stats_flags(trends)

        if not flags["can_show_trend_analysis"]:
            ar_text = (
                f"تم العثور على {flags['sample_size']} سوابق، "
                "لكن حجم العينة غير كافٍ لاستخراج اتجاهات إحصائية موثوقة."
            )
            en_text = (
                f"Found {flags['sample_size']} precedents, but this sample is too small "
                "for reliable trend statistics."
            )
        else:
            ar_text = (
                f"الاتجاهات الإحصائية (بناءً على {flags['sample_size']} سوابق):\n\n"
                f"**معدل فوز المدعي:** {trends.get('plaintiff_win_rate', 0)}%"
            )
            en_text = (
                f"Trend Statistics (Based on {flags['sample_size']} cases):\n\n"
                f"**Plaintiff Win Rate:** {trends.get('plaintiff_win_rate', 0)}%"
            )

        final_text = ar_text if analysis.get("language", "ar") == "ar" else en_text
        return {
            "text": final_text,
            "intent": "trends",
            "suggested_actions": [
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ],
            "citations": self._format_case_citations(analysis.get("related_cases", []))
        }
    
    async def _handle_recommendation(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond with actionable lifecycle-aware recommendation (Arabic First)."""
        classification = analysis.get("classification", {})
        recommendation = analysis.get("recommendation", {})
        trends = analysis.get("trends", {})
        direction = recommendation.get("direction", "").lower()
        is_judgement = direction == "decided_judgement" or "حكم" in str(recommendation.get("recommendation_ar", "")).lower() or trends.get("is_judgement", False)

        if self.llm:
            try:
                case_context = {
                    "classification": classification,
                    "is_judgement": is_judgement,
                    "amount": recommendation.get("award_amount"),
                    "trends": trends,
                    "recommendation": recommendation,
                }
                validator = DataAvailabilityValidator()
                data_report = validator.generate_data_report(
                    {"available_cases": int(trends.get("sample_size", 0) or 0)}
                )
                
                system_prompt = """أنت محامي سعودي خبير بالأنظمة التجارية والمدنية والجزائية.
يجب أن تكون التوصيات عملية وإجرائية (Actionable Advice).
استخدم عملة 'SAR' أو 'ريال سعودي' حصراً. لا تستخدم 'Rs.' أو 'الروبية' أبداً."""

                if is_judgement:
                    system_prompt += """
السياق الحالي: مرحلة ما بعد الحكم (Post-Judgment).
المهام المطلوبة في التوصية:
1. المبادرة بتقديم طلب تنفيذ إلكتروني (Execution Request) عبر بوابة ناجز.
2. التأكد من تاريخ صدور الحكم لحساب مدة الاعتراض (30 يوماً).
3. في حال عدم السداد، التوصية بإجراءات الحجز (Asset Tracing & Freezing).
لا تطلب من المستخدم 'البحث عن أدلة' أو 'تحقيق إضافي' فالقضية محكومة."""
                else:
                    system_prompt += """
السياق الحالي: مرحلة ما قبل التقاضي/نزاع (Pre-litigation).
المهام المطلوبة في التوصية:
1. حصر الأدلة والأسانيد (العقود، المراسلات، تقارير الخبرة).
2. استكمال المتطلبات النظامية حسب نوع القضية.
3. تقدير الموقف القانوني بناءً على سوابق المحاكم العامة."""
                
                generated_rec = self.llm.generate_recommendations(case_context, data_report)
                
                # Global Currency Scrub
                generated_rec = generated_rec.replace("Rs.", "SAR").replace("rupees", "SAR").replace("Rupees", "SAR")
                
                return {
                    "text": generated_rec,
                    "intent": "recommendation",
                    "suggested_actions": [
                        {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"},
                        {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"}
                    ]
                }
            except: pass

        if is_judgement:
             actions = [
                {"label": "Enforcement Petition | طلب تنفيذ", "action": "draft_enforcement"},
                {"label": "Appeal Memo | مذكرة اعتراض", "action": "draft_appeal"}
             ]
        else:
             actions = [
                {"label": "Draft Claim | كتابة لائحة دعوى", "action": "draft_claim"},
                {"label": "Draft Defense | كتابة مذكرة دفاع", "action": "draft_defense"}
             ]

        return {
            "text": str(recommendation.get("recommendation_ar", "لا تتوفر توصية حالياً.")),
            "intent": "recommendation",
            "suggested_actions": actions
        }


    
    async def _handle_full_analysis(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Provide a full structured case analysis in Arabic."""
        clf = analysis.get("classification", {}) or {}
        trends = analysis.get("trends", {}) or {}
        recommendation = analysis.get("recommendation", {}) or {}
        entities = analysis.get("entities", {}) or {}
        principles = analysis.get("legal_principles", []) or []
        related_cases = analysis.get("related_cases", []) or []

        direction = str(recommendation.get("direction", "")).lower()
        rec_ar = str(recommendation.get("recommendation_ar", "لا تتوفر توصية تفصيلية حالياً."))
        is_judgement = (
            direction == "decided_judgement"
            or "حكم" in rec_ar
            or bool(trends.get("is_judgement", False))
        )

        court_name = entities.get("court_name")
        if not court_name and related_cases and isinstance(related_cases[0], dict):
            court_name = ((related_cases[0].get("case") or {}).get("court"))
        court_name = court_name or "غير محدد"

        plaintiff = entities.get("plaintiff") or "غير محدد"
        defendant = entities.get("defendant") or "غير محدد"
        case_date = entities.get("date") or "غير محدد"
        doc_type = entities.get("doc_type") or "legal_document"
        dispute_type = entities.get("dispute_type") or "غير محدد"
        judgment_result = entities.get("judgment_result") or "غير متوفر"
        compensation_amount = entities.get("compensation_amount") or "غير متوفر"
        salary = entities.get("salary") or "غير متوفر"
        duration = entities.get("duration") or "غير متوفر"
        articles = entities.get("articles") or []

        subtype_lines = []
        for st in (clf.get("sub_types") or [])[:3]:
            if isinstance(st, dict):
                subtype_lines.append(
                    f"- {st.get('name_ar', st.get('case_type', 'غير محدد'))} ({st.get('relevance', 0)}%)"
                )

        principle_lines = []
        is_ar = analysis.get("language", "ar") == "ar"
        for pr in principles[:5]:
            if isinstance(pr, dict):
                p_text = pr.get('name_ar', 'مبدأ قانوني') if is_ar else pr.get('name_en', 'Legal Principle')
                principle_lines.append(f"- {p_text}")
        if not principle_lines:
            principle_lines = ["- لا توجد مبادئ قانونية مستخرجة من النص الحالي."] if is_ar else ["- No legal principles extracted from the current text."]

        outcomes = trends.get("outcomes", {}) if isinstance(trends.get("outcomes", {}), dict) else {}
        outcomes_text = "\n".join([f"- {k}: {v}" for k, v in outcomes.items()]) if outcomes else "- لا تتوفر بيانات نتائج مفصلة."

        related_lines = []
        for rc in related_cases[:3]:
            if not isinstance(rc, dict):
                continue
            case_obj = rc.get("case", {}) or {}
            related_lines.append(
                "\n".join([
                    f"- القضية: {case_obj.get('case_id', 'N/A')}",
                    f"  المحكمة: {case_obj.get('court', 'غير محدد')}",
                    f"  درجة التشابه: {rc.get('similarity_score', 'N/A')}%",
                    f"  المنطوق: {case_obj.get('judgment', 'غير متوفر')}",
                ])
            )
        if not related_lines:
            related_lines = ["- لا توجد سوابق مشابهة كافية."]

        article_text = "، ".join(articles[:8]) if articles else "غير متوفر"
        subtypes_text = "\n".join(subtype_lines) if subtype_lines else "- لا توجد تصنيفات فرعية بارزة."

        ar_text = f"""### التحليل الشامل للقضية

#### 1) البيانات الأساسية
- نوع القضية: {clf.get('name_ar', 'غير محدد')}
- المحكمة: {court_name}
- تاريخ القضية/الحكم: {case_date}
- نوع المستند: {doc_type}
- نوع النزاع: {dispute_type}

#### 2) الأطراف والكيانات
- المدعي: {plaintiff}
- المدعى عليه: {defendant}
- نتيجة الحكم (إن وجدت): {judgment_result}
- مبلغ التعويض: {compensation_amount}
- الراتب/الأجر: {salary}
- المدة: {duration}
- المواد/الإشارات النظامية المستخرجة: {article_text}

#### 3) التصنيف القانوني
- التصنيف الرئيسي: {clf.get('name_ar', 'غير محدد')}
- التصنيف الإنجليزي: {clf.get('name_en', 'N/A')}
- الكلمات المطابقة: {", ".join(clf.get('matched_keywords', [])[:8]) if clf.get('matched_keywords') else 'غير متوفر'}
- التصنيفات الفرعية:
{subtypes_text}

#### 4) المبادئ القانونية المستخرجة
{chr(10).join(principle_lines)}

#### 5) التحليل الإحصائي والاتجاهات
- حجم العينة: {trends.get('sample_size', 0)}
- القضايا المفصول فيها: {trends.get('decided_cases', 0)}
- معدل فوز المدعي: {trends.get('plaintiff_win_rate', 0)}%
- متوسط التعويض: {trends.get('average_compensation', 0)}
- وسيط التعويض: {trends.get('median_compensation', 0)}
- نطاق التعويض: {trends.get('compensation_range', {}) if trends.get('compensation_range') else 'غير متوفر'}
- موثوقية الإحصاء: {trends.get('reliability', 'غير متوفر')}
- توزيع النتائج:
{outcomes_text}

#### 6) التوصية القانونية
- الاتجاه: {recommendation.get('direction', 'غير محدد')}
- الثقة: {recommendation.get('confidence', 0)}%
- التوصية:
{rec_ar}
- إخلاء المسؤولية:
{recommendation.get('disclaimer_ar', 'هذا تحليل استرشادي لدعم القرار وليس حكماً قضائياً ملزماً.')}

#### 7) السوابق الأقرب
{chr(10).join(related_lines)}
"""

        en_text = f"""### Comprehensive Case Analysis

#### 1) Basic Data
- Case Type: {clf.get('name_en', 'Unspecified')}
- Court: {court_name}
- Case/Judgment Date: {case_date}
- Document Type: {doc_type}
- Dispute Type: {dispute_type}

#### 2) Parties and Entities
- Plaintiff: {plaintiff}
- Defendant: {defendant}
- Judgment Result (if any): {judgment_result}
- Compensation Amount: {compensation_amount}
- Salary/Wage: {salary}
- Duration: {duration}
- Extracted Articles/Statutory References: {article_text}

#### 3) Legal Classification
- Main Classification: {clf.get('name_en', 'Unspecified')}
- Arabic Classification: {clf.get('name_ar', 'N/A')}
- Matched Keywords: {", ".join(clf.get('matched_keywords', [])[:8]) if clf.get('matched_keywords') else 'Unavailable'}
- Subclassifications:
{subtypes_text}

#### 4) Extracted Legal Principles
{chr(10).join(principle_lines)}

#### 5) Statistical Analysis and Trends
- Sample Size: {trends.get('sample_size', 0)}
- Decided Cases: {trends.get('decided_cases', 0)}
- Plaintiff Win Rate: {trends.get('plaintiff_win_rate', 0)}%
- Avg Compensation: {trends.get('average_compensation', 0)}
- Median Compensation: {trends.get('median_compensation', 0)}
- Compensation Range: {trends.get('compensation_range', {}) if trends.get('compensation_range') else 'Unavailable'}
- Statistical Reliability: {trends.get('reliability', 'Unavailable')}
- Outcome Distribution:
{outcomes_text}

#### 6) Legal Recommendation
- Direction: {recommendation.get('direction', 'Unspecified')}
- Confidence: {recommendation.get('confidence', 0)}%
- Recommendation:
{rec_ar}
- Disclaimer:
{recommendation.get('disclaimer_en', 'This is an advisory analysis to support decision-making and not a binding judicial ruling.')}

#### 7) Closest Precedents
{chr(10).join(related_lines)}
"""

        if is_judgement:
            suggested_actions = [
                {"label": "Enforcement Petition | طلب تنفيذ", "action": "draft_enforcement"},
                {"label": "Appeal Memo | مذكرة اعتراض", "action": "draft_appeal"},
            ]
        else:
            suggested_actions = [
                {"label": "Draft Claim | كتابة لائحة دعوى", "action": "draft_claim"},
                {"label": "Draft Defense | كتابة مذكرة دفاع", "action": "draft_defense"},
            ]

        final_text = ar_text if analysis.get("language", "ar") == "ar" else en_text
        return {
            "text": final_text.strip(),
            "intent": "full_analysis",
            "suggested_actions": suggested_actions,
            "citations": self._format_case_citations(related_cases),
        }

    async def _handle_bench_memo(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate a Judicial Bench Memo combining key analysis metrics."""
        clf = analysis.get("classification", {})
        principles = analysis.get("legal_principles", [])
        recommendation = analysis.get("recommendation", {})
        trends = analysis.get("trends", {})
        case_strength = analysis.get("case_strength", "غير محدد")
        appeal_risk = analysis.get("appeal_risk", "غير محدد")
        contradictions = analysis.get("contradictions", [])
        
        ar_text = f"""### مذكرة تحضيرية للقاضي (Bench Memo)

**التصنيف:** {clf.get('name_ar', 'غير محدد')}
**قوة موقف الدعوى:** {case_strength}
**خطر الاستئناف/النقض:** {appeal_risk}

#### 1) الموقف القانوني والاحتماليات
- **نسبة فوز المدعي:** {trends.get('plaintiff_win_rate', 0)}% (بناءً على {trends.get('sample_size', 0)} سوابق)
- **متوسط التعويض في السوابق:** {trends.get('average_compensation', 0)} ريال.

#### 2) المبادئ القانونية والنظامية المفتاحية\n"""
        for p in principles[:3]:
            # Inject URL if exists
            p_name = f"[{p.get('name_ar')}]({p.get('url')})" if p.get('url') else p.get('name_ar')
            ar_text += f"- **{p_name}**: {p.get('description_ar')}\n"
        if not principles:
            ar_text += "- لم يتم استخراج مبادئ صريحة.\n"
            
        ar_text += "\n#### 3) التناقضات أو الملاحظات الجوهرية (Contradictions)\n"
        for c in contradictions:
            ar_text += f"- {c}\n"
            
        ar_text += f"\n#### 4) الرأي المقترح (Recommendation)\n{recommendation.get('recommendation_ar', 'لا توجد توصية.')}"

        en_text = f"""### Judicial Bench Memo

**Classification:** {clf.get('name_en', 'Unspecified')}
**Case Strength:** {case_strength}
**Appeal Risk:** {appeal_risk}

#### 1) Legal Position & Probabilities
- **Plaintiff Win Rate:** {trends.get('plaintiff_win_rate', 0)}% (Based on {trends.get('sample_size', 0)} precedents)
- **Historical Average Compensation:** {trends.get('average_compensation', 0)} SAR.

#### 2) Key Statutory Principles\n"""
        for p in principles[:3]:
            p_name = f"[{p.get('name_en')}]({p.get('url')})" if p.get('url') else p.get('name_en')
            en_text += f"- **{p_name}**\n"
        if not principles:
            en_text += "- No explicit principles extracted.\n"
            
        en_text += "\n#### 3) Material Contradictions & Notes\n"
        for c in contradictions:
             en_text += f"- {c}\n"
             
        en_text += f"\n#### 4) Suggested Opinion\n{recommendation.get('recommendation_en', 'No recommendation.')}"

        final_text = ar_text if analysis.get("language", "ar") == "ar" else en_text
        return {
            "text": final_text.strip(),
            "intent": "bench_memo",
            "suggested_actions": [
                {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"},
                {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"}
            ],
            "citations": self._format_case_citations(analysis.get("related_cases", []))
        }

    async def _handle_bench_memo(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Aggregate all Phase 2 metrics into a unified Judges Bench Memo."""
        clf = analysis.get("classification", {})
        case_type_ar = clf.get("name_ar", "غير محدد")
        case_type_en = clf.get("name_en", "Unknown")
        
        case_strength = analysis.get("case_strength", "متوسط")
        appeal_risk = analysis.get("appeal_risk", "متوسط")
        contradictions = analysis.get("contradictions", [])
        principles = analysis.get("legal_principles", [])
        recommendation = analysis.get("recommendation", {}).get("recommendation_ar", "لا تتوفر توصية")
        recommendation_en = analysis.get("recommendation", {}).get("recommendation_en", "No recommendation")
        
        ar_principles = "\n".join([f"- **[{p.get('name_ar')}]({p.get('url')})**: {p.get('description_ar', '')}" if p.get('url') else f"- **{p.get('name_ar')}**: {p.get('description_ar', '')}" for p in principles[:3]]) if principles else "- لم تتوفر مبادئ قطعية متعلقة بالنص."
        en_principles = "\n".join([f"- **[{p.get('name_en')}]({p.get('url')})**" if p.get('url') else f"- **{p.get('name_en')}**" for p in principles[:3]]) if principles else "- No explicit principles found."
        
        ar_contradictions = "\n".join([f"- ⚠️ {c}" for c in contradictions]) if contradictions else "- ✅ لم يتم رصد تناقضات بارزة"
        en_contradictions = "\n".join([f"- ⚠️ {c}" for c in contradictions]) if contradictions else "- ✅ No notable contradictions detected"
        
        memo_ar = f"""### مذكرة تحضيرية للقاضي (Bench Memo) ⚖️

**توصيف الدعوى:** {case_type_ar}
**مؤشر القوة القانونية:** {case_strength}
**مخاطر استئناف الحكم:** {appeal_risk}

#### 1. الملاحظات والتناقضات المرصودة:
{ar_contradictions}

#### 2. المبادئ والمواد المستند إليها:
{ar_principles}

#### 3. التوجيه القضائي المقترح:
{recommendation}"""

        memo_en = f"""### Judicial Bench Memo ⚖️

**Case Classification:** {case_type_en}
**Case Strength Index:** {case_strength}
**Appeal Risk:** {appeal_risk}

#### 1. Detected Contradictions/Flags:
{en_contradictions}

#### 2. Anchored Legal Principles:
{en_principles}

#### 3. Proposed Judicial Direction:
{recommendation_en}"""

        lang = analysis.get("language", "ar")
        final_text = memo_ar if lang == "ar" else memo_en

        return {
            "text": final_text,
            "intent": "bench_memo",
            "suggested_actions": [
                {"label": "Draft Judgment | مسودة حكم", "action": "draft_enforcement"},
                {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"}
            ],
            "citations": self._format_case_citations(analysis.get("related_cases", []))
        }

    # --- STATIC LEGAL TEMPLATES ---
    CLAIM_TEMPLATE_AR = """### مسودة لائحة دعوى
 
**إلى محكمة:** {court_name}
**موضوع الدعوى:** {case_type}
 
#### 1. الأطراف:
- **المدعي:** [يتم إدراج الاسم هنا]
- **المدعى عليه:** [يتم إدراج الاسم هنا]
 
#### 2. وقائع الدعوى:
{facts_summary}
 
#### 3. الأسانيد النظامية والشرعية:
{legal_basis}
 
#### 4. الطلبات:
- إلزام المدعى عليه بدفع مبلغ وقدره **({amount} ريال سعودي)**.
- إلزام المدعى عليه بكافة المصاريف القضائية وأتعاب المحاماة."""

    CLAIM_TEMPLATE_EN = """### Plaintiff's Claim Draft
 
#### 1. Parties:
- **Plaintiff:** [Insert Name]
- **Defendant:** [Insert Name]
 
#### 2. Factual Summary:
{facts_summary_en}
 
#### 3. Legal Grounds:
{legal_basis_en}"""
 
    DEFENSE_TEMPLATE_AR = """### مسودة مذكرة دفاع
 
**إلى محكمة:** {court_name}
 
#### 1. الأطراف:
- **المدعي:** [يتم إدراج الاسم هنا]
- **المدعى عليه:** [يتم إدراج الاسم هنا]
 
#### 2. ملخص الرد:
{facts_summary}
 
#### 3. الدفوع القانونية:
{legal_basis}
 
#### 4. الطلبات:
- الحكم بصرف النظر عن الدعوى لعدم الصحة والجدارة."""

    DEFENSE_TEMPLATE_EN = """### Defense Memo Draft
 
**To Court:** {court_name}
 
#### 1. Parties:
- **Plaintiff:** [Insert Name]
- **Defendant:** [Insert Name]
 
#### 2. Defense Summary:
{facts_summary}
 
#### 3. Legal Defenses:
{legal_basis}
 
#### 4. Requests:
- Dismissal of the lawsuit due to lack of merit and validity."""
 
    APPEAL_TEMPLATE_AR = """### مسودة مذكرة اعتراض
 
#### 1. وقائع القضية:
{facts_summary}
 
#### 2. أسباب الاعتراض:
{legal_basis}
 
#### 3. الطلبات:
- قبول الاعتراض شكلاً وموضوعاً، ونقض الحكم الصادر."""

    APPEAL_TEMPLATE_EN = """### Appeal Memo Draft
 
#### 1. Case Facts:
{facts_summary}
 
#### 2. Grounds for Appeal:
{legal_basis}
 
#### 3. Requests:
- Acceptance of the appeal in form and substance, and overturning the issued judgment."""
 
    ENFORCEMENT_TEMPLATE_AR = """### مسودة طلب تنفيذ
 
- **طالب التنفيذ:** [يتم إدراج الاسم هنا]
- **المنفذ ضده:** [يتم إدراج الاسم هنا]
 
#### 1. ملخص المستحقات:
{facts_summary}
 
#### 2. الطلبات الإجرائية:
- إلزام المنفذ ضده بسداد مبلغ وقدره **({amount} ريال سعودي)** فوراً."""

    ENFORCEMENT_TEMPLATE_EN = """### Enforcement Petition Draft
 
- **Execution Petitioner:** [Insert Name]
- **Executed Against:** [Insert Name]
 
#### 1. Summary of Dues:
{facts_summary}
 
#### 2. Procedural Requests:
- Compel the executed against to immediately pay the amount of **({amount} SAR)**."""

    async def _handle_draft_request(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Handle draft selection."""
        return {
            "text": "يرجى اختيار نوع المسودة المراد إنشاؤها:",
            "intent": "draft",
            "suggested_actions": [
                {"label": "Plaintiff Claim | لائحة دعوى", "action": "draft_claim"},
                {"label": "Defense Memo | مذكرة دفاع", "action": "draft_defense"}
            ]
        }

    async def _handle_draft_claim(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate a plaintiff claim draft (Enterprise Grounding)."""
        clf = analysis.get("classification", {})
        case_type_ar = clf.get("name_ar", "غير محدد")
        case_text = self.context.case_text or ""
        recommendation = analysis.get("recommendation", {})
        amount = recommendation.get("award_amount", "............")
        
        facts_summary, legal_basis, facts_summary_en, legal_basis_en = "............", "............", "............", "............"
        citations = []

        if self.llm:
            try:
                logger.info("LLM draft_claim generation started.")
                legal_context, citations = self._get_legal_context(case_type_ar)
                target_prompt = f"""STRICT GROUNDING TASK:
Draft facts and legal grounds for a '{case_type_ar}' claim.
CASE TEXT: {case_text}
CLAIM AMOUNT: {amount} SAR
ROLES: Plaintiff (Claimant), Defendant (Respondent).

STRICT INSTRUCTIONS:
- Use ONLY facts from the CASE TEXT.
- Use currency 'SAR' or 'Saudi Riyals' only.
- Do NOT invent companies, employment roles (Manager), or moral damages.
- Do NOT flip roles.
- Output format:
1. ملخص الوقائع: [Arabic text]
2. الأسانيد: [Arabic text]"""
                
                ai_output = self.llm.generate(target_prompt, system_prompt=f"أنت خبير صياغة لوائح دعوى سعودي. السياق الأنظمة: {legal_context}")
                logger.info("LLM draft_claim generation completed (chars=%s).", len(ai_output or ""))
                ai_output = self._clean_draft(ai_output, {"amount": amount})
                
                # Global Currency Scrub
                ai_output = ai_output.replace("Rs.", "SAR").replace("rupees", "SAR").replace("Rupees", "SAR")

                if "1." in ai_output and "2." in ai_output:
                    parts = ai_output.split("2.")
                    facts_summary = parts[0].replace("1.", "").replace("ملخص الوقائع:", "").strip()
                    legal_basis = parts[1].replace("الأسانيد:", "").strip()
                
                if HAS_TRANSLATOR:
                    facts_summary_en = GoogleTranslator(source='auto', target='en').translate(facts_summary[:500])
                    legal_basis_en = GoogleTranslator(source='auto', target='en').translate(legal_basis[:500])
                    # Ensure translated currency is correct
                    facts_summary_en = (facts_summary_en or "............").replace("Rs.", "SAR").replace("rupees", "SAR")
                    legal_basis_en = (legal_basis_en or "............").replace("Rs.", "SAR").replace("rupees", "SAR")
            except Exception as e:
                logger.warning("LLM draft_claim generation failed: %r", e, exc_info=True)
        if not facts_summary or facts_summary.strip() == "............":
            fallback_case = (case_text or "").strip()
            facts_summary = fallback_case[:700] if fallback_case else "وقائع الدعوى مستخلصة من ملف القضية المرفوع، ويطلب المدعي إلزام المدعى عليه بالحقوق محل النزاع."
        if not legal_basis or legal_basis.strip() == "............":
            principles = analysis.get("legal_principles", []) or []
            principle_names = [p.get("name_ar") for p in principles if isinstance(p, dict) and p.get("name_ar")]
            legal_basis = "الأسانيد النظامية: القواعد العامة في الإثبات والعقود والمسؤولية المدنية وفق الأنظمة السعودية."
            if principle_names:
                legal_basis += " المبادئ ذات الصلة: " + "، ".join(principle_names[:3]) + "."
        if analysis.get("language", "ar") == "ar":
            final_text = self.CLAIM_TEMPLATE_AR.format(
                court_name="المحكمة العامة",
                case_type=case_type_ar,
                facts_summary=facts_summary,
                legal_basis=legal_basis,
                amount=amount
            )
        else:
            final_text = self.CLAIM_TEMPLATE_EN.format(
                facts_summary_en=facts_summary_en,
                legal_basis_en=legal_basis_en
            )
        return {
            "text": final_text, 
            "intent": "draft_claim", 
            "metadata": {"is_draft": True}, 
            "citations": citations,
            "suggested_actions": [
                {"label": "Draft Defense | مذكرة دفاع", "action": "draft_defense"}, 
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ]
        }

    async def _handle_draft_defense(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate a defense memo draft (Enterprise Grounding)."""
        clf = analysis.get("classification", {})
        case_type_ar = clf.get("name_ar", "غير محدد")
        case_text = self.context.case_text or ""
        recommendation = analysis.get("recommendation", {})
        amount = recommendation.get("award_amount", "............")
        facts_summary, legal_basis, facts_summary_en, legal_basis_en = "............", "............", "............", "............"
        
        citations = []
        if self.llm:
            try:
                logger.info("LLM draft_defense generation started.")
                legal_context, citations = self._get_legal_context(case_type_ar)
                target_prompt = f"""STRICT GROUNDING TASK:
Draft a defense response for a '{case_type_ar}' case.
CASE TEXT: {case_text}
ROLES: Plaintiff (Opponent), Defendant (Client).

STRICT INSTRUCTIONS:
- Use ONLY the CASE TEXT to build defenses.
- Use currency 'SAR' or 'Saudi Riyals' only.
- Do NOT introduce fake employment narratives.
- Do NOT refer to the client as the 'Manager' unless explicitly in text.
- Output format:
1. ملخص الرد: [Arabic text]
2. الدفوع: [Arabic text]"""
                
                ai_output = self.llm.generate(target_prompt, system_prompt=f"أنت محامي دفاع سعودي. السياق الأنظمة: {legal_context}")
                logger.info("LLM draft_defense generation completed (chars=%s).", len(ai_output or ""))
                ai_output = self._clean_draft(ai_output, {"amount": amount})
                # Global Currency Scrub
                ai_output = ai_output.replace("Rs.", "SAR").replace("rupees", "SAR").replace("Rupees", "SAR")

                if "1." in ai_output and "2." in ai_output:
                    parts = ai_output.split("2.")
                    facts_summary = parts[0].replace("1.", "").replace("ملخص الرد:", "").strip()
                    legal_basis = parts[1].replace("الدفوع:", "").strip()
            except Exception as e:
                logger.warning("LLM draft_defense generation failed: %r", e, exc_info=True)
        if not facts_summary or facts_summary.strip() == "............":
            fallback_case = (case_text or "").strip()
            facts_summary = fallback_case[:700] if fallback_case else "ملخص الرد مستمد من الوقائع الواردة في ملف القضية، مع التمسك بدفوع شكلية وموضوعية لصالح المدعى عليه."
        if not legal_basis or legal_basis.strip() == "............":
            principles = analysis.get("legal_principles", []) or []
            principle_names = [p.get("name_ar") for p in principles if isinstance(p, dict) and p.get("name_ar")]
            legal_basis = "الدفوع النظامية: انتفاء أركان المسؤولية أو عدم كفاية الإثبات أو عدم توافر علاقة السببية وفق الأنظمة السعودية."
            if principle_names:
                legal_basis += " المبادئ ذات الصلة: " + "، ".join(principle_names[:3]) + "."
        lang = analysis.get("language", "ar")
        if lang == "ar":
            final_text = self.DEFENSE_TEMPLATE_AR.format(court_name="المحكمة العامة", facts_summary=facts_summary, legal_basis=legal_basis)
        else:
            final_text = self.DEFENSE_TEMPLATE_EN.format(court_name="General Court", facts_summary=facts_summary, legal_basis=legal_basis)
        return {
            "text": final_text, 
            "intent": "draft_defense", 
            "citations": citations,
            "suggested_actions": [
                {"label": "Draft Claim | لائحة دعوى", "action": "draft_claim"}, 
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ]
        }

    async def _handle_draft_enforcement(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate an enforcement petition (Standardized)."""
        recommendation = analysis.get("recommendation", {})
        entities = analysis.get("entities", {}) or {}
        amount = recommendation.get("award_amount") or entities.get("compensation_amount") or "............"
        fallback_summary = recommendation.get("recommendation_ar") or "بناءً على منطوق الحكم القضائي، يطلب طالب التنفيذ إلزام المنفذ ضده بسداد المبلغ المحكوم به واتخاذ إجراءات التنفيذ النظامية."
        lang = analysis.get("language", "ar")
        if lang == "ar":
            final_text = self.ENFORCEMENT_TEMPLATE_AR.format(amount=amount, facts_summary=fallback_summary)
        else:
            final_text = self.ENFORCEMENT_TEMPLATE_EN.format(amount=amount, facts_summary=fallback_summary)
        return {"text": final_text, "intent": "draft_enforcement", "citations": [], "suggested_actions": [{"label": "Appeal Memo | مذكرة اعتراض", "action": "draft_appeal"}]}

    async def _handle_draft_appeal(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate an appeal memo (Standardized)."""
        case_text = (self.context.case_text or "").strip()
        facts_summary = case_text[:600] if case_text else "وقائع الحكم محل الاعتراض: صدر حكم ابتدائي يتضمن إلزامات مالية، ونتمسك بوجود قصور في التسبيب وفساد في الاستدلال يستوجب نقض الحكم."
        principles = analysis.get("legal_principles", []) or []
        principle_names = [p.get("name_ar") for p in principles if isinstance(p, dict) and p.get("name_ar")]
        legal_basis = "الأساس النظامي للاعتراض: المادة 185 من نظام المرافعات الشرعية، مع التمسك بما ورد من قصور في التسبيب ومخالفة الثابت بالأوراق."
        if principle_names:
            legal_basis = f"{legal_basis} المبادئ ذات الصلة: " + "، ".join(principle_names[:3]) + "."
        lang = analysis.get("language", "ar")
        if lang == "ar":
            final_text = self.APPEAL_TEMPLATE_AR.format(facts_summary=facts_summary, legal_basis=legal_basis)
        else:
            final_text = self.APPEAL_TEMPLATE_EN.format(facts_summary=facts_summary, legal_basis=legal_basis)
        return {"text": final_text, "intent": "draft_appeal", "citations": [], "suggested_actions": [{"label": "Enforcement Petition | طلب تنفيذ", "action": "draft_enforcement"}]}

    def _clean_draft(self, text: str, facts: Dict) -> str:
        """Helper to remove hallucinations and enforce fact consistency."""
        if not text: return ""
        
        # 1. Purge non-Arabic/non-English hallucinations (Chinese characters, etc.)
        text = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\u2e80-\u2eff\u3000-\u303f\uff00-\uffef]+', '', text)
        
        # 2. Fact Consistency
        extracted_amount = str(facts.get("amount") or "")
        if extracted_amount and extracted_amount != "............":
            # Strip commas and currency markers for internal comparison
            clean_text = text.replace(',', '')
            clean_ext = extracted_amount.replace(',', '')
            matches = re.findall(r'(\d{4,})', clean_text)
            for m in matches:
                if m != clean_ext:
                    text = text.replace(m, extracted_amount)
        
        # 3. Strip common placeholders and narrative drift keywords
        blacklisted = [
            "Company A", "Company B", "شركة A", "شركة B", "34/1980", "1980 Law", 
            "المدير المسؤول", "مدير الشركة", "Manager", "Company", "Rs.", "rupees"
        ]
        for item in blacklisted:
            text = text.replace(item, "............")
            
        # 4. Remove generic LLM brackets
        text = re.sub(r'\[.*?\]', '............', text)
            
        return text.strip()

    async def _handle_outcome(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond about case outcome probability."""
        trends = analysis.get("trends", {})
        flags = self._stats_flags(trends)
        if flags["can_show_win_rate"]:
            text = (
                f"نسبة فوز المدعي التقريبية: {trends.get('plaintiff_win_rate', 0)}%\n"
                f"Approximation of Plaintiff win rate: {trends.get('plaintiff_win_rate', 0)}%"
            )
        else:
            text = (
                "البيانات المتاحة غير كافية لإظهار نسبة فوز موثوقة حالياً.\n"
                "Available precedent data is insufficient for a reliable win-rate estimate."
            )
        return {
            "text": text,
            "intent": "outcome",
            "suggested_actions": [
                {"label": "Detailed Recommendations | توصيات مفصلة", "action": "recommendations"},
                {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"}
            ]
        }

    async def _handle_compensation(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond about compensation information."""
        trends = analysis.get("trends", {})
        flags = self._stats_flags(trends)
        if flags["can_show_compensation"]:
            comp = trends.get("average_compensation", 0)
            text = (
                f"المعدل التاريخي للتعويضات: {comp} ر.س\n"
                f"Historical average compensation: {comp} SAR"
            )
        else:
            text = (
                "بيانات التعويضات غير كافية لإخراج متوسط إحصائي موثوق.\n"
                "Compensation data is insufficient for a reliable average."
            )
        return {
            "text": text,
            "intent": "compensation",
            "suggested_actions": [
                {"label": "Outcome Probability | احتمالية النتيجة", "action": "outcome"},
                {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"}
            ]
        }

    async def _handle_entities(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond about extracted entities."""
        entities = analysis.get("entities", {})
        entities_list = "\n".join([f"• {e}: {v}" for e, v in entities.items()])
        return {
            "text": f"الأطراف المكتشفة:\n{entities_list}\n\nDetected Entities:\n{entities_list}", 
            "intent": "entities",
            "suggested_actions": [
                {"label": "Case Summary | ملخص القضية", "action": "case_summary"},
                {"label": "Legal Principles | المبادئ القانونية", "action": "legal_principles"}
            ]
        }

    async def _handle_general_inquiry(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Handle general inquiries."""
        suggested = [
            {"label": "Case Summary | ملخص القضية", "action": "case_summary"},
            {"label": "Legal Recommendations | توصيات قانونية", "action": "recommendations"}
        ] if analysis else [
            {"label": "Analyze Case | تحليل قضية", "action": "upload"},
            {"label": "Search Precedents | بحث السوابق", "action": "similar_cases"}
        ]
        
        if self.llm and analysis:
            try:
                compact_analysis = {
                    "classification": analysis.get("classification"),
                    "trends": analysis.get("trends"),
                    "recommendation": analysis.get("recommendation"),
                    "legal_principles": (analysis.get("legal_principles") or [])[:3],
                    "entities": analysis.get("entities"),
                }
                res = self.llm.generate(
                    f"Compact case data: {json.dumps(compact_analysis, ensure_ascii=False)}\nQuestion: {query}",
                    system_prompt="You are a legal assistant.",
                    max_new_tokens=96,
                )
                return {"text": res, "intent": "general_inquiry", "suggested_actions": suggested}
            except Exception as e:
                logger.warning("General inquiry LLM fallback failed: %r", e, exc_info=True)
        
        text = "أنا هنا لمساعدتك في تحليل القضايا القانونية السعودية.\nI am here to help you analyze Saudi legal cases."
        return {"text": text, "intent": "general_inquiry", "suggested_actions": suggested}

    def get_conversation_history(self) -> List[Dict]:
        return self.context.get_last_n_messages(20)

    def clear_conversation(self):
        self.context.clear()

    def get_context_summary(self) -> Dict:
        return {
            "has_analysis": self.context.analysis_data is not None,
            "message_count": len(self.context.messages)
        }

    def _link_law_citations(self, text: str) -> str:
        """
        Scans text for references like "المادة 77" or "Article 77".
        If found and NOT already markdown-linked, wraps it in a markdown hyperlink
        pointing to the BOE.
        """
        if not text:
            return ""

        # Using a universal anchor link to Saudi Labor Law for demo/POC purposes.
        # Can easily be extended to dynamically resolve specific Law GUIDs via DB hit.
        boe_base_url = "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1"
        
        # Regex to find unlinked instances of "المادة X" or "Article X" or "الماده X" 
        # Negative lookbehind (?<!\[) and lookahead (?!\s*\]) ensure we don't double-link existing markdown
        pattern_ar = r'(?<!\[)(المادة\s+\d+|الماده\s+\d+)(?!\s*\]|\()'
        pattern_en = r'(?<!\[)(Article\s+\d+)(?!\s*\]|\()'
        
        # Replace occurrences with markdown links
        linked_text = re.sub(pattern_ar, rf'[\1]({boe_base_url})', text)
        linked_text = re.sub(pattern_en, rf'[\1]({boe_base_url})', linked_text)
        
        return linked_text
