"""Read-only HID report-descriptor summarization."""

from __future__ import annotations

from collections import defaultdict


def summarize_report_descriptor(descriptor: bytes) -> dict[str, object]:
    """Return report IDs and byte sizes without interpreting vendor semantics."""
    totals: dict[str, dict[int, int]] = {
        "input": defaultdict(int), "output": defaultdict(int), "feature": defaultdict(int)
    }
    report_size = report_count = report_id = 0
    stack: list[tuple[int, int, int]] = []
    index = 0
    while index < len(descriptor):
        prefix = descriptor[index]
        index += 1
        if prefix == 0xFE:  # Long item.
            if index + 2 > len(descriptor):
                break
            length = descriptor[index]
            index += 2 + length
            continue
        size_code = prefix & 0x03
        size = 4 if size_code == 3 else size_code
        if index + size > len(descriptor):
            break
        value = int.from_bytes(descriptor[index:index + size], "little") if size else 0
        index += size
        item_type = (prefix >> 2) & 0x03
        tag = (prefix >> 4) & 0x0F
        if item_type == 1:  # Global item.
            if tag == 7:
                report_size = value
            elif tag == 8:
                report_id = value
            elif tag == 9:
                report_count = value
            elif tag == 10:
                stack.append((report_size, report_count, report_id))
            elif tag == 11 and stack:
                report_size, report_count, report_id = stack.pop()
        elif item_type == 0 and tag in {8, 9, 11}:  # Input, Output, Feature.
            kind = {8: "input", 9: "output", 11: "feature"}[tag]
            totals[kind][report_id] += report_size * report_count

    def rows(kind: str) -> list[dict[str, int]]:
        return [
            {
                "report_id": rid,
                "size_bytes": (bits + 7) // 8 + (1 if rid else 0),
                "payload_bits": bits,
            }
            for rid, bits in sorted(totals[kind].items())
        ]

    return {
        "report_ids": sorted({rid for values in totals.values() for rid in values}),
        "input_reports": rows("input"),
        "output_reports": rows("output"),
        "feature_reports": rows("feature"),
    }
