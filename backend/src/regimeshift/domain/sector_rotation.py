from regimeshift.domain.models import (
    PricePoint,
    RotationPhase,
    RotationSignal,
    SectorPerformance,
    SectorRotationAssessment,
)

SECTOR_UNIVERSE = {
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLK": "Technology",
    "XLU": "Utilities",
}

CYCLICAL_SECTORS = {"XLC", "XLY", "XLE", "XLF", "XLI", "XLB", "XLK"}
DEFENSIVE_SECTORS = {"XLP", "XLV", "XLU"}


def _period_return(points: list[PricePoint], sessions: int) -> float:
    return (points[-1].close / points[-(sessions + 1)].close) - 1


class SectorRotationEngine:
    minimum_points = 64
    benchmark_symbol = "SPY"

    def assess(self, histories: dict[str, list[PricePoint]]) -> SectorRotationAssessment:
        required_symbols = {self.benchmark_symbol, *SECTOR_UNIVERSE}
        missing = sorted(required_symbols - histories.keys())
        if missing:
            raise ValueError(f"Sector rotation is missing history for: {', '.join(missing)}")

        for symbol in required_symbols:
            if len(histories[symbol]) < self.minimum_points:
                raise ValueError(
                    f"Sector rotation requires {self.minimum_points} price points for {symbol}"
                )

        benchmark_1m = _period_return(histories[self.benchmark_symbol], 21)
        benchmark_3m = _period_return(histories[self.benchmark_symbol], 63)
        rows: list[dict[str, object]] = []

        for symbol, name in SECTOR_UNIVERSE.items():
            one_month = _period_return(histories[symbol], 21)
            three_month = _period_return(histories[symbol], 63)
            relative_1m = one_month - benchmark_1m
            relative_3m = three_month - benchmark_3m
            score = (relative_1m * 0.6) + (relative_3m * 0.4)
            if relative_1m >= 0 and relative_3m >= 0:
                phase = RotationPhase.LEADING
            elif relative_1m >= 0:
                phase = RotationPhase.IMPROVING
            elif relative_3m >= 0:
                phase = RotationPhase.WEAKENING
            else:
                phase = RotationPhase.LAGGING
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "one_month_return": one_month,
                    "three_month_return": three_month,
                    "relative_strength_1m": relative_1m,
                    "relative_strength_3m": relative_3m,
                    "rotation_score": score,
                    "phase": phase,
                }
            )

        rows.sort(key=lambda row: float(row["rotation_score"]), reverse=True)
        sectors = [
            SectorPerformance(
                rank=rank,
                symbol=str(row["symbol"]),
                name=str(row["name"]),
                one_month_return=round(float(row["one_month_return"]), 4),
                three_month_return=round(float(row["three_month_return"]), 4),
                relative_strength_1m=round(float(row["relative_strength_1m"]), 4),
                relative_strength_3m=round(float(row["relative_strength_3m"]), 4),
                rotation_score=round(float(row["rotation_score"]), 4),
                phase=RotationPhase(row["phase"]),
            )
            for rank, row in enumerate(rows, start=1)
        ]
        breadth = sum(sector.rotation_score > 0 for sector in sectors) / len(sectors)
        top_symbols = {sector.symbol for sector in sectors[:3]}
        cyclical_leaders = len(top_symbols & CYCLICAL_SECTORS)
        defensive_leaders = len(top_symbols & DEFENSIVE_SECTORS)

        if cyclical_leaders >= 2 and breadth >= 0.55:
            signal = RotationSignal.RISK_ON
        elif defensive_leaders >= 2 or breadth <= 0.35:
            signal = RotationSignal.DEFENSIVE
        else:
            signal = RotationSignal.MIXED

        dispersion = sectors[0].rotation_score - sectors[-1].rotation_score
        confidence = min(0.94, 0.52 + abs(breadth - 0.5) * 0.55 + dispersion * 1.5)
        leaders = [sector.symbol for sector in sectors[:3]]
        laggards = [sector.symbol for sector in sectors[-3:]]
        rationale = (
            f"{breadth:.0%} of sectors outperform SPY on the weighted 1M/3M signal; "
            f"leaders are {', '.join(leaders)} and laggards are {', '.join(laggards)}."
        )
        return SectorRotationAssessment(
            as_of=histories[self.benchmark_symbol][-1].timestamp,
            signal=signal,
            confidence=round(confidence, 3),
            breadth=round(breadth, 3),
            leaders=leaders,
            laggards=laggards,
            sectors=sectors,
            rationale=rationale,
        )
