#!/usr/bin/env python3
"""Validate professor-workbook GEX metrics against 5-day forward SPX volatility.

This reads cached values from the Results1 sheet. It does not execute VBA and it
does not reproduce the metrics from raw Level3 chains.
"""

import argparse
import json
import math
import statistics
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(f"{NS}t")) for item in root]


def _sheet_path(archive: zipfile.ZipFile, title: str) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rel_id = next(
        sheet.attrib[f"{REL_NS}id"]
        for sheet in workbook.iter(f"{NS}sheet")
        if sheet.attrib["name"] == title
    )
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = next(
        rel.attrib["Target"]
        for rel in rels.iter(f"{PKG_NS}Relationship")
        if rel.attrib["Id"] == rel_id
    )
    return f"xl/{target.lstrip('/')}"


def _column(reference: str) -> str:
    return "".join(character for character in reference if character.isalpha())


def load_rows(path: Path) -> list[dict[str, float | str]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        sheet = _sheet_path(archive, "Results1")
        rows = []
        with archive.open(sheet) as stream:
            for _, element in ElementTree.iterparse(stream, events=("end",)):
                if element.tag != f"{NS}row":
                    continue
                values: dict[str, float | str] = {}
                for cell in element.findall(f"{NS}c"):
                    value = cell.find(f"{NS}v")
                    if value is None or value.text is None:
                        continue
                    raw: float | str = value.text
                    if cell.attrib.get("t") == "s":
                        raw = shared[int(raw)]
                    else:
                        raw = float(raw)
                    values[_column(cell.attrib["r"])] = raw
                if isinstance(values.get("A"), float) and isinstance(values.get("L"), float):
                    rows.append(values)
                element.clear()
    return rows


def correlation(xs: list[float], ys: list[float]) -> float:
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    denominator = math.sqrt(
        sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys)
    )
    return numerator / denominator if denominator else 0.0


def evaluate(rows: list[dict[str, float | str]]) -> dict[str, object]:
    observations = []
    for index in range(len(rows) - 5):
        closes = [float(rows[offset]["L"]) for offset in range(index, index + 6)]
        returns = [math.log(closes[i + 1] / closes[i]) for i in range(5)]
        rv5 = math.sqrt(sum(value**2 for value in returns) / 5)
        row = rows[index]
        observations.append(
            {
                "date": (
                    datetime(1899, 12, 30, tzinfo=UTC)
                    + timedelta(days=float(row["A"]))
                ).date(),
                "gex": float(row["B"]),
                "gex_plus": float(row["D"]),
                "giv": float(row["E"]),
                "crx": float(row["J"]),
                "rv5": rv5,
            }
        )
    split = int(len(observations) * 0.7)

    def stats(items: list[dict[str, object]]) -> dict[str, float]:
        rv = [float(item["rv5"]) for item in items]
        return {
            metric: round(correlation([float(item[metric]) for item in items], rv), 4)
            for metric in ("gex", "gex_plus", "giv", "crx")
        }

    negative = [float(item["rv5"]) for item in observations if float(item["gex"]) < 0]
    positive = [float(item["rv5"]) for item in observations if float(item["gex"]) >= 0]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": "GEX_NN_Copy.xlsm cached Results1 values supplied by Ninh D. Nguyen, Ph.D.",
        "period": {
            "start": str(observations[0]["date"]),
            "end": str(observations[-1]["date"]),
            "observations": len(observations),
            "chronological_split": split,
        },
        "target": "5-session forward RMS daily log return",
        "correlations": {
            "full": stats(observations),
            "train_70pct": stats(observations[:split]),
            "holdout_30pct": stats(observations[split:]),
        },
        "gex_sign_regime": {
            "negative_days": len(negative),
            "positive_days": len(positive),
            "negative_avg_rv5": round(statistics.fmean(negative), 6),
            "positive_avg_rv5": round(statistics.fmean(positive), 6),
            "negative_to_positive_vol_ratio": round(
                statistics.fmean(negative) / statistics.fmean(positive), 3
            ),
        },
        "limitations": [
            "Uses workbook-produced metrics; it does not independently recompute Greeks or GEX.",
            "Cached workbook outputs may include methodology not visible in this repository.",
            "No option fills, slippage, or strategy P&L are modeled.",
            "GEX describes expected volatility structure, not price direction.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    result = evaluate(load_rows(args.workbook))
    rendered = json.dumps(result, indent=2)
    print(rendered)


if __name__ == "__main__":
    main()
