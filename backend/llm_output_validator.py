"""
Rule-based validator for suspicious statistical claims in generated text.
"""

import re
from typing import Any, Dict, List


class LLMOutputValidator:
    """Validate and flag potentially hallucinated statistics."""

    SUSPICIOUS_PATTERNS = [
        r"(?:in|shows|results|cases show)\s+(\d+%|\d+\s*percent)",
        r"(?:average|typically|usually|generally|most)\s+(?:cases|judges|courts)",
        r"(?:win rate|success rate|conviction rate):\s+\d+%",
        r"(?:average|typical)\s+(?:compensation|damages|award):\s*\$?\d[\d,]*",
        r"(?:precedent|case law)\s+shows",
    ]

    def __init__(self, data_availability: Dict[str, Any] = None):
        self.data_available = data_availability or {}

    def validate_output(self, output_text: str) -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []
        for pattern in self.SUSPICIOUS_PATTERNS:
            matches = re.findall(pattern, output_text, re.IGNORECASE)
            if matches:
                issues.append(
                    {
                        "type": "suspicious_statistic",
                        "pattern": pattern,
                        "matches": matches,
                    }
                )

        issues.extend(self._check_red_flags(output_text))
        return {
            "is_valid": len(issues) == 0,
            "issues_found": issues,
            "issue_count": len(issues),
            "recommendations": self._get_recommendations(issues),
            "cleaned_text": self._clean_suspicious_content(output_text),
        }

    def _check_red_flags(self, text: str) -> List[Dict[str, Any]]:
        flags: List[Dict[str, Any]] = []
        lower = text.lower()
        if "most cases" in lower and "based on" not in lower:
            flags.append(
                {
                    "type": "unjustified_generalization",
                    "phrase": "most cases",
                    "issue": "Generalization without explicit data support.",
                }
            )

        count_match = re.search(r"(\d+(?:,\d{3})*)\s*(?:cases|judgments)", text, re.IGNORECASE)
        if count_match:
            claimed = int(count_match.group(1).replace(",", ""))
            available = int(self.data_available.get("total_cases_available", 0))
            if claimed > available:
                flags.append(
                    {
                        "type": "impossible_case_count",
                        "claimed": claimed,
                        "available": available,
                        "issue": f"Claims {claimed} cases but only {available} available.",
                    }
                )
        return flags

    def _get_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        recommendations: List[str] = []
        if any(item["type"] == "suspicious_statistic" for item in issues):
            recommendations.append("Verify every statistic has supporting data and sample size.")
        if any(item["type"] == "unjustified_generalization" for item in issues):
            recommendations.append("Replace unsupported generalizations with explicit limitations.")
        if any(item["type"] == "impossible_case_count" for item in issues):
            recommendations.append("Correct case counts to available dataset size.")
        return recommendations

    def _clean_suspicious_content(self, text: str) -> str:
        cleaned = text
        for pattern in self.SUSPICIOUS_PATTERNS:
            for match in re.finditer(pattern, cleaned, re.IGNORECASE):
                phrase = match.group(0)
                cleaned = cleaned.replace(phrase, f"[SUSPICIOUS: {phrase}]")
        return cleaned

