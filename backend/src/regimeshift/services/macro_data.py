import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

import httpx

from regimeshift.domain.models import MacroQuad, MacroQuadAssessment

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
_cache: tuple[datetime, MacroQuadAssessment] | None = None


def unavailable_macro(reason: str) -> MacroQuadAssessment:
    return MacroQuadAssessment(
        quadrant=MacroQuad.UNAVAILABLE,
        label="Macro data unavailable",
        source="Federal Reserve Bank of St. Louis (FRED)",
        status="unavailable",
        confidence=0,
        rationale=reason,
    )


def _series(client: httpx.Client, series: str) -> list[tuple[datetime, float]]:
    response = client.get(FRED_CSV.format(series=series))
    response.raise_for_status()
    rows = []
    for row in csv.DictReader(StringIO(response.text)):
        value = row.get(series)
        date = row.get("DATE") or row.get("observation_date")
        if not value or value == "." or not date:
            continue
        rows.append((datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC), float(value)))
    return rows


def _year_over_year(
    values: list[tuple[datetime, float]], periods: int
) -> list[tuple[datetime, float]]:
    return [
        (values[index][0], values[index][1] / values[index - periods][1] - 1)
        for index in range(periods, len(values))
    ]


def get_macro_quad(*, force: bool = False) -> MacroQuadAssessment:
    global _cache
    now = datetime.now(UTC)
    if not force and _cache:
        cache_ttl = timedelta(hours=6) if _cache[1].status == "live" else timedelta(minutes=5)
        if now - _cache[0] < cache_ttl:
            return _cache[1]
    try:
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            gdp = _year_over_year(_series(client, "GDPC1"), 4)
            cpi = _year_over_year(_series(client, "CPIAUCSL"), 12)
        if len(gdp) < 2 or len(cpi) < 4:
            raise ValueError("FRED returned insufficient GDP/CPI history")
        growth_accelerating = gdp[-1][1] > gdp[-2][1]
        inflation_accelerating = cpi[-1][1] > cpi[-4][1]
        if growth_accelerating and not inflation_accelerating:
            quadrant, label = MacroQuad.QUAD_I, "Growth up / inflation down"
        elif growth_accelerating and inflation_accelerating:
            quadrant, label = MacroQuad.QUAD_II, "Growth up / inflation up"
        elif not growth_accelerating and inflation_accelerating:
            quadrant, label = MacroQuad.QUAD_III, "Growth down / inflation up"
        else:
            quadrant, label = MacroQuad.QUAD_IV, "Growth down / inflation down"
        assessment = MacroQuadAssessment(
            quadrant=quadrant,
            label=label,
            real_gdp_yoy=round(gdp[-1][1], 4),
            cpi_yoy=round(cpi[-1][1], 4),
            growth_accelerating=growth_accelerating,
            inflation_accelerating=inflation_accelerating,
            data_as_of=max(gdp[-1][0], cpi[-1][0]),
            source="FRED GDPC1 + CPIAUCSL",
            status="live",
            confidence=0.78,
            rationale=(
                f"Real GDP YoY is {gdp[-1][1]:.1%} and "
                f"CPI YoY is {cpi[-1][1]:.1%}; acceleration uses the prior GDP quarter "
                "and a three-month CPI comparison."
            ),
        )
    except Exception as error:
        assessment = unavailable_macro(f"Macro data request failed: {error}")
    _cache = (now, assessment)
    return assessment
