"""
Document Stage Detection Engine
Detects the legal process stage of a document (claim, defense, judgment, appeal, etc.)
Required for Issue 3: Intent Detection Failure
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class DocumentStage(Enum):
    """Possible document stages in legal process"""
    CLAIM = "claim"
    DEFENSE = "defense"
    JUDGMENT = "judgment"
    APPEAL = "appeal"
    EVIDENCE = "evidence"
    HEARING = "hearing"
    ENFORCEMENT = "enforcement"
    UNKNOWN = "unknown"


class DocumentStageDetector:
    """Detects the stage/type of legal document to enable stage-aware analysis."""
    
    def __init__(self):
        """Initialize stage detector with indicators."""
        self.stage_indicators = self._initialize_indicators()
        logger.info("[STAGE_INIT] Document Stage Detector initialized")
    
    def _initialize_indicators(self) -> Dict[DocumentStage, Dict]:
        """Initialize keywords and patterns for each document stage."""
        return {
            DocumentStage.CLAIM: {
                "name_ar": "دعوى/شكوى",
                "name_en": "Claim/Petition",
                "keywords": [
                    "دعوى", "شكوى", "عريضة", "المدعي", "يطالب", "المطالبة", "يسأل",
                    "يطلب", "الطلب", "الدعوى", "الشكوى", "رفع دعوى", "تقديم شكوى",
                    "التماس", "التماس قضائي", "الالتماس", "المقدمة",
                    "claim", "petition", "complaint", "plaintiff", "seek", "request",
                    "تقدم الشاكية", "يرفع المدعي", "المشكو بحقه", "طالبة", "يمثل"
                ],
                "patterns": [
                    r"(?:يرفع|تقدم|يسأل|يطلب|تقديم) .*? (?:دعوى|شكوى|عريضة)",
                    r"(?:المدعي|الشاكي) (?:يطلب|يسأل|يطالب|تقدم)",
                    r"(?:is|are) (?:filing|submitting) .*? (?:claim|petition|complaint)",
                ],
                "negative_keywords": ["الحكم رقم", "قضت المحكمة", "قررت المحكمة", "حكمت"],
                "description": "Initial legal claim or petition"
            },
            DocumentStage.DEFENSE: {
                "name_ar": "جواب/رد",
                "name_en": "Defense/Response",
                "keywords": [
                    "الدفع", "جواب", "دفاع", "ينفي", "ينكر", "يعترض", "المدعى عليه",
                    "يرد", "الرد", "الاعتراض", "بالاعتراض", "بالدفع", "الدفاع",
                    "defense", "response", "deny", "object", "defendant", "opposes", "rejects",
                    "جواب الدعوى", "رد المدعى عليه", "أوجه الدفع", "يدفع", "ينفي"
                ],
                "patterns": [
                    r"(?:جواب|رد) (?:الدعوى|المدعى عليه|الدفاع)",
                    r"(?:المدعى عليه|المشكو بحقه|ترد) (?:يدفع|ينفي|ينكر|يعترض|تدفع)",
                    r"(?:defendant|respondent) (?:denies|opposes|rejects)",
                    r"(?:بدفع|رد على|اعتراض على|جواب)",
                ],
                "negative_keywords": ["الحكم رقم", "قضت المحكمة", "حكمت", "الاستئناف رقم"],
                "description": "Response or defense to a claim"
            },
            DocumentStage.JUDGMENT: {
                "name_ar": "حكم/قرار",
                "name_en": "Judgment/Ruling",
                "keywords": [
                    "الحكم", "القرار", "حكمت", "قضت", "الأحكام", "قضاء", "قضائي",
                    "قررت", "تقرر", "يقرر", "تقضي", "تقضى", "اقضى", "المحكمة",
                    "القاضي", "الحاكم", "راسل", "رسل القضية",
                    "judgment", "ruling", "decision", "court finds", "hereby orders", "adjudged"
                ],
                "patterns": [
                    r"(?:قضت|حكمت|قررت|تقضي) المحكمة",
                    r"(?:أحكام بـ|الحكم بـ|القرار بـ|قرار بـ)",
                    r"(?:الحكم النهائي|الحكم الصادر|قرار)",
                    r"(?:hereby )?(?:orders|adjudges|rules)",
                    r"judgment (?:is )?(?:rendered|entered)",
                ],
                "positive_keywords": ["الرسم", "الصادر", "النهائي", "رقم الحكم"],
                "description": "Court judgment or final ruling"
            },
            DocumentStage.APPEAL: {
                "name_ar": "استئناف/تمييز",
                "name_en": "Appeal",
                "keywords": [
                    "استئناف", "استأنف", "الاستئناف", "تمييز", "الطعن", "طاعن",
                    "معترض", "اعتراض", "الاستشكال", "النقض", "الطعن بالنقض",
                    "appeal", "appellate", "appellant", "appealing", "reverse", "remand",
                    "يستأنف", "استأنفت", "الاستئناف في", "على حكم", "ضد الحكم"
                ],
                "patterns": [
                    r"استئناف رقم",
                    r"(?:يستأنف|استأنفت|الاستئناف) (?:في|على|ضد|من)",
                    r"(?:ضد )?(?:الحكم|القرار) رقم",
                    r"(?:appeals? to|appealing to|appeals? from)",
                    r"(?:grounds for appeal|appellate review|appeal of)",
                ],
                "positive_keywords": ["ضد", "ضد الحكم", "ضد القرار", "يستأنف الحكم"],
                "requires_prior_judgment": True,
                "description": "Appeal or challenge to prior judgment"
            },
            DocumentStage.EVIDENCE: {
                "name_ar": "وثيقة/مرفق",
                "name_en": "Evidence/Exhibit",
                "keywords": [
                    "وثيقة", "وثائق", "مرفق", "مرفقات", "محرر", "محررات", "مستند",
                    "مستندات", "إثبات", "إثباتات", "ملحق", "ملحقات",
                    "exhibit", "evidence", "document", "attachment", "proof"
                ],
                "patterns": [
                    r"(?:وثيقة|مرفق|محرر|مستند) رقم",
                    r"(?:attached|filed) (?:as )?(?:exhibit|evidence)",
                ],
                "is_supporting_document": True,
                "description": "Supporting document or evidence"
            },
            DocumentStage.HEARING: {
                "name_ar": "جلسة/محاضر",
                "name_en": "Hearing/Proceedings",
                "keywords": [
                    "جلسة", "جلسات", "محضر", "الجلسة", "حضر", "حاضر", "الحضور",
                    "جلس", "انعقدت", "انقسم", "معاد", "إعادة",
                    "hearing", "session", "proceedings", "attended", "present"
                ],
                "patterns": [
                    r"(?:جلسة|محضر) (?:رقم|تاريخ)",
                    r"(?:في الجلسة|محضر الجلسة)",
                ],
                "description": "Court hearing or session record"
            },
            DocumentStage.ENFORCEMENT: {
                "name_ar": "تنفيذ",
                "name_en": "Enforcement",
                "keywords": [
                    "تنفيذ", "التنفيذ", "منفذ", "المنفذ", "نفاذ", "نافذ", "إجراء",
                    "enforcement", "execute", "execution", "enforce"
                ],
                "patterns": [
                    r"(?:تنفيذ|التنفيذ) (?:الحكم|القرار)",
                    r"(?:دعوى|طلب) (?:تنفيذ|التنفيذ)",
                ],
                "description": "Enforcement of judgment"
            },
            DocumentStage.UNKNOWN: {
                "name_ar": "غير محدد",
                "name_en": "Unknown",
                "keywords": [],
                "description": "Document stage cannot be determined"
            }
        }
    
    def detect_stage(self, document_text: str) -> Dict[str, Any]:
        """
        Detect the stage of a legal document.
        
        Args:
            document_text: The text of the legal document
            
        Returns:
            Dict with stage, confidence, indicators, etc.
        """
        try:
            logger.info(f"[STAGE_DETECT_START] Starting document stage detection (length: {len(document_text)})")
            
            # Validation
            if not document_text or len(document_text.strip()) < 100:
                logger.warning("[STAGE_DETECT] Document too short for reliable detection")
                return self._return_unknown("Document too short for reliable detection")
            
            text_lower = document_text.lower()
            
            # Score each stage
            scores = {}
            indicators = {}
            
            for stage, stage_config in self.stage_indicators.items():
                if stage == DocumentStage.UNKNOWN:
                    continue
                
                score = 0
                found_indicators = []
                
                # Check keywords
                for keyword in stage_config["keywords"]:
                    if keyword in text_lower:
                        occurrences = text_lower.count(keyword)
                        score += occurrences * 2  # Weight keywords at 2 points each
                        found_indicators.append(f"{keyword} (×{occurrences})")
                
                # Check patterns with higher weight
                for pattern in stage_config.get("patterns", []):
                    matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                    if matches > 0:
                        score += matches * 3  # Patterns worth 3 points each
                        found_indicators.append(f"pattern: {pattern[:35]}... (×{matches})")
                
                # Negative keywords (reduce score)
                for neg_kw in stage_config.get("negative_keywords", []):
                    if neg_kw in text_lower:
                        score = max(0, score - 5)  # Penalty for conflicting keywords
                        found_indicators.append(f"negative: {neg_kw}")
                
                scores[stage] = score
                indicators[stage.value] = found_indicators
                
                logger.debug(f"[STAGE_SCORE] {stage.value}: score={score}, indicators={len(found_indicators)}")
            
            # Find highest scoring stage
            if not scores or max(scores.values()) == 0:
                logger.warning("[STAGE_DETECT] No indicators found, returning UNKNOWN")
                return self._return_unknown("No stage indicators detected in document")
            
            max_stage = max(scores, key=scores.get)
            max_score = scores[max_stage]
            
            # Calculate confidence (normalized to 0-1)
            total_score = sum(scores.values())
            confidence = max_score / total_score if total_score > 0 else 0
            confidence = min(confidence, 0.99)  # Cap at 99%
            confidence = max(confidence, 0.4)   # Floor at 40%
            
            logger.info(f"[STAGE_RESULT] Detected: {max_stage.value} (confidence={confidence:.1%})")
            
            # Compile result
            result = {
                "stage": max_stage.value,
                "stage_ar": self.stage_indicators[max_stage]["name_ar"],
                "stage_en": self.stage_indicators[max_stage]["name_en"],
                "confidence": round(confidence, 2),
                "description": self.stage_indicators[max_stage]["description"],
                "indicators": indicators[max_stage.value],
                "all_scores": {stage.value: round(scores[stage], 1) for stage in scores},
            }
            
            if confidence < 0.6:
                result["warning"] = "Low confidence - consider manual review"
                logger.warning(f"[STAGE_WARNING] Low confidence ({confidence:.1%}) for {max_stage.value}")
            
            return result
            
        except Exception as e:
            logger.error(f"[STAGE_ERROR] Exception during stage detection: {e}", exc_info=True)
            return self._return_unknown(str(e))
    
    def _return_unknown(self, warning_msg: str = None) -> Dict[str, Any]:
        """Return unknown stage result."""
        return {
            "stage": DocumentStage.UNKNOWN.value,
            "stage_ar": "غير محدد",
            "stage_en": "Unknown",
            "confidence": 0.0,
            "description": "Document stage cannot be determined",
            "indicators": [],
            "warning": warning_msg or "Unable to determine document stage"
        }
    
    def get_analysis_prompt_for_stage(self, stage: str) -> str:
        """
        Get LLM prompt template based on document stage.
        This enables stage-aware analysis with appropriate context.
        """
        prompts = {
            DocumentStage.CLAIM.value: """
هذه وثيقة دعوى/شكوى أولية. حلل الوثيقة:
1. ما هي المطالبات الرئيسية للمدعي؟
2. ما التعويض أو الإجراء المطلوب؟
3. ما الأساس القانوني للمطالبات؟
4. ما الأدلة المسندة للمطالبات؟

ملاحظة: هذه دعوى أولية وليست قرار نهائي. عبّر عن المطالبات بحذر.
""",
            DocumentStage.DEFENSE.value: """
هذه وثيقة دفاع/رد على الدعوى. حلل الوثيقة:
1. ما الادعاءات التي ينكرها المدعى عليه؟
2. ما حجج الدفاع المقدمة؟
3. ما الأدلة المسندة للدفاع؟
4. هل هناك ادعاءات مقابلة؟

ملاحظة: هذا رد على مطالبات، لا يمثل القرار النهائي.
""",
            DocumentStage.JUDGMENT.value: """
هذه وثيقة حكم/قرار محكمة نهائي. حلل الوثيقة:
1. ما هو قرار المحكمة النهائي؟
2. ما أسباب الحكم والتبريرات القانونية؟
3. من انتصر وما التعويضات المقررة؟
4. هل هناك شروط أو آليات لتنفيذ الحكم؟

ملاحظة: هذا حكم نهائي. قدّم معلومات عن التنفيذ والطعن إن وجد.
""",
            DocumentStage.APPEAL.value: """
هذه وثيقة استئناف/طعن في حكم سابق. حلل الوثيقة:
1. ما الحكم الأصلي موضوع الاستئناف؟
2. ما أسباب وأساس الاستئناف؟
3. ما الأخطاء القانونية المدعاة؟
4. ما التعويض المطلوب من محكمة الاستئناف؟

ملاحظة: هذا استئناف لحكم سابق. اذكر آليات الطعن المتاحة.
""",
            DocumentStage.EVIDENCE.value: """
هذه وثيقة إثبات/مرفق داعم. حلل الوثيقة:
1. ما نوع الدليل/الوثيقة؟
2. كيف يدعم هذا الدليل الحالة؟
3. ما مصدر الدليل وحالته؟

ملاحظة: هذه وثيقة داعمة فقط، لا تمثل الموضوع الأساسي.
""",
            DocumentStage.UNKNOWN.value: """
حلل هذه الوثيقة القانونية:
1. ما نوع الوثيقة (دعوى، دفاع، حكم، إلخ)؟
2. في أي مرحلة إجرائية نحن؟
3. ما المسائل القانونية الرئيسية؟
4. ما الحالة الحالية أو الطلب؟
"""
        }
        
        return prompts.get(stage, prompts[DocumentStage.UNKNOWN.value])
    
    def get_arabics_keywords(self) -> Dict[str, List[str]]:
        """Get Arabic keywords for each stage for reference/testing."""
        result = {}
        for stage, config in self.stage_indicators.items():
            if stage != DocumentStage.UNKNOWN:
                # Extract Arabic keywords (non-English ones)
                arabic_keywords = [kw for kw in config["keywords"] if self._is_arabic(kw)]
                if arabic_keywords:
                    result[stage.value] = arabic_keywords
        return result
    
    @staticmethod
    def _is_arabic(text: str) -> bool:
        """Check if text contains Arabic characters."""
        return any('\u0600' <= char <= '\u06FF' for char in text)


# Global instance
stage_detector = DocumentStageDetector()
