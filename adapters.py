"""Version-aware import adapters for source-tool exports. Standard library only.

Each adapter is a pure function: one exported payload in, one flat record out
with identity, conditions, method and key results. Values are taken as
published by the source tool — never recomputed, unit-converted or completed;
missing conditions stay missing. Adapters pin the source schema they support
and record their own version so imported records stay interpretable when
source formats evolve.
"""
from __future__ import annotations

import math
import re

LIV_ADAPTER_VERSION = 1

_SHA256 = re.compile(r"[0-9a-f]{64}")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, label):
    _require(isinstance(value, (int, float)) and not isinstance(value, bool)
             and math.isfinite(value), f"{label} must be a finite number")
    return float(value)


def _optional_number(value, label):
    return None if value is None else _number(value, label)


def _input_provenance(payload, tool):
    """Keep the raw-input file name and hash the source tool recorded, if any."""
    file_name, digest = payload.get("source_file"), payload.get("source_sha256")
    if file_name is None and digest is None:
        return None
    _require(isinstance(file_name, str) and file_name.strip(),
             f"{tool} source_file must be a nonempty string")
    _require(isinstance(digest, str) and _SHA256.fullmatch(digest),
             f"{tool} source_sha256 must be a lowercase 64-hex digest")
    return {"file": file_name, "sha256": digest}


def adapt_liv(payload):
    """Map a laser-characterization-tools analysis.json (schema 0.1.0) to a record.

    Accepts CW analysis only. The threshold stays labeled as a
    linear-extrapolation estimate over the recorded fit interval; a missing
    temperature stays None and must be supplemented by the manifest.
    """
    _require(isinstance(payload, dict), "LIV export must be a JSON object")
    schema = payload.get("schema_version")
    _require(schema == "0.1.0", f"Unsupported LIV schema_version: {schema!r}; expected '0.1.0'")
    method = payload.get("method")
    _require(method == "explicit-window-linear-extrapolation",
             f"Unsupported LIV method: {method!r}")
    mode = payload.get("measurement_mode")
    _require(mode == "CW", f"LIV export must be CW analysis, got {mode!r}")
    fit = payload.get("fit_range_mA")
    _require(isinstance(fit, list) and len(fit) == 2, "LIV fit_range_mA must be [lower, upper]")
    lower = _number(fit[0], "LIV fit lower bound")
    upper = _number(fit[1], "LIV fit upper bound")
    _require(lower < upper, "LIV fit lower bound must be below the upper bound")
    warnings = payload.get("warnings", [])
    _require(isinstance(warnings, list) and all(isinstance(item, str) for item in warnings),
             "LIV warnings must be a list of strings")
    sample_id = payload.get("sample_id")
    _require(sample_id is None or (isinstance(sample_id, str) and sample_id.strip()),
             "LIV sample_id must be a nonempty string or absent")
    return {
        "adapter": "liv",
        "adapter_version": LIV_ADAPTER_VERSION,
        "source_tool": "laser-characterization-tools",
        "source_schema_version": schema,
        "source_software_version": payload.get("software_version"),
        "source_sample_id": sample_id,
        "source_input": _input_provenance(payload, "LIV"),
        "conditions": {
            "measurement_mode": mode,
            "temperature_C": _optional_number(payload.get("temperature_C"), "LIV temperature_C"),
        },
        "method": {
            "name": method,
            "fit_range_mA": [lower, upper],
            "baseline_mW": _number(payload.get("baseline_mW"), "LIV baseline_mW"),
            "fit_r_squared": _optional_number(payload.get("fit_r_squared"), "LIV fit_r_squared"),
        },
        "results": {
            "threshold_estimate_mA": _number(payload.get("threshold_estimate_mA"),
                                             "LIV threshold_estimate_mA"),
            "slope_efficiency_mW_per_mA": _number(payload.get("slope_efficiency_mW_per_mA"),
                                                  "LIV slope_efficiency_mW_per_mA"),
            "max_power_mW": _number(payload.get("max_power_mW"), "LIV max_power_mW"),
        },
        "warnings": list(warnings),
    }


ADAPTERS = {"liv": adapt_liv}
