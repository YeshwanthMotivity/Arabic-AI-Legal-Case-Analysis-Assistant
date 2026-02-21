"""
Precedent Trend Analyzer for Arabic Legal Cases.

Analyzes similar case rulings to compute:
- Plaintiff win rate (%)
- Average compensation amount (SAR)
- Outcome distribution (win/loss/dismissed/jurisdictional)
- Most cited legal principles
- Sample size warnings

Uses regex to detect ruling outcomes and extract monetary amounts
from judgment text. No ML needed.
"""

import re
import math
from typing import List, Dict, Optional
from models import Case

MIN_SAMPLE_FOR_WIN_RATE = 3
MIN_SAMPLE_FOR_COMPENSATION = 3

def filter_outliers(compensations: List[float]) -> List[float]:
    """
    Robust outlier filtering using median-ratio check and IQR.
    """
    if not compensations: return []
    if len(compensations) < 2: return compensations
    
    sorted_c = sorted(compensations)
    n = len(sorted_c)
    median = sorted_c[n // 2]
    
    # 1. Aggressive check for extreme outliers relative to median
    # (Especially important for small N where IQR fails)
    filtered_comp = list(compensations)
    if median > 0:
        # If max is > 20x median, it's almost certainly an error/outlier in this domain
        if sorted_c[-1] > 20 * median:
            filtered_comp = [x for x in compensations if x < sorted_c[-1]]
            if len(filtered_comp) < 2: return filtered_comp
            sorted_c = sorted(filtered_comp)
            n = len(sorted_c)
    
    # 2. IQR Check for remaining data (if N >= 4)
    if n >= 4:
        q1 = sorted_c[n // 4]
        q3 = sorted_c[n * 3 // 4]
        iqr = q3 - q1
        upper_bound = q3 + 3.0 * iqr 
        return [x for x in filtered_comp if x <= upper_bound]
            
    return filtered_comp


# ── Arabic numeral conversion ──────────────────────────────────────────

ARABIC_DIGITS = {'٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
                 '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'}

def arabic_to_int(text: str) -> Optional[float]:
    """Convert Arabic numeral string to float."""
    # Replace Arabic digits with Western
    for ar, en in ARABIC_DIGITS.items():
        text = text.replace(ar, en)
    # Remove commas and spaces but keep decimal dots
    text = text.replace(',', '').replace(' ', '').strip()
    try:
        return float(text)
    except ValueError:
        return None


# ── Outcome Detection ──────────────────────────────────────────────────

OUTCOME_PATTERNS = {
    "plaintiff_win": [
        r"إلزام المدعى عليه",
        r"إلزام المدعى عليها",
        r"بأن تدفع",
        r"بأن يدفع",
        r"بسداد مبلغ",
        r"حكمت.*بإلزام",
        r"إلزام.*بدفع",
        r"لصالح المدعي",
    ],
    "plaintiff_loss": [
        r"رفض الدعوى",
        r"برفض الدعوى",
        r"عدم قبول الدعوى",
        r"رفض.*المقامة",
    ],
    "dismissed": [
        r"إثبات ترك",
        r"ترك.*الدعوى",
        r"شطب الدعوى",
        r"انقضاء الخصومة",
    ],
    "jurisdictional": [
        r"عدم اختصاص",
        r"عدم الاختصاص",
        r"إحالة.*المحكمة المختصة",
    ]
}


def detect_outcome(judgment_text: str) -> str:
    """Detect the ruling outcome from judgment text."""
    scores = {}
    
    for outcome, patterns in OUTCOME_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, judgment_text):
                score += 1
        scores[outcome] = score
    
    # Return highest scoring outcome
    if max(scores.values()) == 0:
        return "unknown"
    
    return max(scores, key=scores.get)


def extract_compensation_amount(text: str) -> Optional[float]:
    """Extract monetary amount from judgment/facts text."""
    # Pattern: number followed by ريال
    patterns = [
        # Western numerals
        r'([\d,\.]+)\s*ريال',
        # Arabic numerals with parentheses
        r'\(([\d٠-٩,\.]+)\)\s*(?:ريال|ألف|مائة)',
        # مبلغ قدره pattern
        r'مبلغ[اً]?\s*(?:قدره|وقدره)\s*\(?([\d٠-٩,\.]+)\)?',
        # بمبلغ pattern 
        r'بمبلغ\s*\(?([\d٠-٩,\.]+)\)?',
    ]
    
    amounts = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            raw = match.group(1)
            amount = arabic_to_int(raw)
            if amount and amount > 0:
                amounts.append(amount)
    
    # Return the largest amount found (usually the judgment amount)
    return max(amounts) if amounts else None


def analyze_trends(cases: List[Case]) -> Dict:
    """
    Analyze ruling trends from a list of similar cases.
    
    Returns:
        - outcomes: dict of outcome counts
        - plaintiff_win_rate: float (0-100)
        - average_compensation: float (SAR)
        - median_compensation: float (SAR)
        - compensation_range: (min, max)
        - sample_size: int
        - reliability: str ("high"/"medium"/"low"/"insufficient")
    """
    outcomes = {
        "plaintiff_win": 0,
        "plaintiff_loss": 0,
        "dismissed": 0,
        "jurisdictional": 0,
        "unknown": 0
    }
    
    compensations = []
    
    for case in cases:
        # Detect outcome
        outcome = detect_outcome(case.judgment)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        # Extract compensation if plaintiff won
        if outcome == "plaintiff_win":
            amount = extract_compensation_amount(case.judgment)
            if amount is None:
                # Try from facts
                amount = extract_compensation_amount(case.facts)
            if amount and amount > 0:
                compensations.append(amount)
    
    sample_size = len(cases)
    decided_cases = outcomes["plaintiff_win"] + outcomes["plaintiff_loss"]
    
    # Win rate (only among decided cases)
    if decided_cases > 0:
        plaintiff_win_rate = round((outcomes["plaintiff_win"] / decided_cases) * 100, 1)
    else:
        plaintiff_win_rate = 0.0
    
    # Compensation stats
    # Compensation stats with Robust Filtering (Remove Outliers)
    if compensations:
        sorted_comp = sorted(compensations)
        n = len(sorted_comp)
        median_compensation = sorted_comp[n // 2]
        
        filtered_comp = filter_outliers(compensations)
        
        avg_compensation = round(sum(filtered_comp) / len(filtered_comp), 2) if filtered_comp else 0.0
        comp_range = (min(compensations), max(compensations))
    else:
        avg_compensation = 0.0
        median_compensation = 0.0
        comp_range = (0, 0)
    
    # Reliability assessment based on sample size
    if sample_size >= 10:
        reliability = "high"
    elif sample_size >= 5:
        reliability = "medium"
    else:
        # Enforce statistical significance: < 5 samples is insufficient
        reliability = "insufficient"
        
    # If insufficient data, suppress misleading "100%" win rates based on 1-2 cases
    if reliability == "insufficient":
        plaintiff_win_rate = 0.0
        avg_compensation = 0.0
        median_compensation = 0.0
        comp_range = (0, 0)

    # Compensation statistics also require their own minimum sample size.
    if len(compensations) < MIN_SAMPLE_FOR_COMPENSATION:
        avg_compensation = 0.0
        median_compensation = 0.0
        comp_range = (0, 0)

    # Win-rate is hidden if decided sample is too small.
    if decided_cases < MIN_SAMPLE_FOR_WIN_RATE:
        plaintiff_win_rate = 0.0
    
    return {
        "outcomes": outcomes,
        "plaintiff_win_rate": plaintiff_win_rate,
        "average_compensation": avg_compensation,
        "median_compensation": median_compensation,
        "compensation_range": {"min": comp_range[0], "max": comp_range[1]},
        "compensation_count": len(compensations),
        "sample_size": sample_size,
        "decided_cases": decided_cases,
        "reliability": reliability
    }


if __name__ == "__main__":
    # Quick test with mock data
    test_judgment_win = "حكمت المحكمة بإلزام المدعى عليه بسداد مبلغ 75,000 ريال سعودي للمدعي"
    test_judgment_loss = "حكمت الدائرة برفض الدعوى المقامة من المدعية ضد المدعى عليها"
    
    print(f"Win test: {detect_outcome(test_judgment_win)}")
    print(f"Loss test: {detect_outcome(test_judgment_loss)}")
    print(f"Amount: {extract_compensation_amount(test_judgment_win)}")
