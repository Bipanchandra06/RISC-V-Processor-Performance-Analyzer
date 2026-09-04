"""Formatting helpers for downloadable simulator results."""
from __future__ import annotations

import csv
import io
def _core_name(name: str) -> str:
    return name.replace("_", " ").title()


def hazard_rows(payload: dict) -> list[dict]:
    """Convert trace events into a compact, cycle-indexed hazard table."""
    rows = []
    for core, cycles in payload.get("traces", {}).items():
        for item in cycles:
            for event in item.get("events", []):
                event_lower = event.lower()
                if "load-use stall" in event_lower:
                    rows.append({"Processor": _core_name(core), "Cycle": item.get("cycle"),
                                 "Hazard": "Load-use data hazard", "Resolution": "Pipeline stall",
                                 "Stall cycles": 1, "Detail": event})
                elif "branch/jump flush" in event_lower:
                    rows.append({"Processor": _core_name(core), "Cycle": item.get("cycle"),
                                 "Hazard": "Control hazard", "Resolution": "Flush and redirect PC",
                                 "Stall cycles": 0, "Detail": event})
                elif event_lower.startswith("forward"):
                    rows.append({"Processor": _core_name(core), "Cycle": item.get("cycle"),
                                 "Hazard": "Data dependency", "Resolution": "Operand forwarding",
                                 "Stall cycles": 0, "Detail": event})
    return rows


def predictor_rows(payload: dict) -> list[dict]:
    rows = []
    for core, stats in payload.get("predictors", {}).get("branch", {}).items():
        # Branch prediction is a pipeline feature; keep the user-facing
        # statistics focused on the five-stage speculative execution model.
        if core != "five_stage":
            continue
        rows.append({"Processor": _core_name(core), "Mode": stats.get("mode", "-"),
                     "Branches": stats.get("branches", 0), "Predictions": stats.get("predictions", 0),
                     "Mispredictions": stats.get("mispredictions", 0),
                     "Accuracy": stats.get("accuracy", 1.0)})
    return rows


def cache_rows(payload: dict) -> list[dict]:
    rows = []
    for core, values in payload.get("cores", {}).items():
        for cache_key, label in (("instruction_cache", "Instruction"), ("data_cache", "Data")):
            stats = values.get(cache_key)
            if not stats:
                continue
            for event in stats.get("events", []):
                rows.append({"Processor": _core_name(core), "Cache": label,
                             "Cycle": event.get("cycle", "-"), "Address/Block": event.get("block_number", "-"),
                             "Type": event.get("access_type", "-"),
                             "Result": "Hit" if event.get("hit") else "Miss",
                             "Set": event.get("set_index", "-"), "Tag": event.get("tag", "-"),
                             "Penalty": event.get("penalty_cycles", 0),
                             "Evicted block": event.get("evicted_block", "-")})
    return rows


def _summary_rows(payload: dict) -> list[dict]:
    rows = []
    for core, values in payload.get("cores", {}).items():
        rows.append({"Processor": _core_name(core), "Base cycles": values.get("base_cycles", values.get("cycles", 0)),
                     "Retired instructions": values.get("retired_instructions", 0),
                     "Cache penalty cycles": values.get("cache_penalty_cycles", 0),
                     "Effective cycles": values.get("effective_cycles", values.get("cycles", 0)),
                     "Base CPI": values.get("base_cpi", values.get("cpi", 0)),
                     "Effective CPI": values.get("effective_cpi", values.get("cpi", 0)),
                     "Stalls": values.get("stalls", 0), "Forwarding events": values.get("forwarding_events", 0),
                     "Branch flushes": values.get("branch_flushes", 0)})
    return rows


def csv_bytes(payload: dict) -> bytes:
    """Create one CSV containing summary, predictor, hazard, and cache sections."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    for title, rows in (("PERFORMANCE SUMMARY", _summary_rows(payload)),
                        ("BRANCH PREDICTOR STATISTICS", predictor_rows(payload)),
                        ("HAZARDS AND STALLS BY CYCLE", hazard_rows(payload)),
                        ("CACHE ACCESS TRACE", cache_rows(payload))):
        writer.writerow([title])
        if rows:
            writer.writerow(list(rows[0]))
            writer.writerows([list(row.values()) for row in rows])
        writer.writerow([])
    return output.getvalue().encode("utf-8")


def _pdf_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_bytes(payload: dict) -> bytes:
    """Create a dependency-free, readable PDF report from the structured result."""
    lines = ["RISC-V Processor Performance Analyzer", "", "PERFORMANCE SUMMARY"]
    for row in _summary_rows(payload):
        lines.append(" | ".join(f"{key}: {value}" for key, value in row.items()))
    lines += ["", "BRANCH PREDICTOR STATISTICS"]
    for row in predictor_rows(payload):
        lines.append(" | ".join(f"{key}: {value}" for key, value in row.items()))
    lines += ["", "HAZARDS AND STALLS BY CYCLE"]
    for row in hazard_rows(payload):
        lines.append(" | ".join(f"{key}: {value}" for key, value in row.items()))
    lines += ["", "CACHE ACCESS TRACE"]
    for row in cache_rows(payload):
        lines.append(" | ".join(f"{key}: {value}" for key, value in row.items()))
    if not lines:
        lines = ["No results available."]

    pages = [lines[i:i + 42] for i in range(0, len(lines), 42)]
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = []
    for index, page_lines in enumerate(pages):
        page_id = 3 + index * 2
        content_id = page_id + 1
        page_ids.append(page_id)
        content = ["BT", "/F1 8 Tf", "36 760 Td", "10 TL"]
        for line in page_lines:
            content.append(f"({_pdf_escape(line[:180])}) Tj T*")
        content.append("ET")
        stream = "\n".join(content).encode("latin-1", errors="replace")
        objects.extend([
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {3 + len(pages) * 2} 0 R >> >> /Contents {content_id} 0 R >>".encode(),
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ])
    objects.insert(1, (f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>").encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    result.extend("".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:]).encode())
    result.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(result)
