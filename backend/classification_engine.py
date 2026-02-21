"""
Case Type Classification Engine for Arabic Legal Cases.

Upgraded to use Embedding-Based Classification (Semantic Similarity)
while retaining keyword matching for explainability.
"""

import re
from typing import Dict, List, Any
from sentence_transformers import util
import torch
import logging

logger = logging.getLogger(__name__)

# ── Case Type Definitions & Semantic Anchors ───────────────────────────

CASE_TYPES = {
    "contract_dispute": {
        "name_ar": "نزاع عقدي",
        "name_en": "Contract Dispute",
        "anchor": "نزاع حول تنفيذ عقد بين مقاول وصاحب عمل، أو عقد خدمات، مقاولة، صيانة، إصلاح، تركيب.",
        "keywords": [
            "مقاول", "صاحب عمل", "مقاولة",
            "صيانة", "إصلاح", "تركيب", "تطوير", 
            "مشروع", "أعمال", "حسب العقد",
            "فسخ العقد", "إنهاء العقد", "مخالفة العقد",
            "إخلال بالتزامات", "عدم التنفيذ"
        ]
    },
    "labor_dispute": {
        "name_ar": "نزاع عمالي",
        "name_en": "Labor Dispute",
        "anchor": "نزاع عمالي بين عامل وصاحب عمل، فصل تعسفي، مطالبات بالرواتب المتأخرة، مكافأة نهاية الخدمة، بدلات، إجازات، حقوق وظيفية.",
        "keywords": [
            "عامل", "عمال", "موظف", "راتب", "رواتب",
            "فصل تعسفي", "إنهاء خدمات", "مكافأة نهاية الخدمة",
            "نظام العمل", "عقد العمل", "ساعات العمل",
            "إجازة", "تأمينات", "كفالة", "نقل كفالة"
        ]
    },
    "traffic_accident": {
        "name_ar": "حادث مروري",
        "name_en": "Traffic Accident",
        "anchor": "حادث مروري، تصادم سيارات، أضرار في المركبات، دية، أرش إصابة، تعويض عن حادث سير، تقرير المرور ومسؤولية الحادث.",
        "keywords": [
            "حادث", "مروري", "سيارة", "مركبة", "قيادة",
            "تصادم", "إصابة", "وفاة", "مرور", "رخصة قيادة",
            "تأمين المركبة", "إتلاف", "حوادث السير"
        ]
    },
    "commercial_dispute": {
        "name_ar": "نزاع تجاري",
        "name_en": "Commercial Dispute",
        "anchor": "نزاع تجاري بين شركات أو تجار، معاملات تجارية، أوراق تجارية، شيكات، كمبيالات، سندات لأمر، منازعات بنكية، توريد بضائع.",
        "keywords": [
            "تجاري", "تجارية", "شركة", "سجل تجاري",
            "فاتورة", "فواتير", "بيع", "شراء", "سداد",
            "مبلغ", "ريال", "دفع", "مستحقات", "مديونية",
            "التجارية", "الدائرة التجارية",
            "كمبيالة", "سند لأمر", "شيك",
            "بضاعة", "بضائع", "سلعة", "سلع", "مواد",
            "الموردة", "موردة", "المشتري", "مشتري", "الطرف الثاني",
            "المتأخرات", "السداد"
        ]
    },
    "property_dispute": {
        "name_ar": "نزاع عقاري",
        "name_en": "Property Dispute",
        "anchor": "نزاع عقاري، ملكية أرض أو عقار، إيجار، إخلاء عقار، تداخل حدود، صكوك ملكية، تعدي على عقار، مطالبة بأجرة.",
        "keywords": [
            "عقار", "عقارات", "أرض", "مبنى", "شقة",
            "إيجار", "تأجير", "مستأجر", "مؤجر",
            "إخلاء", "صك", "ملكية", "بيع عقار"
        ]
    },
    "partnership": {
        "name_ar": "مضاربة / شراكة",
        "name_en": "Partnership / Mudharaba",
        "anchor": "نزاع شراكة، عقد مضاربة، توزيع أرباح وخسائر، تصفية شركة، محاسبة بين الشركاء، رأس المال، حصص الشركاء.",
        "keywords": [
            "شراكة", "شريك", "مضاربة", "رأس المال",
            "حصة", "أرباح", "خسائر", "توزيع الأرباح",
            "شركة مضاربة", "رأس مال"
        ]
    },
    "compensation": {
        "name_ar": "تعويض",
        "name_en": "Compensation Claim",
        "anchor": "مطالبة بالتعويض عن ضرر مادي أو معنوي، مسؤولية تقصيرية، فعل ضار، تعويض عن إتلاف ممتلكات، جبر الضرر.",
        "keywords": [
            "تعويض", "ضرر", "أضرار", "تعويض عن",
            "جبر الضرر", "المسؤولية المدنية", "إتلاف"
        ]
    },
    "jurisdictional": {
        "name_ar": "اختصاص قضائي",
        "name_en": "Jurisdictional",
        "anchor": "دفع بعدم الاختصاص النوعي أو المكاني للمحكمة، ولاية قضائية، إحالة الدعوى لمحكمة مختصة.",
        "keywords": [
            "اختصاص", "عدم اختصاص", "الولاية القضائية", "الاختصاص القضائي",
            "إحالة", "المحكمة المختصة", "اختصاص نوعي", "اختصاص مكاني",
            "دفع بعدم الاختصاص", "عدم اختصاص المحكمة", "محكمة غير مختصة"
        ]
    }
}

class ClassificationEngine:
    def __init__(self, embedding_model=None):
        """
        Initialize the Classification Engine.
        :param embedding_model: Instance of SentenceTransformer (shared from SimilarityEngine)
        """
        self.model = embedding_model
        self.anchor_embeddings = {}
        self.initialized = False
        self.confidence_threshold = 0.6  # Minimum confidence to accept classification
        
        if self.model:
            self._init_embeddings()

    def set_model(self, embedding_model):
        """Set model lazily if not provided at init."""
        self.model = embedding_model
        self._init_embeddings()

    def _init_embeddings(self):
        """Pre-compute embeddings for all semantic anchors."""
        logger.info("[CLASSIFY_INIT] Initializing Classification Semantic Anchors...")
        try:
            for key, data in CASE_TYPES.items():
                # Encode the anchor text
                emb = self.model.encode(data["anchor"], convert_to_tensor=True)
                self.anchor_embeddings[key] = emb
                logger.debug(f"[CLASSIFY_INIT] Encoded anchor for {key}")
            
            self.initialized = True
            logger.info(f"[CLASSIFY_INIT_SUCCESS] Initialized {len(CASE_TYPES)} classification anchors")
        except Exception as e:
            logger.error(f"[CLASSIFY_INIT_ERROR] Failed to initialize: {e}", exc_info=True)

    def classify_case(self, text: str) -> Dict[str, Any]:
        """
        Classify a legal case using a Hybrid Approach with improved logging:
        1. Semantic Similarity (Primary) - using embeddings
        2. Keyword Matching (Secondary/Explainability) - for transparency
        """
        text = text.strip()
        if not text:
            logger.warning("[CLASSIFY] Empty text provided")
            return self._return_unknown()

        logger.info(f"[CLASSIFY_START] Classifying case (text length: {len(text)} chars)")

        # 1. Semantic Score (if model is loaded)
        semantic_scores = {}
        if self.initialized and self.model:
            try:
                logger.debug(f"[CLASSIFY_SEMANTIC] Computing semantic similarity scores")
                # Encode input text (truncate to first 1000 chars for efficiency)
                input_emb = self.model.encode(text[:1000], convert_to_tensor=True)
                
                for key, anchor_emb in self.anchor_embeddings.items():
                    # Compute Cosine Similarity
                    score = util.cos_sim(input_emb, anchor_emb).item()
                    semantic_scores[key] = max(0, score)  # Ensure non-negative
                    logger.debug(f"[CLASSIFY_SEMANTIC] {key}: {score:.4f}")
            except Exception as e:
                logger.warning(f"[CLASSIFY_SEMANTIC_ERROR] Semantic classification failed: {e}")

        # 2. Keyword Score (Fallback & Explainability)
        logger.debug(f"[CLASSIFY_KEYWORDS] Computing keyword match scores")
        keyword_scores = {}
        matched_keywords_map = {}
        
        text_lower = text.lower()
        for key, data in CASE_TYPES.items():
            k_score = 0
            matched = []
            for kw in data["keywords"]:
                if kw in text_lower:
                    k_score += 1
                    matched.append(kw)
            
            # Normalize keyword score
            keyword_scores[key] = min(k_score / 5.0, 1.0) if k_score > 0 else 0.0
            matched_keywords_map[key] = matched
            
            if matched:
                logger.debug(f"[CLASSIFY_KEYWORDS] {key}: {k_score} keywords found")

        # 3. Hybrid Combination
        logger.debug(f"[CLASSIFY_COMBINE] Combining semantic and keyword scores")
        final_scores = {}
        alpha = 0.7 if self.initialized else 0.0  # Weight for Semantic Score
        beta = 1.0 - alpha                        # Weight for Keyword Score
        
        for key in CASE_TYPES.keys():
            s_score = semantic_scores.get(key, 0.0)
            k_score = keyword_scores.get(key, 0.0)
            
            # Boost: If semantic is high (>0.4) and keywords match, boost score
            boost = 1.1 if (s_score > 0.4 and k_score > 0.2) else 1.0
            
            final_score = (s_score * alpha + k_score * beta) * boost
            final_scores[key] = final_score
            logger.debug(f"[CLASSIFY_COMBINE] {key}: semantic={s_score:.3f}, keyword={k_score:.3f}, final={final_score:.3f}")

        # Sort results
        ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_type = ranked[0][0]
        primary_score = ranked[0][1]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        
        logger.debug(f"[CLASSIFY_RANKED] Top result: {primary_type} (score: {primary_score:.4f})")

        # Check if score is too low
        if primary_score < 0.15:
            logger.warning(f"[CLASSIFY_LOW_SCORE] Primary score {primary_score:.4f} below threshold")
            return self._return_unknown()

        # Improved Confidence Calculation
        # Raw score range: 0.0-1.0
        # We want: confidence that represents actual correctness
        if self.initialized:
            # Use difference between top and second for discrimination
            discrimination = primary_score - second_score
            # Confidence = primary_score * discrimination_bonus
            # If close to second place, lower confidence
            discrimination_bonus = 1.0 + (discrimination * 2.0)  # Boost if clearly winning
            display_confidence = min(primary_score * discrimination_bonus, 0.99)
            display_confidence = max(display_confidence, 0.4)  # Floor at 40%
        else:
            display_confidence = min(primary_score, 0.95)
        
        display_confidence = round(display_confidence, 2)
        logger.info(f"[CLASSIFY_CONFIDENCE] Calculated confidence: {display_confidence:.2%}")

        # Secondary types
        sub_types = []
        for t_key, t_score in ranked[1:4]:
            if t_score > 0 and t_score > primary_score * 0.5:
                sub_types.append({
                    "case_type": t_key,
                    "name_ar": CASE_TYPES[t_key]["name_ar"],
                    "name_en": CASE_TYPES[t_key]["name_en"],
                    "relevance": round(t_score, 2)
                })

        logger.info(f"[CLASSIFY_COMPLETE] Classified as {primary_type} with confidence {display_confidence:.2%}")

        return {
            "case_type": primary_type,
            "name_ar": CASE_TYPES[primary_type]["name_ar"],
            "name_en": CASE_TYPES[primary_type]["name_en"],
            "confidence": display_confidence,
            "matched_keywords": matched_keywords_map.get(primary_type, []),
            "sub_types": sub_types,
            "raw_score": round(primary_score, 4)  # For debugging
        }

    def _return_unknown(self):
        logger.debug("[CLASSIFY] Returning unknown classification")
        return {
            "case_type": "unknown",
            "name_ar": "غير محدد",
            "name_en": "Unknown",
            "confidence": 0.0,
            "matched_keywords": [],
            "sub_types": []
        }

# Global instance for backward compatibility (initially empty)
# This will be properly initialized in main.py
classifier = ClassificationEngine()

# Backward compatible function wrapper
def classify_case(text: str) -> Dict:
    return classifier.classify_case(text)
