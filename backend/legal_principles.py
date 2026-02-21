"""
Legal Principle Extraction Engine for Arabic Legal Cases.

Pattern-matches Arabic legal text against a dictionary of ~20 key
Saudi/Islamic legal doctrines to identify cited principles.

Each principle includes:
- Arabic name
- English name  
- Source section where it was found
- Matched evidence (the sentence)
- Relevance score

Fully rule-based — no hallucination, fully auditable.
"""

import re
from typing import List, Dict


# ── Legal Principles Dictionary ─────────────────────────────────────────
# Each principle has: Arabic name, English name, keywords/patterns

LEGAL_PRINCIPLES = [
    {
        "id": "binding_contracts",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "القوة الملزمة للعقود",
        "name_en": "Binding Force of Contracts",
        "description_ar": "العقد شريعة المتعاقدين — العقود ملزمة لأطرافها",
        "patterns": [
            r"العقد شريعة المتعاقدين",
            r"القوة الملزمة",
            r"عقد صحيح وموقع",
            r"عقد مبرم بين الطرفين",
            r"الالتزامات التعاقدية",
            r"ملزم للطرفين",
            r"التزامات العقد"
        ]
    },
    {
        "id": "burden_of_proof",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "عبء الإثبات",
        "name_en": "Burden of Proof",
        "description_ar": "البينة على المدعي واليمين على من أنكر",
        "patterns": [
            r"البينة على المدعي",
            r"عبء الإثبات",
            r"لم تقدم ما يثبت",
            r"لم يقدم بينة",
            r"عجز عن الإثبات",
            r"إثبات مطالبته",
            r"قدم بينته",
            r"لم يثبت للدائرة"
        ]
    },
    {
        "id": "civil_liability",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "المسؤولية المدنية",
        "name_en": "Civil Liability",
        "description_ar": "كل من أحدث ضرراً بالغير يلتزم بتعويضه",
        "patterns": [
            r"المسؤولية المدنية",
            r"التعويض عن الضرر",
            r"جبر الضرر",
            r"الضرر الناشئ",
            r"تسبب في إتلاف",
            r"إلحاق الضرر"
        ]
    },
    {
        "id": "acknowledgment",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "حجية الإقرار",
        "name_en": "Binding Force of Acknowledgment",
        "description_ar": "الإقرار حجة على المقر ولا عذر لمن أقر",
        "patterns": [
            r"الإقرار حجة",
            r"لا عذر لمن أقر",
            r"إقرار المدعى عليه",
            r"مصادقة على الرصيد",
            r"المصادقة.*إقرار",
            r"أقر بذلك"
        ]
    },
    {
        "id": "fulfillment_obligation",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "وجوب الوفاء بالالتزامات",
        "name_en": "Obligation to Fulfill Commitments",
        "description_ar": "على اليد ما أخذت حتى تؤديه",
        "patterns": [
            r"على اليد ما أخذت",
            r"الوفاء بالالتزام",
            r"سداد المبلغ",
            r"إلزام.{0,20}بسداد",
            r"إلزام.{0,20}بدفع",
            r"إلزام.{0,20}بأن تدفع"
        ]
    },
    {
        "id": "documentary_evidence",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "حجية المحررات",
        "name_en": "Evidentiary Value of Documents",
        "description_ar": "المحرر العادي حجة على من وقعه",
        "patterns": [
            r"المحرر العادي",
            r"نظام الإثبات",
            r"حجة على من وقعه",
            r"المادة.*من نظام الإثبات",
            r"الفواتير.*بينة",
            r"مستندات.*إثبات"
        ]
    },
    {
        "id": "judicial_jurisdiction",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "الاختصاص القضائي",
        "name_en": "Judicial Jurisdiction",
        "description_ar": "تحديد المحكمة المختصة بنظر الدعوى",
        "patterns": [
            r"الاختصاص القضائي",
            r"عدم اختصاص",
            r"الولاية القضائية",
            r"المحكمة المختصة",
            r"اختصاص نوعي",
            r"نظام المرافعات الشرعية"
        ]
    },
    {
        "id": "absence_judgment",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "الحكم الغيابي",
        "name_en": "Default Judgment",
        "description_ar": "الحكم في غياب المدعى عليه بعد تبلغه",
        "patterns": [
            r"عدم حضور.*المدعى عليه",
            r"لم يحضر",
            r"تبلغ.*ولم يحضر",
            r"الحكم الغيابي",
            r"حكمها.*حضورياً",
            r"تبليغ.*صحيح"
        ]
    },
    {
        "id": "abandonment_of_case",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "ترك الخصومة",
        "name_en": "Abandonment of Litigation",
        "description_ar": "تنازل المدعي عن دعواه مع احتفاظه بالحق",
        "patterns": [
            r"ترك الخصومة",
            r"ترك الدعوى",
            r"تنازل المدعي",
            r"ترك.*الدعوى",
            r"المادة.*٩٢.*نظام المرافعات"
        ]
    },
    {
        "id": "good_faith",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "حسن النية",
        "name_en": "Good Faith Doctrine",
        "description_ar": "افتراض حسن النية في التعامل",
        "patterns": [
            r"حسن النية",
            r"سوء النية",
            r"بحسن نية",
            r"التعامل بحسن"
        ]
    },
    {
        "id": "compensation_principle",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "مبدأ التعويض",
        "name_en": "Compensation Principle",
        "description_ar": "التعويض يجب أن يكون بقدر الضرر",
        "patterns": [
            r"التعويض بقدر الضرر",
            r"التعويض المناسب",
            r"تقدير التعويض",
            r"مبلغ التعويض",
            r"التعويض عن"
        ]
    },
    {
        "id": "electronic_notification",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "التبليغ الإلكتروني",
        "name_en": "Electronic Notification",
        "description_ar": "صحة التبليغ عبر الوسائل الإلكترونية",
        "patterns": [
            r"التبليغ.*الإلكتروني",
            r"الوسائل الالكترونية.*التبليغ",
            r"تبليغ.*إلكتروني",
            r"الرسالة النصية",
            r"تبلغت.*إلكترونياً"
        ]
    },
    {
        "id": "contract_dismissal",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "عدم ثبوت التعاقد",
        "name_en": "Unproven Contractual Relationship",
        "description_ar": "رفض الدعوى لعدم إثبات العلاقة التعاقدية",
        "patterns": [
            r"لم يثبت.*تعاقد",
            r"عدم.*إثبات.*التعاقد",
            r"لم تقدم ما يثبت التعاقد",
            r"عدم وجود عقد",
            r"عدم ثبوت"
        ]
    },
    {
        "id": "balance_confirmation",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "حجية مصادقة الرصيد",
        "name_en": "Balance Confirmation as Evidence",
        "description_ar": "مصادقة الرصيد تعد إقراراً بالمبلغ",
        "patterns": [
            r"مصادقة.*الرصيد",
            r"مطابقة رصيد",
            r"المصادقة على الرصيد",
            r"رصيد.*إقرار"
        ]
    },
    {
        "id": "procedural_compliance",
        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",
        "name_ar": "الاستيفاء الشكلي",
        "name_en": "Procedural Compliance",
        "description_ar": "التحقق من الشروط الشكلية لقبول الدعوى",
        "patterns": [
            r"شروط قبول الدعوى",
            r"استيفاء.*الشكلي",
            r"الأوضاع الشكلية",
            r"القبول الشكلي",
            r"اللائحة التنفيذية"
        ]
    },
    # ── Saudi Labor Law Articles ──────────────────────────────────
    {
        "id": "labor_art77",
        "url": "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1",
        "name_ar": "المادة 77 — التعويض عن الفصل غير المشروع",
        "name_en": "Article 77 — Compensation for Unlawful Termination",
        "description_ar": "يحق للعامل المفصول تعسفياً التعويض بأجر المدة المتبقية أو شهرين أيهما أكثر",
        "patterns": [
            r"المادة\s*(?:رقم\s*)?\(?77\)?",
            r"المادة السابعة والسبعون",
            r"فصل تعسفي",
            r"إنهاء العقد.*غير مشروع",
            r"فصل.*بدون سبب",
            r"التعويض عن الفصل"
        ]
    },
    {
        "id": "labor_art80",
        "url": "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1",
        "name_ar": "المادة 80 — إنهاء العقد بدون مكافأة",
        "name_en": "Article 80 — Lawful Termination Without Notice",
        "description_ar": "حالات يحق فيها لصاحب العمل فسخ العقد دون مكافأة أو إنذار",
        "patterns": [
            r"المادة\s*(?:رقم\s*)?\(?80\)?",
            r"المادة الثمانون",
            r"فسخ العقد دون مكافأة",
            r"فسخ.*دون إنذار",
            r"إنهاء.*بدون إنذار.*نظام العمل"
        ]
    },
    {
        "id": "labor_art84",
        "url": "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1",
        "name_ar": "المادة 84 — مكافأة نهاية الخدمة",
        "name_en": "Article 84 — End-of-Service Gratuity",
        "description_ar": "يستحق العامل مكافأة عن مدة خدمته بواقع أجر نصف شهر عن كل سنة من الخمس الأولى",
        "patterns": [
            r"المادة\s*(?:رقم\s*)?\(?84\)?",
            r"المادة الرابعة والثمانون",
            r"مكافأة نهاية الخدمة",
            r"مكافأة.*نهاية.*خدمة",
            r"أجر نصف شهر.*سنة"
        ]
    },
    {
        "id": "labor_art74",
        "url": "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1",
        "name_ar": "المادة 74 — حالات انتهاء عقد العمل",
        "name_en": "Article 74 — Contract Termination Conditions",
        "description_ar": "ينتهي عقد العمل بالاتفاق أو انتهاء المدة أو بلوغ سن التقاعد أو القوة القاهرة",
        "patterns": [
            r"المادة\s*(?:رقم\s*)?\(?74\)?",
            r"المادة الرابعة والسبعون",
            r"انتهاء عقد العمل",
            r"انتهاء مدة العقد",
            r"إنهاء.*باتفاق الطرفين"
        ]
    },
    {
        "id": "labor_art55",
        "url": "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1",
        "name_ar": "المادة 55 — فترة التجربة",
        "name_en": "Article 55 — Probationary Period",
        "description_ar": "فترة التجربة لا تزيد عن تسعين يوماً ويجوز تمديدها لمائة وثمانين يوماً",
        "patterns": [
            r"المادة\s*(?:رقم\s*)?\(?55\)?",
            r"المادة الخامسة والخمسون",
            r"فترة التجربة",
            r"فترة الاختبار",
            r"تحت التجربة"
        ]
    },
    {
        "id": "labor_art113",
        "url": "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1",
        "name_ar": "المادة 113 — ساعات العمل والعمل الإضافي",
        "name_en": "Article 113 — Working Hours & Overtime",
        "description_ar": "لا يجوز تشغيل العامل أكثر من ثماني ساعات يومياً أو ثمان وأربعين ساعة أسبوعياً",
        "patterns": [
            r"المادة\s*(?:رقم\s*)?\(?113\)?",
            r"المادة الثالثة عشرة بعد المائة",
            r"ساعات العمل الإضافي",
            r"أجر إضافي",
            r"عمل إضافي",
            r"ساعات عمل.*إضافية"
        ]
    }
]


def extract_legal_principles(text: str) -> List[Dict]:
    """
    Extract legal principles mentioned in the text.
    
    Returns list of dicts, each with:
        - id: principle identifier
        - name_ar: Arabic name
        - name_en: English name
        - description_ar: Arabic description
        - source_section: which section it was found in (facts/reasoning/verdict)
        - evidence: the matched sentence
        - relevance: score (0.0 - 1.0)
    """
    results = []
    
    # Detect which section each part of text belongs to
    sections = _detect_sections(text)
    
    for principle in LEGAL_PRINCIPLES:
        matches = []
        
        for pattern in principle["patterns"]:
            for match in re.finditer(pattern, text):
                # Find the sentence containing this match
                sentence = _extract_sentence(text, match.start(), match.end())
                source_section = _find_section(match.start(), sections)
                
                matches.append({
                    "pattern": pattern,
                    "matched_text": match.group(),
                    "sentence": sentence,
                    "source_section": source_section
                })
        
        if matches:
            # Calculate relevance based on number and quality of matches
            relevance = min(len(matches) * 0.25, 1.0)
            
            # Prefer reasoning section matches (they carry more weight)
            has_reasoning_match = any(m["source_section"] == "reasoning" for m in matches)
            if has_reasoning_match:
                relevance = min(relevance + 0.2, 1.0)
            
            # Pick the best evidence sentence (prefer from reasoning)
            best_match = next(
                (m for m in matches if m["source_section"] == "reasoning"),
                matches[0]
            )
            
            results.append({
                "id": principle["id"],
                "name_ar": principle["name_ar"],
                "name_en": principle["name_en"],
                "description_ar": principle["description_ar"],
                "source_section": best_match["source_section"],
                "evidence": best_match["sentence"],
                "relevance": round(relevance, 2),
                "match_count": len(matches),
                "url": principle.get("url")
            })
    
    # Sort by relevance descending
    results.sort(key=lambda x: x["relevance"], reverse=True)
    
    return results


def _detect_sections(text: str) -> List[Dict]:
    """Detect section boundaries in the text."""
    sections = []
    
    # Find section markers
    patterns = [
        (r"(?:الوقائع|وقائع الدعوى|تتحصل وقائع)", "facts"),
        (r"(?:الأسباب|أسباب الحكم|وحيث إن المحكمة)", "reasoning"),
        (r"(?:منطوق الحكم|حكمت المحكمة|فلهذه الأسباب)", "verdict"),
    ]
    
    for pattern, section_name in patterns:
        for match in re.finditer(pattern, text):
            sections.append({
                "name": section_name,
                "start": match.start()
            })
    
    # Sort by position
    sections.sort(key=lambda x: x["start"])
    
    # If no sections detected, treat everything as "general"
    if not sections:
        sections = [{"name": "general", "start": 0}]
    
    return sections


def _find_section(position: int, sections: List[Dict]) -> str:
    """Find which section a position belongs to."""
    current_section = "general"
    for section in sections:
        if position >= section["start"]:
            current_section = section["name"]
        else:
            break
    return current_section


def _extract_sentence(text: str, start: int, end: int) -> str:
    """Extract the sentence containing the match."""
    # Find sentence boundaries (Arabic period, question mark, or newline)
    sentence_start = start
    sentence_end = end
    
    # Search backward for sentence start
    for i in range(start - 1, max(start - 500, 0) - 1, -1):
        if i < 0:
            sentence_start = 0
            break
        if text[i] in '.؟!\n':
            sentence_start = i + 1
            break
    else:
        sentence_start = max(start - 500, 0)
    
    # Search forward for sentence end
    for i in range(end, min(end + 500, len(text))):
        if text[i] in '.؟!\n':
            sentence_end = i + 1
            break
    else:
        sentence_end = min(end + 500, len(text))
    
    return text[sentence_start:sentence_end].strip()


if __name__ == "__main__":
    test_text = """الوقائع:
تقدم المدعي بدعوى أمام المحكمة العامة يطالب فيها بإلزام المدعى عليه بسداد مبلغ وقدره 75,000 ريال سعودي، 
وذلك نتيجة إخلاله بالعقد المبرم بين الطرفين والمتعلق بتنفيذ أعمال صيانة في أحد العقارات.

الأسباب:
وحيث إن المحكمة بعد الاطلاع على أوراق الدعوى تبين لها وجود عقد صحيح وموقع بين الطرفين، 
وثبوت قيام المدعي بتنفيذ التزاماته التعاقدية. ولم يقدم المدعى عليه ما يثبت السداد.

منطوق الحكم:
حكمت المحكمة بإلزام المدعى عليه بسداد مبلغ 75,000 ريال سعودي للمدعي، وتحميله المصاريف القضائية."""
    
    principles = extract_legal_principles(test_text)
    print(f"\nFound {len(principles)} legal principles:\n")
    for p in principles:
        print(f"  ️ {p['name_ar']} ({p['name_en']})")
        print(f"     Section: {p['source_section']}")
        print(f"     Evidence: {p['evidence'][:100]}...")
        print(f"     Relevance: {p['relevance']}")
        print()
