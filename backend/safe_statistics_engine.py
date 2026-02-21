"""
Safe statistics engine that refuses low-sample statistical outputs.
"""

import statistics
from typing import Any, Dict, Optional

from data_availability_validator import DataAvailabilityValidator


class SafeStatisticsEngine:
    """Generate validated statistics from a case repository."""

    def __init__(self, case_repository: Any):
        self.case_repo = case_repository
        self.validator = DataAvailabilityValidator(case_repository)

    def calculate_win_rate(
        self, case_filter: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        validation = self.validator.validate_statistic_generation("win_rate", case_filter)
        if not validation["can_generate"]:
            return {
                "success": False,
                "available_cases": validation["available_cases"],
                "required_cases": validation["required_cases"],
                "warning": validation["warning"],
                "recommendation": "Insufficient data for reliable win-rate calculation.",
            }

        cases = self.case_repo.get_cases(filter=case_filter)
        total = len(cases)
        wins = sum(1 for case in cases if case.get("outcome") == "won")
        if total == 0:
            return {"success": False, "warning": "No case outcome data available."}

        rate = wins / total
        return {
            "success": True,
            "win_rate": rate,
            "wins": wins,
            "total_cases": total,
            "sample_size": total,
            "confidence": self._calculate_confidence(total),
        }

    def calculate_average_compensation(
        self, case_filter: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        validation = self.validator.validate_statistic_generation(
            "average_compensation", case_filter
        )
        if not validation["can_generate"]:
            return {
                "success": False,
                "available_cases": validation["available_cases"],
                "required_cases": validation["required_cases"],
                "warning": validation["warning"],
                "recommendation": "Insufficient data for reliable compensation analysis.",
            }

        cases = self.case_repo.get_cases(filter=case_filter)
        amounts = []
        for case in cases:
            value = case.get("compensation_awarded")
            if isinstance(value, (int, float)) and value > 0:
                amounts.append(float(value))

        if not amounts:
            return {
                "success": False,
                "warning": "No compensation data available in cases.",
                "cases_analyzed": len(cases),
                "cases_with_compensation": 0,
            }

        return {
            "success": True,
            "average_compensation": statistics.mean(amounts),
            "median_compensation": statistics.median(amounts),
            "sample_size": len(amounts),
            "total_cases_with_data": len(cases),
            "confidence": self._calculate_confidence(len(amounts)),
        }

    def _calculate_confidence(self, sample_size: int) -> Dict[str, Any]:
        if sample_size >= 20:
            level = "high"
        elif sample_size >= 10:
            level = "moderate"
        elif sample_size >= 5:
            level = "low"
        else:
            level = "insufficient"
        margin = 1.96 / (sample_size ** 0.5) if sample_size > 0 else None
        return {
            "sample_size": sample_size,
            "confidence_level": level,
            "margin_of_error": margin,
        }

