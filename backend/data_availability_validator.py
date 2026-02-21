"""
Data availability validation utilities for safe statistic generation.
"""

from typing import Any, Dict, List, Optional


class DataAvailabilityValidator:
    """Validate if specific statistic types can be generated safely."""

    MIN_SAMPLE_SIZES = {
        "win_rate": 5,
        "average_compensation": 5,
        "precedent_analysis": 10,
        "trend_analysis": 10,
        "comparative_study": 20,
    }

    def __init__(self, case_repository: Optional[Any] = None):
        self.case_repo = case_repository

    def _count_cases(self, case_filter: Optional[Dict[str, str]] = None) -> int:
        if self.case_repo and hasattr(self.case_repo, "count_cases"):
            return int(self.case_repo.count_cases(filter=case_filter))
        return int((case_filter or {}).get("available_cases", 0))

    def validate_statistic_generation(
        self, statistic_type: str, case_filter: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        required_count = self.MIN_SAMPLE_SIZES.get(statistic_type)
        if required_count is None:
            return {
                "can_generate": False,
                "available_cases": self._count_cases(case_filter),
                "required_cases": 0,
                "shortfall": 0,
                "warning": f"Unknown statistic type: {statistic_type}",
            }

        available_count = self._count_cases(case_filter)
        can_generate = available_count >= required_count
        return {
            "can_generate": can_generate,
            "available_cases": available_count,
            "required_cases": required_count,
            "shortfall": max(0, required_count - available_count),
            "warning": None
            if can_generate
            else (
                f"Insufficient data: only {available_count} cases available for "
                f"{statistic_type}, {required_count} required."
            ),
        }

    def get_available_statistics(
        self, case_filter: Optional[Dict[str, str]] = None
    ) -> List[str]:
        available: List[str] = []
        for stat_type in self.MIN_SAMPLE_SIZES:
            if self.validate_statistic_generation(stat_type, case_filter)["can_generate"]:
                available.append(stat_type)
        return available

    def generate_data_report(
        self, case_filter: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        total = self._count_cases(case_filter)
        possible = self.get_available_statistics(case_filter)
        impossible = {
            stat: minimum
            for stat, minimum in self.MIN_SAMPLE_SIZES.items()
            if stat not in possible
        }
        recommendations: List[str] = []
        if total == 0:
            recommendations.append("No similar cases available for statistical analysis.")
        elif total < 5:
            recommendations.append("Very limited case data; statistical claims are suppressed.")
        elif total < 10:
            recommendations.append("Moderate data only; broad trend claims should be cautious.")

        return {
            "total_cases_available": total,
            "filter_applied": case_filter,
            "statistics_possible": possible,
            "statistics_impossible": impossible,
            "recommendations": recommendations,
        }

