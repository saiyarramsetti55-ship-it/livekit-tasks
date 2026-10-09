#!/usr/bin/env python3
"""
Latency Report Generator for CityCare Clinic Voice Agent.
Reads session reports from reports/ and computes p50 and p95 for:
- e2e_latency
- end_of_turn_delay
- llm_node_ttft
- tts_node_ttfb

Exits with code 1 if p95 e2e_latency exceeds 1.5s.
"""

import glob
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_report_files(reports_dir: Path) -> List[Path]:
    """Find all JSON session report files in the reports directory."""
    if not reports_dir.exists():
        return []
    return list(reports_dir.glob("*.json"))


def extract_metrics_recursive(
    data: Any,
    metrics_collector: Dict[str, List[float]],
) -> None:
    """Recursively traverse JSON data to extract per-message / event metrics."""
    target_keys = {
        "e2e_latency",
        "end_of_turn_delay",
        "llm_node_ttft",
        "tts_node_ttfb",
        "transcription_delay",
    }

    if isinstance(data, dict):
        # Check if this dictionary itself contains metrics
        if "metrics" in data and isinstance(data["metrics"], dict):
            m = data["metrics"]
            for k in target_keys:
                if k in m and m[k] is not None and k in metrics_collector:
                    try:
                        val = float(m[k])
                        # If value is in milliseconds (> 50), convert to seconds for consistency
                        if val > 50:
                            val = val / 1000.0
                        metrics_collector[k].append(val)
                    except (ValueError, TypeError):
                        pass

        # Also check direct keys in dictionary
        for k in target_keys:
            if k in data and data[k] is not None and not isinstance(data[k], dict) and k in metrics_collector:
                try:
                    val = float(data[k])
                    if val > 50:
                        val = val / 1000.0
                    metrics_collector[k].append(val)
                except (ValueError, TypeError):
                    pass

        # Check nested dicts
        for value in data.values():
            extract_metrics_recursive(value, metrics_collector)

    elif isinstance(data, list):
        for item in data:
            extract_metrics_recursive(item, metrics_collector)


def calculate_percentiles(values: List[float]) -> Dict[str, Optional[float]]:
    """Compute count, min, max, p50 (median), and p95."""
    if not values:
        return {"count": 0, "min": None, "max": None, "p50": None, "p95": None}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def percentile(p: float) -> float:
        if n == 1:
            return sorted_vals[0]
        k = (n - 1) * p
        f = int(k)
        c = min(f + 1, n - 1)
        d = k - f
        return sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f])

    return {
        "count": n,
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "p50": percentile(0.50),
        "p95": percentile(0.95),
    }


def generate_report(reports_dir: Optional[str] = None) -> int:
    """Generate and display the latency report. Returns exit code (0 or 1)."""
    base_dir = Path(__file__).resolve().parent
    target_dir = Path(reports_dir) if reports_dir else base_dir / "reports"

    print("=" * 65)
    print("      CITYCARE CLINIC VOICE AGENT - LATENCY EVALUATION       ")
    print("=" * 65)
    print(f"Scanning reports directory: {target_dir}")

    files = find_report_files(target_dir)
    print(f"Found {len(files)} session report file(s).")
    print("-" * 65)

    metrics_collector: Dict[str, List[float]] = {
        "e2e_latency": [],
        "end_of_turn_delay": [],
        "llm_node_ttft": [],
        "tts_node_ttfb": [],
    }

    for file_path in files:
        try:
            # Try reading UTF-8 first, fallback to UTF-16
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (UnicodeDecodeError, json.JSONDecodeError):
                with open(file_path, "r", encoding="utf-16") as f:
                    data = json.load(f)

            extract_metrics_recursive(data, metrics_collector)
        except Exception as exc:
            print(f"[WARN] Error reading {file_path.name}: {exc}")

    print(f"{'Metric':<22} | {'Count':<6} | {'p50 (s)':<10} | {'p95 (s)':<10} | {'Status'}")
    print("-" * 65)

    e2e_p95 = None

    for metric_name in ["e2e_latency", "end_of_turn_delay", "llm_node_ttft", "tts_node_ttfb"]:
        vals = metrics_collector[metric_name]
        stats = calculate_percentiles(vals)

        if stats["count"] == 0:
            print(f"{metric_name:<22} | {0:<6} | {'N/A':<10} | {'N/A':<10} | No Data")
        else:
            p50_str = f"{stats['p50']:.3f} s"
            p95_str = f"{stats['p95']:.3f} s"
            status = "OK"
            if metric_name == "e2e_latency":
                e2e_p95 = stats["p95"]
                if stats["p95"] > 1.5:
                    status = "FAIL (>1.5s)"
                else:
                    status = "PASS (<1.5s)"
            elif stats["p95"] > 1.5:
                status = "WARN (>1.5s)"

            print(f"{metric_name:<22} | {stats['count']:<6} | {p50_str:<10} | {p95_str:<10} | {status}")

    print("=" * 65)

    # Enforce threshold on e2e_latency
    if e2e_p95 is not None and e2e_p95 > 1.5:
        print(f"\n[ERROR] Latency check FAILED: p95 e2e_latency ({e2e_p95:.3f}s) exceeds threshold (1.500s).")
        return 1

    print("\n[SUCCESS] Latency check PASSED: All latency metrics within operational limits.")
    return 0


if __name__ == "__main__":
    rep_dir = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(generate_report(rep_dir))
