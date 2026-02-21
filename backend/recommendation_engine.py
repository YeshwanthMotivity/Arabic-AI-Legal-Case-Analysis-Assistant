"""
Recommendation Engine for Arabic Legal Cases.

Generates probabilistic judicial recommendations based on:
- Trend analysis from similar cases
- Case classification
- Identified legal principles

Confidence is adjusted by sample size using log-scaling
per user feedback: confidence = win_rate * log2(sample_size + 1) / 10

Always includes judicial disclaimer.
"""

import math
from typing import Dict, List, Optional

MIN_SAMPLE_FOR_STATS = 5


# ── Judicial Disclaimer ────────────────────────────────────────────────

DISCLAIMER_AR = "️ هذا تحليل دعم القرار وليس حكماً قضائياً ملزماً. القرار النهائي يعود للقاضي المختص."
DISCLAIMER_EN = "️ This is decision support analysis, not a binding judicial ruling. Final decision rests with the presiding judge."


def generate_recommendation(
    trends: Dict,
    classification: Dict,
    principles: List[Dict],
    entities: Dict = None
) -> Dict:
    """
    Generate a probabilistic recommendation based on analysis.
    """
    sample_size = trends.get("sample_size", 0)
    win_rate = trends.get("plaintiff_win_rate", 0)
    reliability = trends.get("reliability", "insufficient")
    avg_comp = trends.get("average_compensation", 0)
    compensation_count = trends.get("compensation_count", 0)
    decided = trends.get("decided_cases", 0)
    
    doc_type = entities.get("doc_type") if entities else None
    
    # ── Confidence calculation (log-adjusted per user feedback) ─────
    if sample_size > 0 and decided > 0:
        log_factor = math.log2(sample_size + 1) / math.log2(21)
        raw_confidence = (win_rate / 100) * log_factor
        confidence = round(min(raw_confidence, 0.95), 2)
    else:
        confidence = 0.0
    
    # ── Generate recommendation text ───────────────────────────────
    recommendation_ar = ""
    recommendation_en = ""
    direction = "neutral"
    
    # OVERRIDE: If this is an already decided judgment, the recommendation 
    # should reflect the reality of the document, not just averages.
    if doc_type == "judgement":
        confidence = 0.99
        direction = "decided_judgement"
        recommendation_ar = "️ تم رصد أن هذه الوثيقة هي 'حكم قضائي' بالفعل. التحليل يشير إلى ثبوت الحق للمدعي (في حال الإلزام) أو رفض الدعوى."
        recommendation_en = "️ This document is detected as an existing 'Judgement'. The recommendation reflects the legal finality of the document."
        
        # If we have extracted compensation, mention it
        if entities.get("compensation_amount"):
            amount = entities.get("compensation_amount")
            recommendation_ar += f"\nمبلغ التعويض المحكوم به: {amount}."
            recommendation_en += f"\nAwarded compensation amount: {amount}."
        
        return {
            "recommendation_ar": recommendation_ar,
            "recommendation_en": recommendation_en,
            "direction": direction,
            "confidence": confidence,
            "disclaimer_ar": DISCLAIMER_AR,
            "disclaimer_en": DISCLAIMER_EN,
            "supporting_principles": principles[:3] if principles else [],
            "based_on_sample_size": sample_size,
            "reliability": "document_final"
        }

    if reliability == "insufficient" or sample_size < MIN_SAMPLE_FOR_STATS:
        recommendation_ar = "لا توجد سوابق كافية لتقديم توصية. يُنصح بالبحث في قواعد بيانات أوسع."
        recommendation_en = "Insufficient precedent data to provide a recommendation. Broader database search advised."
        direction = "insufficient_data"
        confidence = 0.0
    
    elif win_rate >= 70:
        direction = "plaintiff_likely"
        recommendation_ar = f"بناءً على تحليل {sample_size} قضية مشابهة، يُرجح نجاح المدعي بنسبة {win_rate}%."
        recommendation_en = f"Based on analysis of {sample_size} similar cases, plaintiff success is likely ({win_rate}%)."
        
        if avg_comp > 0 and compensation_count >= MIN_SAMPLE_FOR_STATS:
            recommendation_ar += f"\nمتوسط التعويض في القضايا المماثلة: {avg_comp:,.0f} ريال سعودي."
            recommendation_en += f"\nAverage compensation in similar cases: {avg_comp:,.0f} SAR."
    
    elif win_rate >= 40:
        direction = "uncertain"
        recommendation_ar = f"بناءً على تحليل {sample_size} قضية مشابهة، النتيجة غير مؤكدة (نسبة نجاح المدعي {win_rate}%)."
        recommendation_en = f"Based on analysis of {sample_size} similar cases, outcome is uncertain (plaintiff success rate: {win_rate}%)."
    
    else:
        direction = "defendant_likely"
        recommendation_ar = f"بناءً على تحليل {sample_size} قضية مشابهة، يُرجح رفض الدعوى (نسبة نجاح المدعي {win_rate}% فقط)."
        recommendation_en = f"Based on analysis of {sample_size} similar cases, case dismissal is likely (plaintiff success rate: only {win_rate}%)."
    
    # ── Add supporting principles ──────────────────────────────────
    supporting_principles = []
    if principles:
        top_principles = principles[:3]  # Top 3 most relevant
        for p in top_principles:
            supporting_principles.append({
                "name_ar": p["name_ar"],
                "name_en": p["name_en"],
                "relevance": p["relevance"]
            })
    
    return {
        "recommendation_ar": recommendation_ar,
        "recommendation_en": recommendation_en,
        "direction": direction,
        "confidence": confidence,
        "disclaimer_ar": DISCLAIMER_AR,
        "disclaimer_en": DISCLAIMER_EN,
        "supporting_principles": supporting_principles,
        "based_on_sample_size": sample_size,
        "reliability": reliability
    }


if __name__ == "__main__":
    # Test with mock data
    mock_trends = {
        "outcomes": {"plaintiff_win": 4, "plaintiff_loss": 1, "dismissed": 0},
        "plaintiff_win_rate": 80.0,
        "average_compensation": 115000,
        "sample_size": 5,
        "decided_cases": 5,
        "reliability": "medium"
    }
    
    mock_classification = {
        "case_type": "contract_dispute",
        "name_ar": "نزاع عقدي",
        "confidence": 0.85
    }
    
    mock_principles = [
        {"name_ar": "القوة الملزمة للعقود", "name_en": "Binding Force of Contracts", "relevance": 0.9},
        {"name_ar": "عبء الإثبات", "name_en": "Burden of Proof", "relevance": 0.7}
    ]
    
    result = generate_recommendation(mock_trends, mock_classification, mock_principles)
    print(f"Direction: {result['direction']}")
    print(f"Confidence: {result['confidence']}")
    print(f"AR: {result['recommendation_ar']}")
    print(f"EN: {result['recommendation_en']}")
    print(f"Disclaimer: {result['disclaimer_ar']}")
