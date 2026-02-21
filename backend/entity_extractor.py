"""
Structured Entity Extraction for Arabic Legal Documents.

Hybrid extraction strategy:
  1. Regex — for amounts, dates, article references
  2. Keyword windows — for party names (plaintiff/defendant)
  3. Sentence-level heuristics — for verdict detection
  4. Section parsing — for extracting الوقائع block

Returns a StructuredCase dict consumed by draft_engine and recommendation_engine.
"""

import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# ── Section Extraction ────────────────────────────────────────────────

def _extract_section(text: str, start_markers: List[str], stop_markers: List[str], max_chars: int = 2000) -> Optional[str]:
    """
    Extract a section of text between start_markers and stop_markers.
    Returns the text between the first matched start marker and the first matched stop marker.
    """
    clean = text.replace('\r\n', '\n')
    
    # Find the earliest start marker
    start_pos = -1
    for marker in start_markers:
        idx = clean.find(marker)
        if idx != -1 and (start_pos == -1 or idx < start_pos):
            start_pos = idx
    
    if start_pos == -1:
        return None
    
    # Find the earliest stop marker AFTER start
    search_from = start_pos + 10  # skip the marker itself
    end_pos = len(clean)
    
    for marker in stop_markers:
        idx = clean.find(marker, search_from)
        if idx != -1 and idx < end_pos:
            end_pos = idx
    
    # Cap at max_chars
    end_pos = min(end_pos, start_pos + max_chars)
    
    section = clean[start_pos:end_pos].strip()
    return section if len(section) > 20 else None


def _find_sentence_containing(text: str, keyword: str) -> Optional[str]:
    """Find the sentence containing a keyword."""
    idx = text.find(keyword)
    if idx == -1:
        return None
    
    # Expand backward to sentence start
    start = idx
    for i in range(idx - 1, max(idx - 500, 0) - 1, -1):
        if i < 0:
            start = 0
            break
        if text[i] in '.؟!\n':
            start = i + 1
            break
    else:
        start = max(idx - 500, 0)
    
    # Expand forward to sentence end
    end = idx + len(keyword)
    for i in range(end, min(end + 500, len(text))):
        if text[i] in '.؟!\n':
            end = i + 1
            break
    else:
        end = min(end + 500, len(text))
    
    return text[start:end].strip()


# ── Main Extractor ────────────────────────────────────────────────────

class EntityExtractor:
    @staticmethod
    def extract(text: str) -> Dict[str, Any]:
        """
        Hybrid extraction of structured legal entities from Arabic text.
        
        Returns StructuredCase dict with keys:
            plaintiff, defendant, date, salary, compensation_amount,
            contract_value, court_name, judgment_result, dispute_type,
            doc_type, articles, facts_block, duration
        """
        entities: Dict[str, Any] = {
            "plaintiff": None,
            "defendant": None,
            "date": None,
            "contract_value": None,
            "compensation_amount": None,
            "salary": None,
            "duration": None,
            "court_name": None,
            "judgment_result": None,
            "dispute_type": None,
            "doc_type": "legal_document",
            "articles": [],
            "facts_block": None
        }
        
        if not text or len(text.strip()) < 50:
            return entities
        
        # Normalize text for matching
        clean = text.replace('\n', ' ').replace('\r', ' ')
        clean = re.sub(r'\s+', ' ', clean)  # collapse whitespace
        
        # ═══════════════════════════════════════════════════════════
        # 0. DOCUMENT TYPE DETECTION (Prioritize Judgment/Ruling)
        # ═══════════════════════════════════════════════════════════
        judgement_signals = [
            "منطوق الحكم", "حكمت المحكمة", "قرار الدائرة", "أصدرت حكمها", 
            "فلهذه الأسباب حكمت", "صك حكم", "رقم الصك", "تاريخ الصك",
            "قررت الدائرة", "حكماً غيابياً", "حكماً حضورياً", "استلام الصك"
        ]
        claim_signals = [
            "لائحة دعوى", "يطلب المدعي", "تحريك دعوى", "أتقدم لفضيلتكم بهذه الدعوى",
            "موضوع الدعوى", "طلبات المدعي", "صحيفة دعوى"
        ]
        
        judgement_count = sum(1 for s in judgement_signals if s in clean)
        claim_count = sum(1 for s in claim_signals if s in clean)
        
        # Priority: If ANY strong judgment signal exists, it's a judgment. 
        # (Judgments often recite the claim, so claim signals are common in judgments)
        if judgement_count >= 1:
            entities["doc_type"] = "judgement"
        elif claim_count >= 1:
            entities["doc_type"] = "claim"
        
        logger.info(f"  → Doc type detected: {entities['doc_type']} (judgement signals: {judgement_count}, claim signals: {claim_count})")

        # ═══════════════════════════════════════════════════════════
        # 1. COURT NAME DETECTION
        # ═══════════════════════════════════════════════════════════
        court_patterns = [
            r"(المحكمة العمالية\s*(?:بـ?|في)?\s*[\u0621-\u064A]+)",
            r"(المحكمة العامة\s*(?:بـ?|في)?\s*[\u0621-\u064A]+)",
            r"(الدائرة\s+(?:التجارية|العمالية|الجزائية|المدنية)\s*(?:الأولى|الثانية|الثالثة|الرابعة)?)",
            r"(محكمة\s+الاستئناف\s*(?:بـ?|في)?\s*[\u0621-\u064A]+)",
            r"(المحكمة\s+التجارية\s*(?:بـ?|في)?\s*[\u0621-\u064A]+)",
        ]
        for cp in court_patterns:
            cm = re.search(cp, clean)
            if cm:
                entities["court_name"] = cm.group(1).strip()
                break

        # ═══════════════════════════════════════════════════════════
        # 2. PARTY EXTRACTION (keyword window approach)
        # ═══════════════════════════════════════════════════════════
        
        # --- Plaintiff ---
        plaintiff_patterns = [
            # "المقامة من ... ضد"
            r"المقامة من\s+(?:المدعي|المواطن|المواطنة|شركة|مؤسسة)?\s*[:/]?\s*(.+?)(?:\s+ضد|\s+على\s+المدعى)",
            # "المدعي / المدعي:"
            r"المدعي\s*[:/]\s*(.+?)(?:\s+ضد|\s+والمدعى|\s+سجل|\s+هوية|[،,\.])",
            # "المدعية:"
            r"المدعية\s*[:/]\s*(.+?)(?:\s+ضد|\s+والمدعى|\s+سجل|[،,\.])",
            # "تقدم المدعي شركة/مؤسسة ..."
            r"تقدم\s+(?:المدعي|المدعية)\s+(.+?)(?:\s+بدعوى|\s+بطلب|\s+ضد|[،,\.])",
            # "من: شركة ..."
            r"من\s*:\s*(شركة|مؤسسة)\s+(.+?)(?:\s+ضد|\s+على|[،,\.])",
            # "الطرف الأول"
            r"الطرف الأول\s*[:/]\s*(.+?)(?:\s+الطرف الثاني|[،,\.])",
        ]
        for p in plaintiff_patterns:
            m = re.search(p, clean)
            if m:
                # Use last group (handles multi-group patterns)
                name = m.group(m.lastindex).strip() if m.lastindex else m.group(1).strip()
                # Clean trailing particles
                name = re.sub(r'\s*(?:والمدعى|وذلك|حيث|بموجب).*$', '', name).strip()
                if 3 < len(name) < 120:
                    entities["plaintiff"] = name
                    break
        
        # --- Defendant ---
        defendant_patterns = [
            r"ضد\s+(?:المدعى عليه|المدعى عليها)?\s*[:/]?\s*(?:المواطن|المواطنة|شركة|مؤسسة)?\s*(.+?)(?:\s+سجل|\s+هوية|\s+في\s+الدعوى|\s+بتاريخ|\s+وذلك|[،,\.])",
            r"المدعى عليه\s*[:/]\s*(.+?)(?:\s+سجل|\s+هوية|\s+في|[،,\.])",
            r"المدعى عليها\s*[:/]\s*(.+?)(?:\s+سجل|\s+هوية|\s+في|[،,\.])",
            r"الطرف الثاني\s*[:/]\s*(.+?)(?:\s+بموجب|[،,\.])",
        ]
        for p in defendant_patterns:
            m = re.search(p, clean)
            if m:
                name = m.group(1).strip()
                name = re.sub(r'\s*(?:وذلك|حيث|بموجب|يتلخص).*$', '', name).strip()
                # Clean leading artifacts like 'ا:' from regex capture
                name = re.sub(r'^[ا-ي]:\s*', '', name).strip()
                if 3 < len(name) < 120:
                    entities["defendant"] = name
                    break
        
        # Fallbacks if still None
        if not entities["plaintiff"]:
            entities["plaintiff"] = "المدعي"
        if not entities["defendant"]:
            entities["defendant"] = "المدعى عليه"

        # ═══════════════════════════════════════════════════════════
        # 3. DATE EXTRACTION (Hijri + Gregorian)
        # ═══════════════════════════════════════════════════════════
        date_patterns = [
            # Hijri: 1445/05/20 or 20/05/1445 or 1445-05-20
            r"(\d{1,2}[/\-]\d{1,2}[/\-]1[34]\d{2})",
            r"(1[34]\d{2}[/\-]\d{1,2}[/\-]\d{1,2})",
            # Gregorian: 2024/01/15 or 15/01/2024
            r"(\d{1,2}/\d{1,2}/20\d{2})",
            r"(20\d{2}/\d{1,2}/\d{1,2})",
            # Textual: بتاريخ 1445/05/20هـ
            r"بتاريخ\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\s*هـ?",
        ]
        for dp in date_patterns:
            dm = re.search(dp, clean)
            if dm:
                entities["date"] = dm.group(1).strip()
                break

        # ═══════════════════════════════════════════════════════════
        # 4. MONEY EXTRACTION (Salary, Compensation, Contract Value)
        # ═══════════════════════════════════════════════════════════
        
        # --- Salary ---
        salary_patterns = [
            r"(?:راتب(?:ه)?|أجر(?:ه)?(?:\s+الشهري)?|الراتب الشهري|الأجر الشهري|أجر شهري)\s*(?:وقدره|البالغ|هو|بمبلغ|مقداره)?\s*[:\s]*(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            r"(?:راتب|أجر)\s+(?:أساسي|شهري)\s*(?:وقدره|البالغ)?\s*[:\s]*(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            r"(?:يتقاضى|يحصل على)\s+(?:مبلغ\s+)?(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)\s*(?:شهرياً|شهري)",
            r"مبلغ\s+(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س)\s*شهرياً",
        ]
        for sp in salary_patterns:
            sm = re.search(sp, clean)
            if sm:
                entities["salary"] = sm.group(1).replace(',', '') + " ريال"
                break

        # --- Compensation / Award Amount ---
        comp_patterns = [
            # Explicit award totals
            r"إجمالي\s+(?:المستحقات|المبلغ|التعويض)\s*[:\s]*(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            r"صافي\s+(?:المستحقات|التعويض)\s*[:\s]*(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            # Court award phrasing
            r"بمبلغ\s*(?:وقدره)?\s*(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            r"مبلغ\s*(?:وقدره|قدره)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            r"إلزام.*?بدفع\s+(?:مبلغ\s*(?:وقدره)?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            r"إلزام.*?بسداد\s+(?:مبلغ\s+)?(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            # Direct claim amount
            r"(?:مطالبة|يطالب)\s+(?:بمبلغ\s+)?(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            # General "مبلغ X ريال" (lowest priority)
            r"مبلغ\s+(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
        ]
        for cp in comp_patterns:
            cm = re.search(cp, clean)
            if cm:
                raw_amount = cm.group(1).replace(',', '')
                # Skip tiny amounts that are likely salary or fees, not compensation
                try:
                    if float(raw_amount) >= 500:
                        entities["compensation_amount"] = cm.group(1) + " ريال"
                        break
                except ValueError:
                    pass

        # --- Contract Value (fallback to salary if not found) ---
        contract_patterns = [
            r"قيمة العقد\s*[:\s]*(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
            r"العقد\s+(?:بمبلغ|بقيمة)\s+(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|SAR)",
        ]
        for cvp in contract_patterns:
            cvm = re.search(cvp, clean)
            if cvm:
                entities["contract_value"] = cvm.group(1) + " ريال"
                break
        
        if not entities["contract_value"] and entities["salary"]:
            entities["contract_value"] = entities["salary"]

        # ═══════════════════════════════════════════════════════════
        # 5. DURATION EXTRACTION
        # ═══════════════════════════════════════════════════════════
        duration_patterns = [
            r"(\d+)\s+(?:سنوات|سنة|أعوام|عام)",
            r"لمدة\s+(\d+)\s+(?:سنوات|سنة|أعوام|عام|أشهر|شهر)",
            r"مدة\s+العقد\s*[:\s]*(\d+)\s*(?:سنوات|سنة|أعوام|عام|أشهر|شهر)",
        ]
        for drp in duration_patterns:
            drm = re.search(drp, clean)
            if drm:
                # Detect unit
                full_match = drm.group(0)
                if any(u in full_match for u in ["أشهر", "شهر"]):
                    entities["duration"] = drm.group(1) + " أشهر"
                else:
                    entities["duration"] = drm.group(1) + " سنوات"
                break

        # ═══════════════════════════════════════════════════════════
        # 6. LEGAL ARTICLES (Saudi Labor Law + Others)
        # ═══════════════════════════════════════════════════════════
        article_patterns = [
            (r"المادة\s*(?:رقم\s*)?\(?(\d+)\)?", None),  # Generic "المادة 77"
            (r"المادة\s+السابعة\s+والسبعون", "77"),
            (r"المادة\s+الرابعة\s+والثمانون", "84"),
            (r"المادة\s+الثمانون", "80"),
            (r"المادة\s+الرابعة\s+والسبعون", "74"),
            (r"المادة\s+الخامسة\s+والخمسون", "55"),
            (r"المادة\s+الثالثة\s+عشرة\s+بعد\s+المائة", "113"),
        ]
        found_articles = set()
        for pattern, fixed_num in article_patterns:
            for m in re.finditer(pattern, clean):
                if fixed_num:
                    found_articles.add(fixed_num)
                else:
                    art_num = m.group(1)
                    # Only keep reasonable article numbers (1-250)
                    try:
                        if 1 <= int(art_num) <= 250:
                            found_articles.add(art_num)
                    except ValueError:
                        pass
        entities["articles"] = sorted(list(found_articles), key=lambda x: int(x))

        # ═══════════════════════════════════════════════════════════
        # 7. JUDGMENT RESULT (sentence-level heuristics)
        # ═══════════════════════════════════════════════════════════
        if entities["doc_type"] == "judgement":
            # Find the sentence containing the verdict
            verdict_keywords = ["حكمت المحكمة", "فلهذه الأسباب حكمت", "قررت الدائرة", "أصدرت حكمها"]
            verdict_sentence = None
            for vk in verdict_keywords:
                verdict_sentence = _find_sentence_containing(clean, vk)
                if verdict_sentence:
                    break
            
            if verdict_sentence:
                # Heuristic: Check what the court ordered
                if any(w in verdict_sentence for w in ["إلزام", "ألزمت", "يلزم", "تلزم"]):
                    entities["judgment_result"] = "إلزام المدعى عليه (Plaintiff Win)"
                elif any(w in verdict_sentence for w in ["رفض الدعوى", "رد الدعوى", "عدم قبول"]):
                    entities["judgment_result"] = "رفض الدعوى (Plaintiff Loss)"
                elif any(w in verdict_sentence for w in ["صلح", "تسوية"]):
                    entities["judgment_result"] = "تسوية ودية (Settlement)"
                elif any(w in verdict_sentence for w in ["عدم الاختصاص"]):
                    entities["judgment_result"] = "عدم الاختصاص (Jurisdictional)"
                else:
                    entities["judgment_result"] = "حكم صادر (Decided)"
            else:
                # Broader search
                if "إلزام" in clean or "ألزمت" in clean:
                    entities["judgment_result"] = "إلزام المدعى عليه (Plaintiff Win)"
                elif "رفض الدعوى" in clean or "رد الدعوى" in clean:
                    entities["judgment_result"] = "رفض الدعوى (Plaintiff Loss)"

        # ═══════════════════════════════════════════════════════════
        # 8. DISPUTE TYPE INFERENCE (from text signals, NOT classification)
        # ═══════════════════════════════════════════════════════════
        labor_signals = ["نظام العمل", "عقد عمل", "مكافأة نهاية الخدمة", "فصل تعسفي", 
                         "المحكمة العمالية", "العامل", "صاحب العمل", "راتب", "أجر",
                         "المادة 77", "المادة 80", "المادة 84"]
        commercial_signals = ["عقد تجاري", "شركة", "مؤسسة", "الدائرة التجارية", 
                              "فاتورة", "مصادقة رصيد", "شيك", "كمبيالة"]
        civil_signals = ["إيجار", "عقار", "تعويض", "ضرر", "المحكمة العامة"]
        
        labor_score = sum(1 for s in labor_signals if s in clean)
        commercial_score = sum(1 for s in commercial_signals if s in clean)
        civil_score = sum(1 for s in civil_signals if s in clean)
        
        max_score = max(labor_score, commercial_score, civil_score)
        if max_score > 0:
            if labor_score == max_score:
                entities["dispute_type"] = "عمالي"
            elif commercial_score == max_score:
                entities["dispute_type"] = "تجاري"
            else:
                entities["dispute_type"] = "مدني"
        else:
            entities["dispute_type"] = "عام"
            
        logger.info(f"  → Dispute type: {entities['dispute_type']} (labor:{labor_score}, commercial:{commercial_score}, civil:{civil_score})")

        # ═══════════════════════════════════════════════════════════
        # 9. FACTS BLOCK EXTRACTION (section-aware)
        # ═══════════════════════════════════════════════════════════
        facts_block = _extract_section(
            text,
            start_markers=["الوقائع", "وقائع الدعوى", "تتحصل وقائع", "أولاً: الوقائع", "ملخص القضية"],
            stop_markers=["الأسباب", "أسباب الحكم", "حكمت المحكمة", "ثانياً:", "منطوق الحكم"],
            max_chars=2000
        )
        if facts_block:
            entities["facts_block"] = facts_block
        else:
            # Fallback: use first meaningful paragraph (skip court headers)
            # Find first sentence that looks like case content
            paragraphs = text.split('\n')
            content_paras = []
            for para in paragraphs:
                para = para.strip()
                # Skip short lines (headers, metadata)
                if len(para) > 80:
                    content_paras.append(para)
                if len(content_paras) >= 3:
                    break
            if content_paras:
                entities["facts_block"] = "\n".join(content_paras)[:1500]
        
        # ═══════════════════════════════════════════════════════════
        # SUMMARY LOG
        # ═══════════════════════════════════════════════════════════
        populated = sum(1 for k, v in entities.items() if v and v != "المدعي" and v != "المدعى عليه" and v != "legal_document" and v != "عام" and v != [])
        logger.info(f"  → Entity extraction complete: {populated}/13 fields populated")
        
        return entities


if __name__ == "__main__":
    # Test with a real-world-like judgment
    sample = """
    الدائرة العمالية الأولى بالمحكمة العمالية بجدة
    
    في القضية المقامة من المدعي: محمد أحمد العتيبي ضد المدعى عليها: شركة الأفق للمقاولات
    سجل تجاري رقم 123456
    
    الوقائع:
    تقدم المدعي بدعوى يطلب فيها إلزام المدعى عليها بدفع مستحقاته العمالية وتشمل:
    رواتب متأخرة وبدل إجازات ومكافأة نهاية الخدمة. حيث كان يعمل لدى المدعى عليها 
    براتب شهري وقدره 8,500 ريال وذلك منذ تاريخ 1440/03/15هـ ولمدة 4 سنوات.
    تم فصله تعسفياً بدون سابق إنذار وبالمخالفة لأحكام المادة 77 من نظام العمل.
    
    الأسباب:
    وحيث إن الدائرة اطلعت على المستندات وثبت لها صحة العلاقة العمالية.
    واستناداً إلى المادة 84 من نظام العمل بشأن مكافأة نهاية الخدمة.
    
    منطوق الحكم:
    حكمت المحكمة بإلزام المدعى عليها بدفع مبلغ وقدره 127,500 ريال للمدعي
    شاملاً مكافأة نهاية الخدمة والتعويض عن الفصل التعسفي.
    """
    
    result = EntityExtractor.extract(sample)
    print("\n=== Extraction Results ===")
    for k, v in result.items():
        status = "[OK]" if v and v not in ["المدعي", "المدعى عليه", "legal_document", "عام", []] else "[--]"
        print(f"  {status} {k}: {v}")
