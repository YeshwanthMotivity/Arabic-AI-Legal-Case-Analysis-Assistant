"""
Deterministic Query Engine for Interactive Legal Panel.

Routes structured user queries to specific analysis outputs without
using generative AI, ensuring safety and explainability.
"""

import logging

from models import AnalyzeResponse, QueryResponse

logger = logging.getLogger(__name__)

MIN_SAMPLE_FOR_STATS = 5


def process_query(query_type: str, analysis_data: AnalyzeResponse) -> QueryResponse:
    """Process a structured query from precomputed analysis."""
    logger.info("Processing query: %s", query_type)

    if query_type == "outcome":
        rec = analysis_data.recommendation
        if not rec:
            return QueryResponse(
                answer="No recommendation is available for this case.",
                type="text",
                source="recommendation_engine",
            )

        direction_map = {
            "plaintiff_likely": "Plaintiff outcome appears likely.",
            "defendant_likely": "Defendant-favoring outcome appears likely.",
            "uncertain": "Outcome is uncertain and requires more evidence.",
            "insufficient_data": "Insufficient data for outcome prediction.",
        }
        answer = direction_map.get(rec.direction, "Unknown direction")
        confidence_pct = int(rec.confidence * 100)
        return QueryResponse(
            answer=f"{answer} (Confidence: {confidence_pct}%)",
            type="text",
            source="recommendation_engine",
            data={"direction": rec.direction, "confidence": rec.confidence},
        )

    if query_type == "principles":
        principles = analysis_data.legal_principles
        if not principles:
            return QueryResponse(
                answer="No legal principles were extracted.",
                type="text",
                source="legal_principles_engine",
            )

        principle_names = [f"- {p.name_ar} ({p.source_section})" for p in principles[:5]]
        answer = "Applicable legal principles:\n" + "\n".join(principle_names)
        return QueryResponse(
            answer=answer,
            type="list",
            source="legal_principles_engine",
            data={"principles": [p.dict() for p in principles]},
        )

    if query_type == "similar_cases":
        trends = analysis_data.trends
        if not trends:
            return QueryResponse(
                answer="No sufficient similar precedents were found.",
                type="text",
                source="trend_analyzer",
            )

        if trends.sample_size < MIN_SAMPLE_FOR_STATS or trends.decided_cases < MIN_SAMPLE_FOR_STATS:
            return QueryResponse(
                answer=(
                    "Similar cases were found, but sample size is too small "
                    "for statistically reliable win-rate reporting."
                ),
                type="text",
                source="trend_analyzer",
                data={
                    "sample_size": trends.sample_size,
                    "decided_cases": trends.decided_cases,
                    "required_sample_size": MIN_SAMPLE_FOR_STATS,
                },
            )

        return QueryResponse(
            answer=(
                f"Found {trends.sample_size} similar precedents. "
                f"Plaintiff-favoring outcome rate: {trends.plaintiff_win_rate}%."
            ),
            type="stats",
            source="trend_analyzer",
            data=trends.dict(),
        )

    if query_type == "compensation":
        trends = analysis_data.trends
        if (
            not trends
            or trends.average_compensation == 0
            or trends.compensation_count < MIN_SAMPLE_FOR_STATS
        ):
            return QueryResponse(
                answer=(
                    "Insufficient compensation data for a reliable statistical summary."
                ),
                type="text",
                source="trend_analyzer",
            )

        avg = "{:,}".format(int(trends.average_compensation))
        max_comp = "{:,}".format(
            int(max(trends.compensation_range.values()) if trends.compensation_range else 0)
        )
        return QueryResponse(
            answer=(
                f"Average compensation in similar cases: {avg} SAR.\n"
                f"Maximum recorded compensation: {max_comp} SAR."
            ),
            type="stats",
            source="trend_analyzer",
            data={"average": trends.average_compensation},
        )

    if query_type == "confidence":
        rec = analysis_data.recommendation
        if not rec:
            return QueryResponse(answer="Unavailable.", type="text", source="system")
        return QueryResponse(
            answer=(
                f"Reliability level: {rec.reliability}.\n"
                f"Analysis is based on {rec.based_on_sample_size} precedent cases."
            ),
            type="text",
            source="recommendation_engine",
            data={"reliability": rec.reliability},
        )

    return QueryResponse(answer="Unknown query type.", type="error", source="system")

