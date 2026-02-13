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
        
    def set_analyzer(self, analyzer_func):
        """Inject the full analysis pipeline function."""
        self.analyzer = analyzer_func
    
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
            "outcome": ["النتيجة", "outcome", "result", "probability", "احتمالية"],
            "compensation": ["تعويض", "compensation", "damages", "amount", "مبلغ"],
            "entities": ["الأطراف", "parties", "entities", "من", "شخصيات"]
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
            
            self.context.add_message("user", user_message)
            
            user_translation = None
            if HAS_TRANSLATOR and any('\u0600' <= char <= '\u06FF' for char in user_message):
                try:
                    text_to_translate = user_message[:2000] 
                    user_translation = GoogleTranslator(source='auto', target='en').translate(text_to_translate)
                except Exception as e:
                    logger.warning(f"User message translation failed: {e}")
            
            intent = self.detect_intent(user_message)
            
            # Detect if this is a NEW case description requiring re-analysis
            is_new_case_input = False
            # Fix: Only treat as new case if text is sufficiently long (> 50 chars)
            # This prevents short commands like "case_summary" from being analyzed as a case
            if intent == "case_summary" and self.analyzer and len(user_message) > 50:
                if not self.context.analysis_data:
                    is_new_case_input = True
                elif len(user_message) > 400:
                    # Check if text is significantly different from current context
                    current_text = self.context.case_text or ""
                    if user_message[:100].lower() != current_text[:100].lower():
                        is_new_case_input = True

            if is_new_case_input:
                try:
                    logger.info("New case input detected. Triggering re-analysis...")
                    analysis_result = await self.analyzer(user_message)
                    analysis_dict = analysis_result.dict()
                    self.context.set_analysis(analysis_dict, user_message)
                except Exception as e:
                    logger.error(f"Auto-analysis failed: {e}")

            response = await self._generate_response(user_message, intent)
            
            # Include the current analysis in the response so the frontend stays synced
            response["analysis_data"] = self.context.analysis_data
            
            assistant_text = response.get("text", "")
            if HAS_TRANSLATOR and assistant_text and any('\u0600' <= char <= '\u06FF' for char in assistant_text):
                try:
                    is_bilingual = "---" in assistant_text
                    if not is_bilingual:
                        translated_text = GoogleTranslator(source='auto', target='en').translate(assistant_text[:4500])
                        if translated_text and translated_text.lower() != assistant_text.lower():
                            response["text"] = f"{assistant_text}\n\n---\n\n{translated_text}"
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
        
        has_analysis_handlers = {
            "case_summary": self._handle_case_summary,
            "case_type": self._handle_case_type,
            "similar_cases": self._handle_similar_cases,
            "legal_principles": self._handle_legal_principles,
            "trends": self._handle_trends,
            "recommendation": self._handle_recommendation,
            "full_analysis": self._handle_full_analysis,
            "draft": self._handle_draft_request,
            "draft_claim": self._handle_draft_claim,
            "draft_defense": self._handle_draft_defense,
            "draft_enforcement": self._handle_draft_enforcement,
            "draft_appeal": self._handle_draft_appeal,
            "outcome": self._handle_outcome,
            "compensation": self._handle_compensation,
            "entities": self._handle_entities,
        }
        
        if intent in has_analysis_handlers and not analysis:
            return await self._handle_no_analysis(user_message)
        
        if analysis:
            handler = has_analysis_handlers.get(intent, self._handle_general_inquiry)
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
            domain_principles_ar = [f"• {p.get('name_ar', '')} - {p.get('description_ar', '')}" for p in principles[:3]] if principles else ["لم يتم استخراج مبادئ"]
            domain_principles_en = [f"• {p.get('name_en', '')}" for p in principles[:3]] if principles else ["No principles extracted"]

        principles_text_ar = "\n".join(domain_principles_ar)
        principles_text_en = "\n".join(domain_principles_en)
        
        rec_text_ar = recommendation.get("recommendation_ar", "لم تتوفر توصيات")
        rec_text_en = recommendation.get("recommendation_en", "No recommendations available")
        
        # Currency Scrub
        rec_text_en = rec_text_en.replace("Rs.", "SAR").replace("rupees", "SAR").replace("Rupees", "SAR")
        
        win_rate = trends.get("plaintiff_win_rate", "N/A")
        sample_size = trends.get("sample_size", 0)
        
        response_ar = f"""### ملخص التحليل الاستشاري
 
**نوع القضية:** {clf.get('name_ar', 'N/A')}
**الموقف القانوني:** بناءً على {sample_size} سوابق قضائية مماثلة، تبلغ نسبة فوز المدعي حوالي {win_rate}%.
 
**المبادئ القانونية المستند إليها:**
{principles_text_ar}
 
**التوصية القانونية:**
{rec_text_ar}"""
 
        response_en = f"""### Consultative Analysis Summary
 
**Case Type:** {clf.get('name_en', 'N/A')}
**Legal Position:** Based on {sample_size} historical precedents, the plaintiff win rate is approximately {win_rate}%.
 
**Applicable Legal Principles:**
{principles_text_en}
 
**Professional Recommendation:**
{rec_text_en}"""

        return {
            "text": f"{response_ar}\n\n---\n\n{response_en}",
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
            
        return {
            "text": f"""تصنيف القضية:

**النوع الرئيسي:** {clf.get('name_ar', 'غير معروف')}
**النوع الإنجليزي:** {clf.get('name_en', 'Unknown')}

---

Case Classification:

**Main Type:** {clf.get('name_ar', 'Unknown')}
**Type (English):** {clf.get('name_en', 'Unknown')}""",
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
        direction = rec.get("direction", "").lower()
        is_judgement = direction == "decided_judgement" or "حكم" in str(rec.get("recommendation_ar", "")).lower()
        
        win_rate = trends.get('plaintiff_win_rate', 'N/A')
        avg_compensation = trends.get('avg_compensation', 'N/A')
        
        ar_comp = f"{avg_compensation} ريال" if avg_compensation != 'N/A' else "بيانات التعويض غير كافية حالياً"
        en_comp = f"{avg_compensation} SAR" if avg_compensation != 'N/A' else "Insufficient historical compensation data available"
        
        case_type_ar = classification.get('name_ar', 'قضيتك')
        case_type_en = classification.get('name_en', 'your case')
        sample_size = trends.get('sample_size', 0)

        case_status_ar = f"نسبة فوز المدعي: {win_rate}%" if not is_judgement else "تم الحكم فيها"
        case_status_en = f"Plaintiff Win Rate: {win_rate}%" if not is_judgement else "Already Judged"

        ar_text = f"نتائج البحث عن قضايا مشابهة:\n\nلقد وجدنا قضايا مرتبطة بنوع: **{case_type_ar}**. (إجمالي العينة: {sample_size} قضايا)\n\n**الإحصائيات المستخلصة من السوابق:**\n• حالة القضية: {case_status_ar}\n• متوسط التعويض: {ar_comp}\n\n**السوابق والقرارات القضائية (مرفقة أدناه):**\nتم اختيار أهم السوابق القضائية المشابهة لحالتك والمبنية على مبادئ محاكمنا."
        en_text = f"**Similar Case Results:**\n\nWe found precedents related to: **{case_type_en}**. (Total sample: {sample_size} cases)\n\n**Extracted Trend Data:**\n• Case Status: {case_status_en}\n• Average Compensation: {en_comp}\n\n**Detailed Precedents (Listed Below):**\nWe have identified the most relevant historical decisions matching your case context."

        return {
            "text": f"{ar_text}\n\n---\n\n{en_text}",
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
        principles_text_ar = "\n".join([f"  • **{p.get('name_ar', 'N/A')}** - {p.get('description_ar', '')}" for p in principles])
        principles_text_en = "\n".join([f"  • **{p.get('name_en', 'N/A')}**" for p in principles])
        
        return {
            "text": f"⚖️ المبادئ القانونية ذات الصلة:\n\n{principles_text_ar}\n\n---\n\n⚖️ Relevant Legal Principles:\n\n{principles_text_en}",
            "intent": "legal_principles",
            "suggested_actions": [
                {"label": "Recommendations | التوصيات", "action": "recommendations"},
                {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"}
            ]
        }
    
    async def _handle_trends(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond with trend statistics (Arabic First)."""
        trends = analysis.get("trends", {})
        sample_size = trends.get("sample_size", 0)
        
        ar_text = f"الاتجاهات الإحصائية (بناءً على {sample_size} سوابق):\n\n**معدل فوز المدعي:** {trends.get('plaintiff_win_rate', 0)}%"
        en_text = f"Trend Statistics (Based on {sample_size} cases):\n\n**Plaintiff Win Rate:** {trends.get('plaintiff_win_rate', 0)}%"

        return {
            "text": f"{ar_text}\n\n---\n\n{en_text}",
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
                case_context = json.dumps({"classification": classification, "is_judgement": is_judgement, "amount": recommendation.get("award_amount")}, ensure_ascii=False)
                
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
                
                prompt = f"بناءً على تحليل القضية: {case_context}\n\nقدم توصية قانونية عملية واحترافية (بالعربية أولاً ثم الإنجليزية)."
                generated_rec = self.llm.generate(prompt, system_prompt=system_prompt)
                
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

        return {
            "text": str(recommendation.get("recommendation_ar", "لا تتوفر توصية حالياً.")),
            "intent": "recommendation",
            "suggested_actions": [
                {"label": "Draft Claim | كتابة لائحة دعوى", "action": "draft_claim"},
                {"label": "Draft Defense | كتابة مذكرة دفاع", "action": "draft_defense"}
            ]
        }
    
    async def _handle_full_analysis(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Provide comprehensive analysis with lifecycle-aware routing (Arabic First)."""
        clf = analysis.get("classification", {})
        trends = analysis.get("trends", {})
        recommendation = analysis.get("recommendation", {})
        direction = recommendation.get("direction", "").lower()
        is_judgement = direction == "decided_judgement" or "حكم" in str(recommendation.get("recommendation_ar", "")).lower() or trends.get("is_judgement", False)
        
        ar_text = f"تحليل شامل للقضية:\n\n**التصنيف:** {clf.get('name_ar', 'N/A')}\n**معدل فوز المدعي (تاريخياً):** {trends.get('plaintiff_win_rate', 0)}%"
        en_text = f"Comprehensive Case Analysis:\n\n**Classification:** {clf.get('name_en', 'N/A')}\n**Historical Plaintiff Win Rate:** {trends.get('plaintiff_win_rate', 0)}%"

        # Enterprise Routing: Hide Claim/Defense for Judgments
        if is_judgement:
            suggested_actions = [
                {"label": "Enforcement Petition | طلب تنفيذ", "action": "draft_enforcement"},
                {"label": "Appeal Memo | مذكرة اعتراض", "action": "draft_appeal"}
            ]
        else:
            suggested_actions = [
                {"label": "Draft Claim | كتابة لائحة دعوى", "action": "draft_claim"},
                {"label": "Draft Defense | كتابة مذكرة دفاع", "action": "draft_defense"}
            ]

        return {
            "text": f"{ar_text}\n\n---\n\n{en_text}",
            "intent": "full_analysis",
            "suggested_actions": suggested_actions,
            "citations": self._format_case_citations(analysis.get("related_cases", []))
        }
    
    # --- STATIC LEGAL TEMPLATES ---
    CLAIM_TEMPLATE = """### مسودة لائحة دعوى
 
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
- إلزام المدعى عليه بكافة المصاريف القضائية وأتعاب المحاماة.
 
---
### Plaintiff's Claim Draft
 
#### 1. Parties:
- **Plaintiff:** [Insert Name]
- **Defendant:** [Insert Name]
 
#### 2. Factual Summary:
{facts_summary_en}
 
#### 3. Legal Grounds:
{legal_basis_en}"""
 
    DEFENSE_TEMPLATE = """### مسودة مذكرة دفاع
 
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
 
    APPEAL_TEMPLATE = """### مسودة مذكرة اعتراض
 
#### 1. وقائع القضية:
{facts_summary}
 
#### 2. أسباب الاعتراض:
{legal_basis}
 
#### 3. الطلبات:
- قبول الاعتراض شكلاً وموضوعاً، ونقض الحكم الصادر."""
 
    ENFORCEMENT_TEMPLATE = """### مسودة طلب تنفيذ
 
- **طالب التنفيذ:** [يتم إدراج الاسم هنا]
- **المنفذ ضده:** [يتم إدراج الاسم هنا]
 
#### 1. ملخص المستحقات:
{facts_summary}
 
#### 2. الطلبات الإجرائية:
- إلزام المنفذ ضده بسداد مبلغ وقدره **({amount} ريال سعودي)** فوراً."""

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
                    facts_summary_en = facts_summary_en.replace("Rs.", "SAR").replace("rupees", "SAR")
            except: pass

        final_text = self.CLAIM_TEMPLATE.format(
            court_name="المحكمة العامة", 
            case_type=case_type_ar, 
            facts_summary=facts_summary, 
            legal_basis=legal_basis, 
            facts_summary_en=facts_summary_en, 
            legal_basis_en=legal_basis_en, 
            amount=amount
        )
        return {
            "text": final_text, 
            "intent": "draft_claim", 
            "metadata": {"is_draft": True}, 
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
        
        if self.llm:
            try:
                legal_context, _ = self._get_legal_context(case_type_ar)
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
                ai_output = self._clean_draft(ai_output, {"amount": amount})
                # Global Currency Scrub
                ai_output = ai_output.replace("Rs.", "SAR").replace("rupees", "SAR").replace("Rupees", "SAR")

                if "1." in ai_output and "2." in ai_output:
                    parts = ai_output.split("2.")
                    facts_summary = parts[0].replace("1.", "").replace("ملخص الرد:", "").strip()
                    legal_basis = parts[1].replace("الدفوع:", "").strip()
            except: pass

        final_text = self.DEFENSE_TEMPLATE.format(court_name="المحكمة العامة", facts_summary=facts_summary, legal_basis=legal_basis)
        return {
            "text": final_text, 
            "intent": "draft_defense", 
            "suggested_actions": [
                {"label": "Draft Claim | لائحة دعوى", "action": "draft_claim"}, 
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ]
        }

    async def _handle_draft_enforcement(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate an enforcement petition (Standardized)."""
        recommendation = analysis.get("recommendation", {})
        amount = recommendation.get("award_amount", "............")
        final_text = self.ENFORCEMENT_TEMPLATE.format(amount=amount, facts_summary="بناءً على منطوق الحكم القاضي بإلزام المنفذ ضده بدفع المبلغ المذكور.")
        return {"text": final_text, "intent": "draft_enforcement", "suggested_actions": [{"label": "Appeal Memo | مذكرة اعتراض", "action": "draft_appeal"}]}

    async def _handle_draft_appeal(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate an appeal memo (Standardized)."""
        final_text = self.APPEAL_TEMPLATE.format(facts_summary="............ (يرجى وصف الحكم)، وأسبابه القصور في التسبيب والفساد في الاستدلال.", legal_basis="المادة 185 من نظام المرافعات الشرعية.")
        return {"text": final_text, "intent": "draft_appeal", "suggested_actions": [{"label": "Enforcement Petition | طلب تنفيذ", "action": "draft_enforcement"}]}

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
        win_rate = analysis.get("trends", {}).get("plaintiff_win_rate", 0)
        return {
            "text": f"نسبة فوز المدعي التقريبية: {win_rate}%\nApproximation of Plaintiff win rate: {win_rate}%", 
            "intent": "outcome",
            "suggested_actions": [
                {"label": "Detailed Recommendations | توصيات مفصلة", "action": "recommendations"},
                {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"}
            ]
        }

    async def _handle_compensation(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond about compensation information."""
        trends = analysis.get("trends", {})
        comp = trends.get('average_compensation', 0)
        return {
            "text": f"المعدل التاريخي للتعويضات: {comp} ر.س\nHistorical average compensation: {comp} SAR", 
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
                res = self.llm.generate(f"بيانات: {json.dumps(analysis, ensure_ascii=False)}\nسؤال: {query}", system_prompt="أنت مساعد قانوني.")
                return {"text": res, "intent": "general_inquiry", "suggested_actions": suggested}
            except: pass
        
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
