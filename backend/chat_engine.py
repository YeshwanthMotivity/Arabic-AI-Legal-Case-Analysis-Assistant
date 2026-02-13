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
    
    def set_analysis(self, analysis_data: Dict, case_text: str):
        """Store the current case analysis data."""
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
        
    def _initialize_intents(self) -> Dict[str, List[str]]:
        """Define intent detection keywords in Arabic and English."""
        return {
            "case_summary": ["ملخص", "summary", "ملخص القضية", "summarize", "اختصار", "case_summary", "show_details"],
            "case_type": ["النوع", "type", "classification", "التصنيف", "نوع القضية"],
            "similar_cases": ["حالات مشابهة", "similar", "precedent", "similar cases", "قضايا شبيهة", "قضايا مشابهة", "مشابهة", "search_similar"],
            "legal_principles": ["المبادئ", "principles", "قواعد قانونية", "legal_principles"],
            "trends": ["الاتجاهات", "trends", "statistics", "إحصائيات", "معدلات"],
            "recommendation": ["توصية", "advice", "رأي", "اقتراح", "recommendations"],
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
    
    def _is_likely_case(self, text: str) -> bool:
        """Detect if text is likely a legal case description."""
        if len(text) < 100:
            return False
            
        case_markers = [
            "الوقائع", "الأسباب", "منطوق الحكم", "حكمت المحكمة", 
            "المدعي", "المدعى عليه", "قضية رقم", "بناءً على"
        ]
        
        # Count how many markers are present
        matches = sum(1 for marker in case_markers if marker in text)
        
        # If it's long and has legal terms, it's likely a case description
        return matches >= 2 or (len(text) > 500 and matches >= 1)

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
            if analysis_data:
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
            
            if intent == "case_summary" and not self.context.analysis_data and self.analyzer:
                try:
                    analysis_result = await self.analyzer(user_message)
                    analysis_dict = analysis_result.dict()
                    self.context.set_analysis(analysis_dict, user_message)
                except Exception as e:
                    logger.error(f"Decisive analysis failed: {e}")

            response = await self._generate_response(user_message, intent)
            
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
                amount = current_analysis.get("recommendation", {}).get("award_amount") or "............"
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
        
        sample_size = trends.get("sample_size", 0)
        
        # Determine if this is a final judgment
        direction = recommendation.get("direction", "").lower()
        is_judgement = direction == "decided_judgement" or "حكم" in str(recommendation.get("recommendation_ar", "")).lower() or trends.get("is_judgement", False)
        
        award_amount = analysis.get("entities", {}).get("compensation_amount") or recommendation.get("award_amount") or "غير محدد"

        if is_judgement:
            header_ar = "📋 ملخص منطوق الحكم (Final Ruling):"
            header_en = "📋 **Final Court Ruling Summary:**"
            win_rate_ar = f"💡 **حالة القضية:** تم الحكم فيها (منطوق حكم)"
            win_rate_en = f"💡 **Case Status:** Decided Judgment"
        else:
            win_rate = trends.get("plaintiff_win_rate", "N/A")
            header_ar = "[Summary] ملخص التحليل:"
            header_en = "[Summary] **Case Analysis Summary:**"
            win_rate_ar = f"**نسبة فوز المدعي (تاريخياً):** {win_rate}% (بناءً على {sample_size} سوابق قضائية)"
            win_rate_en = f"**Historical Plaintiff Win Rate:** {win_rate}% (Based on {sample_size} local precedents)"

        response_ar = f"""{header_ar}

**نوع القضية:** {clf.get('name_ar', 'N/A')}
{win_rate_ar}
**المبلغ المحكوم به/المطالب به:** {award_amount}

**المبادئ القانونية المطبقة:**
{principles_text_ar}

**التوصية/الخلاصة:**
{rec_text_ar}"""

        response_en = f"""{header_en}

**Case Type:** {clf.get('name_en', 'N/A')}
{win_rate_en}
**Awarded/Claimed Amount:** {award_amount}

**Applicable Legal Principles:**
{principles_text_en}

**Recommendation/Outcome:**
{rec_text_en}"""

        return {
            "text": f"{response_ar}\n\n---\n\n{response_en}",
            "intent": "case_summary",
            "suggested_actions": [
                {"label": "Full Details | عرض التفاصيل الكاملة", "action": "full_analysis"},
                {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"},
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ]
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

        if is_judgement:
            ar_text = f"🔍 تم رصد أن هذه القضية محكومة بالفعل بموجب صك حكم.\n\nنوع القضية المستخلص: **{case_type_ar}**.\n\n**تفاصيل المنطوق:**\n• الحالة: حكم قضائي نافذ\n• مبلغ الإلزام: {analysis.get('entities', {}).get('compensation_amount') or 'راجع المنطوق'}"
            en_text = f"🔍 **This is a Decided Judgment:**\n\nExtracted Case Type: **{case_type_en}**.\n\n**Ruling Details:**\n• Status: Legally Binding Judgment\n• Awarded Amount: {analysis.get('entities', {}).get('compensation_amount') or 'See text'}"
            suggested_actions = [
                {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"},
                {"label": "Enforcement | طلب تنفيذ", "action": "draft_enforcement"}
            ]
        else:
            ar_text = f"🔍 نتائج البحث عن قضايا مشابهة:\n\nلقد وجدنا قضايا مرتبطة بنوع: **{case_type_ar}**. (إجمالي العينة: {sample_size} قضايا)\n\n**الإحصائيات المستخلصة من السوابق:**\n• حالة القضية: {case_status_ar}\n• متوسط التعويض: {ar_comp}"
            en_text = f"🔍 **Similar Case Results:**\n\nWe found precedents related to: **{case_type_en}**. (Total sample: {sample_size} cases)\n\n**Extracted Trend Data:**\n• Case Status: {case_status_en}\n• Average Compensation: {en_comp}"
            suggested_actions = [
                {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"},
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ]

        return {
            "text": f"{ar_text}\n\n---\n\n{en_text}",
            "intent": "similar_cases",
            "suggested_actions": suggested_actions
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
            ]
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
استخدم عملة 'SAR' أو 'ريال سعودي' حصراً. لا تستخدم 'Rs.' أو 'الروبية' أبداً.
نظام العمل السعودي مرجعه (1426هـ / 2005م).

STRICT GROUNDING RULES:
1. لا تقم أبداً باختراع أسماء شركات (مثل BC) أو أشخاص. استخدم "............" للمعلومات الناقصة.
2. التزم بالحقائق المستخلصة من النص المرفق حصراً.
3. إذا كان النص حكماً قضائياً (Judgement)، لا تتحدث عن احتمالات الفوز، بل اشرح للمستخدم أن الحكم صدر لصالحه أو ضده وما هي الخطوات التالية للتنفيذ."""

                if is_judgement:
                    system_prompt += """
السياق الحالي: مرحلة ما بعد الحكم (Post-Judgment).
اشرح للمستخدم ماذا يعني الحكم الصادر وكيف يمكنه التنفيذ عبر ناجز."""
                else:
                    system_prompt += """
السياق الحالي: مرحلة ما قبل التقاضي/نزاع (Pre-litigation).
انصح المستخدم بالأدلة التي يحتاجها لتقوية موقفه."""
                
                # OPTIMIZATION: Structured Prompt + Input Capping
                # 1. Cap case text to avoid 25k char overload
                case_text_from_context = self.context.case_text or ""
                short_case_text = case_text_from_context[:3000]
                
                entities = analysis.get("entities", {})
                
                # 2. Structured Prompt with Fact Injection
                prompt = f"""STRICT GROUNDING TASK:
Case Facts:
- Parties: Plaintiff: {entities.get('plaintiff', 'Unknown')}, Defendant: {entities.get('defendant', 'Unknown')}
- Case Type: {classification.get('name_en', 'N/A')}
- Award/Amount: {entities.get('compensation_amount') or recommendation.get('award_amount', 'N/A')}
- Is Final Judgment: {is_judgement}

Document Content:
{short_case_text}

Task: Provide clear legal advice based ONLY on these facts.
Format: Arabic first, then English.
"""
                generated_rec = await self.llm.generate(prompt, system_prompt=system_prompt, max_new_tokens=400)
                
                # Filtering common hallucinated placeholders
                generated_rec = generated_rec.replace("Company BC", "............").replace("BC Company", "............")

                suggested_actions = [
                    {"label": "Similar Cases | قضايا مشابهة", "action": "similar_cases"},
                    {"label": "Full Analysis | تحليل شامل", "action": "full_analysis"}
                ]
                
                # Filter out Claim action if already judged
                if not is_judgement:
                     suggested_actions.append({"label": "Draft Claim | كتابة لائحة دعوى", "action": "draft_claim"})

                return {
                    "text": generated_rec,
                    "intent": "recommendation",
                    "suggested_actions": suggested_actions
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
            "suggested_actions": suggested_actions
        }
    
    # --- STATIC LEGAL TEMPLATES ---
    CLAIM_TEMPLATE = """[Draft] **مسودة لائحة دعوى:**

إلى محكمة: {court_name}
موضوع الدعوى: {case_type}

1. الأطراف:
   - المدعي: {plaintiff}
   - المدعى عليه: {defendant}

2. وقائع الدعوى:
{facts_summary}

3. الأسانيد النظامية والشرعية:
{legal_basis}

4. الطلبات:
   - إلزام المدعى عليه بدفع مبلغ ({amount}) ريال سعودي.
   - إلزام المدعى عليه بكافة المصاريف القضائية.

---
[Draft] **Plaintiff Claim Draft:**

1. Parties:
   - Plaintiff: {plaintiff}
   - Defendant: {defendant}

2. Factual Summary:
{facts_summary_en}

3. Legal Grounds:
{legal_basis_en}"""

    DEFENSE_TEMPLATE = """[Draft] **مذكرة دفاع:**

إلى محكمة: {court_name}

1. الأطراف:
   - المدعي: {plaintiff}
   - المدعى عليه: {defendant}
"""

2. ملخص الرد:
{facts_summary}

3. الدفوع:
{legal_basis}

4. الطلبات:
   - رد الدعوى لعدم الصحة."""

    APPEAL_TEMPLATE = """[Draft] **مذكرة اعتراض:**

1. وقائع القضية:
{facts_summary}

2. أسباب الاعتراض:
{legal_basis}

3. الطلبات:
   - قبول الاعتراض شكلاً وموضوعاً."""

    ENFORCEMENT_TEMPLATE = """[Draft] **طلب تنفيذ:**

1. طالب التنفيذ: {plaintiff}
2. المنفذ ضده: {defendant}
"""

3. ملخص المستحقات:
{facts_summary}

4. الطلبات:
   - إلزام المنفذ ضده بدفع مبلغ ({amount}) ريال سعودي."""

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
                # OPTIMIZATION: Cap input
                short_case_text = case_text[:3000]
                
                target_prompt = f"""STRICT GROUNDING TASK:
Draft facts and legal grounds for a '{case_type_ar}' claim.
CASE CONTEXT (TRUNCATED): {short_case_text}
CLAIM AMOUNT: {amount} SAR
ROLES: Plaintiff (Claimant), Defendant (Respondent).

STRICT INSTRUCTIONS:
- Use ONLY facts from the provided text. NEVER invent names. Use "............" if missing.
- Use currency 'SAR' or 'Saudi Riyals' only.
- Saudi Labor Law is (1246H / 2005G).
- Output format:
1. ملخص الوقائع: [Arabic text]
2. الأسانيد: [Arabic text]"""
                
                ai_output = await self.llm.generate(target_prompt, system_prompt=f"أنت خبير صياغة لوائح دعوى سعودي. السياق الأنظمة: {legal_context}", max_new_tokens=500)
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
            court_name="المحكمة العمالية" if "عمالي" in case_type_ar else "المحكمة العامة", 
            case_type=case_type_ar, 
            plaintiff=analysis.get("entities", {}).get("plaintiff") or "............",
            defendant=analysis.get("entities", {}).get("defendant") or "............",
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
                # OPTIMIZATION: Cap input
                short_case_text = case_text[:3000]

                target_prompt = f"""STRICT GROUNDING TASK:
Draft a defense response for a '{case_type_ar}' case.
CASE CONTEXT (TRUNCATED): {short_case_text}
ROLES: Plaintiff (Opponent), Defendant (Client).

STRICT INSTRUCTIONS:
- Use ONLY the provided text to build defenses.
- Use currency 'SAR' or 'Saudi Riyals' only.
- Output format:
1. ملخص الرد: [Arabic text]
2. الدفوع: [Arabic text]"""
                
                ai_output = await self.llm.generate(target_prompt, system_prompt=f"أنت محامي دفاع سعودي. السياق الأنظمة: {legal_context}", max_new_tokens=500)
                ai_output = self._clean_draft(ai_output, {"amount": amount})
                # Global Currency Scrub
                ai_output = ai_output.replace("Rs.", "SAR").replace("rupees", "SAR").replace("Rupees", "SAR")

                if "1." in ai_output and "2." in ai_output:
                    parts = ai_output.split("2.")
                    facts_summary = parts[0].replace("1.", "").replace("ملخص الرد:", "").strip()
                    legal_basis = parts[1].replace("الدفوع:", "").strip()
            except: pass

        final_text = self.DEFENSE_TEMPLATE.format(
            court_name="المحكمة العامة", 
            plaintiff=analysis.get("entities", {}).get("plaintiff") or "............",
            defendant=analysis.get("entities", {}).get("defendant") or "............",
            facts_summary=facts_summary, 
            legal_basis=legal_basis
        )
        return {
            "text": final_text, 
            "intent": "draft_defense", 
            "metadata": {"is_draft": True},
            "suggested_actions": [
                {"label": "Draft Claim | لائحة دعوى", "action": "draft_claim"}, 
                {"label": "Recommendations | التوصيات", "action": "recommendations"}
            ]
        }

    async def _handle_draft_enforcement(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Generate an enforcement petition (Structured Grounding)."""
        entities = analysis.get("entities", {})
        recommendation = analysis.get("recommendation", {})
        amount = entities.get("compensation_amount") or recommendation.get("award_amount") or "............"
        
        final_text = self.ENFORCEMENT_TEMPLATE.format(
            plaintiff=entities.get("plaintiff") or "............",
            defendant=entities.get("defendant") or "............",
            amount=amount, 
            facts_summary="بناءً على منطوق الحكم القاضي بإلزام المنفذ ضده بدفع المبلغ المذكور."
        )
        return {
            "text": final_text, 
            "intent": "draft_enforcement", 
            "metadata": {"is_draft": True},
            "suggested_actions": [{"label": "Appeal Memo | مذكرة اعتراض", "action": "draft_appeal"}]
        }

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
        return {"text": f"نسبة فوز المدعي التقريبية: {win_rate}%", "intent": "outcome"}

    async def _handle_compensation(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond about compensation information."""
        trends = analysis.get("trends", {})
        return {"text": f"المعدل التاريخي للتعويضات: {trends.get('average_compensation', 0)} ر.س", "intent": "compensation"}

    async def _handle_entities(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Respond about extracted entities."""
        entities = analysis.get("entities", {})
        entities_list = "\n".join([f"• {e}: {v}" for e, v in entities.items()])
        return {"text": f"الأطراف المكتشفة:\n{entities_list}", "intent": "entities"}

    async def _handle_general_inquiry(self, query: str, analysis: Dict) -> Dict[str, Any]:
        """Handle general inquiries."""
        if self.llm and analysis:
            try:
                res = await self.llm.generate(f"بيانات: {json.dumps(analysis, ensure_ascii=False)}\nسؤال: {query}", system_prompt="أنت مساعد قانوني.")
                return {"text": res, "intent": "general_inquiry"}
            except: pass
        return {"text": "أنا هنا لمساعدتك في تحليل القضايا القانونية السعودية.", "intent": "general_inquiry"}

    def get_conversation_history(self) -> List[Dict]:
        return self.context.get_last_n_messages(20)

    def clear_conversation(self):
        self.context.clear()

    def get_context_summary(self) -> Dict:
        return {
            "has_analysis": self.context.analysis_data is not None,
            "message_count": len(self.context.messages)
        }
