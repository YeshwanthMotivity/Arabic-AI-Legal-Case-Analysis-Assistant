"""
Draft Generation Engine for Arabic Legal Documents.

Generates a structured legal draft based on:
1. Case Classification (Type)
2. Extracted Legal Principles (filtered by dispute_type)
3. Analysis Trends (Precedent Win Rates)
4. Recommended Strategy
5. StructuredCase entities from entity_extractor

Uses context-aware principle selection:
  - Labor disputes → only labor law principles
  - Commercial disputes → only commercial principles
  - Generic fallback for unknown types
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ─── COMMERCIAL PRINCIPLE IDS (to filter OUT for labor cases) ─────────
COMMERCIAL_ONLY_PRINCIPLES = {
    "binding_contracts", "balance_confirmation", "documentary_evidence",
    "contract_dismissal", "good_faith"
}

LABOR_ONLY_PRINCIPLES = {
    "labor_art77", "labor_art80", "labor_art84", "labor_art74",
    "labor_art55", "labor_art113"
}

# ─── TEMPLATES ────────────────────────────────────────────────────────

TEMPLATES = {
    "plaintiff_claim": """
باسم الله الرحمن الرحيم

إلى فضيلة رئيس {court_name}                سلمكم الله
السلام عليكم ورحمة الله وبركاته،

الموضوع: لائحة دعوى ( {case_type} )

أتقدم لفضيلتكم بهذه الدعوى ضد المدعى عليه: {defendant_name}
حيث تتلخص وقائع دعواي في الآتي:

أولاً: الوقائع
{facts_summary}

ثانياً: الأسانيد النظامية والشرعية
تأسيسًا على ما سبق، ونظراً لثبوت {key_evidence}، واستناداً إلى المبادئ النظامية التالية:
{legal_principles_list}

ثالثاً: الطلبات
لذا؛ ألتمس من فضيلتكم الحكم لي بالآتي:
1. إلزام المدعى عليه بـ {claim_request}.
2. تعويضي عن أتعاب المحاماة والمصاريف.

والله ولي التوفيق،،،

مقدمه: {plaintiff_name}
""",

    "defendant_response": """
باسم الله الرحمن الرحيم

إلى فضيلة رئيس {court_name}                سلمكم الله
السلام عليكم ورحمة الله وبركاته،

الموضوع: مذكرة جوابية في الدعوى رقم ( {case_number} )

أتقدم لفضيلتكم بهذا الرد على دعوى المدعي، والذي تتلخص فيما يلي:

أولاً: عدم صحة ادعاء المدعي
حيث ذكر المدعي في دعواه أن {plaintiff_claim_summary}، وهذا غير صحيح والدليل على ذلك {defense_evidence}.

ثانياً: الدفوع النظامية
تأسيسًا على المبدأ القضائي المستقر الذي ينص على:
{legal_principles_list}
فإن ما طالب به المدعي يخالف النظام.

ثالثاً: الطلبات
بناءً على ما تقدم، أطلب من فضيلتكم:
1. رد دعوى المدعي لعدم الصحة/عدم الاختصاص.
2. تحميل المدعي كافة المصاريف.

والله ولي التوفيق،،،

المدعى عليه / وكيله: {defendant_name}
""",
    "legal_opinion": """
باسم الله الرحمن الرحيم

الموضوع: مذكرة رأي قانوني تحليلية ( {case_type} )

المحكمة: {court_name}
نتيجة الحكم: {judgment_result}

بناءً على وثيقة ( {case_type} ) الصادرة والمتعلقة بالخلاف بين {plaintiff_name} و {defendant_name}، نورد لكم التحليل التالي:

أولاً: ملخص الوقائع المستخرجة
{facts_summary}

ثانياً: الأسانيد والمواد النظامية المرصودة
استناداً إلى معطيات القضية، تم رصد الاستشهادات التالية:
{legal_principles_list}

ثالثاً: الرأي القانوني والتوصية
{recommendation_text}

هذا ما لزم بيانه، والله ولي التوفيق.
"""
}

# ─── PRINCIPLE FILTERING ──────────────────────────────────────────────

def _filter_principles_by_dispute(principles: List[Dict], dispute_type: str) -> List[Dict]:
    """
    Context-aware principle selection based on dispute_type from entity extraction.
    Uses entities.dispute_type (not classification string) per architecture decision.
    """
    if dispute_type == "عمالي":
        # For labor: prioritize labor articles, exclude commercial-only
        filtered = [p for p in principles if p.get("id", "") not in COMMERCIAL_ONLY_PRINCIPLES]
        # Sort: labor articles first
        filtered.sort(key=lambda p: (0 if p.get("id", "").startswith("labor_") else 1, -p.get("relevance", 0)))
        return filtered
    
    elif dispute_type == "تجاري":
        # For commercial: exclude labor articles
        filtered = [p for p in principles if p.get("id", "") not in LABOR_ONLY_PRINCIPLES]
        return filtered
    
    else:
        # Generic: return all, sorted by relevance
        return principles


# ─── DRAFT GENERATION LOGIC ───────────────────────────────────────────

def generate_draft(
    case_type: str,
    classification_confidence: float,
    legal_principles: List[Dict[str, Any]],
    recommendation: Dict[str, Any],
    party_role: str = "plaintiff",
    entities: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generate a legal draft consuming StructuredCase entities.
    """
    if not entities:
        entities = {}
    
    logger.info(f"Generating draft for {party_role} in {case_type} case...")
    
    doc_type = entities.get('doc_type', 'claim')
    dispute_type = entities.get('dispute_type', 'عام')
    
    # 1. Select Template based on Document Type & Role
    if doc_type == "judgement":
        template_key = "legal_opinion"
        title = f"تحليل قانوني - {case_type}"
    elif party_role == "plaintiff":
        template_key = "plaintiff_claim"
        title = f"لائحة دعوى - {case_type}"
    else:
        template_key = "defendant_response"
        title = f"مذكرة دفاع - {case_type}"
        
    template = TEMPLATES.get(template_key, TEMPLATES["plaintiff_claim"])
    
    # 2. Filter & Format Legal Principles (by dispute_type, not case_type)
    filtered_principles = _filter_principles_by_dispute(legal_principles, dispute_type)
    
    relevant_principles = [p for p in filtered_principles if p.get("relevance", 0) > 0.6]
    if not relevant_principles:
        relevant_principles = filtered_principles[:3]
    
    principles_text = ""
    
    # Inject detected articles from the PDF first (highest priority)
    if entities.get('articles'):
        for art in entities['articles']:
            principles_text += f"- المادة {art} من نظام العمل (تم رصدها في النص الأصلي)\n"
    
    # Then add matched principles
    for p in relevant_principles[:5]:
        p_name = p.get("name_ar", "")
        p_id = p.get("id", "")
        
        # Skip duplicate article mentions (already injected above)
        if entities.get('articles'):
            if any(f"المادة {art}" in p_name for art in entities['articles']):
                continue
        
        principles_text += f"- {p_name}\n"
    
    if not principles_text:
        if dispute_type == "عمالي":
            principles_text = "- أحكام نظام العمل السعودي.\n- حقوق العامل في التعويض."
        else:
            principles_text = "- القواعد العامة في المعاملات.\n- العقد شريعة المتعاقدين."
    
    # 3. Extract all structured fields from entities
    plaintiff_name = entities.get('plaintiff') or "المدعي"
    defendant_name = entities.get('defendant') or "المدعى عليه"
    date = entities.get('date') or "[التاريخ]"
    amount = entities.get('compensation_amount') or "[المبلغ]"
    salary = entities.get('salary')
    duration = entities.get('duration')
    court_name = entities.get('court_name') or "المحكمة العامة"
    judgment_result = entities.get('judgment_result') or "—"
    facts_block = entities.get('facts_block')
    
    direction = recommendation.get("direction", "uncertain")
    recommendation_text = recommendation.get("recommendation_ar", "جاري تحليل الموقف القانوني.")
    
    # 4. Build Facts Summary (from extracted الوقائع section, NOT raw text)
    if facts_block and len(facts_block) > 50:
        # Use the real extracted facts
        facts_summary = facts_block
        # Append structured data points if available
        supplements = []
        if salary:
            supplements.append(f"الأجر الشهري: {salary}")
        if duration:
            supplements.append(f"مدة العلاقة التعاقدية: {duration}")
        if amount and amount != "[المبلغ]":
            supplements.append(f"المبلغ المطالب به: {amount}")
        if supplements:
            facts_summary += "\n\n" + " | ".join(supplements)
    else:
        # Fallback: construct from structured fields
        facts_summary = f"حيث تم التعاقد بين الطرفين بتاريخ {date}."
        if salary:
            facts_summary += f" وكان الأجر الشهري المتفق عليه {salary}."
        if duration:
            facts_summary += f" واستمرت العلاقة التعاقدية لمدة {duration}."
        if amount and amount != "[المبلغ]":
            facts_summary += f"\nونشأ الخلاف حول استحقاقات مالية قدرها {amount}."
        else:
            facts_summary += "\nونشأ الخلاف حول الالتزامات العقدية والمستحقات العمالية."

    # 5. Build Claim Request
    key_evidence = "مستندات القضية المرفقة"
    if dispute_type == "عمالي":
        if amount and amount != "[المبلغ]":
            claim_request = f"سداد المستحقات العمالية ({amount}) والتعويض عن الفصل التعسفي"
        else:
            claim_request = "سداد كافة المستحقات العمالية والتعويض"
        key_evidence = "عقد العمل وكشوفات الرواتب"
    else:
        claim_request = f"سداد المبالغ المستحقة ({amount})"
        
    # 6. Fill Template
    draft_text = template.format(
        case_type=case_type,
        defendant_name=defendant_name,
        plaintiff_name=plaintiff_name,
        court_name=court_name,
        case_number="[رقم القضية]", 
        facts_summary=facts_summary,
        key_evidence=key_evidence,
        legal_principles_list=principles_text,
        claim_request=claim_request,
        plaintiff_claim_summary="أخل بالتزامه العقدي",
        defense_evidence="[الدليل المضاد]",
        recommendation_text=recommendation_text,
        judgment_result=judgment_result
    )
    
    # 7. Quality Check: warn if placeholders remain
    remaining_placeholders = []
    for placeholder in ["[التاريخ]", "[المبلغ]", "[الاسم هنا]"]:
        if placeholder in draft_text:
            remaining_placeholders.append(placeholder)
    if remaining_placeholders:
        logger.warning(f"   Draft still contains placeholders: {remaining_placeholders}")
    
    return {
        "title": title,
        "content": draft_text,
        "type": doc_type,
        "metadata": {
            "based_on_principles": len(relevant_principles),
            "strategy_direction": direction,
            "dispute_type": dispute_type,
            "court_name": court_name,
            "entities_used": [k for k, v in entities.items() if v and v not in ["المدعي", "المدعى عليه", "legal_document", "عام", []]],
            "remaining_placeholders": remaining_placeholders
        }
    }
