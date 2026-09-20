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
PL_ADAPTER_VERSION = 1
BEAM_ADAPTER_VERSION = 1
SPECTRUM_ADAPTER_VERSION = 1

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


def _optional_int(value, label):
    _require(value is None or (isinstance(value, int) and not isinstance(value, bool)),
             f"{label} must be an integer or absent")
    return value


def adapt_pl(payload):
    """Map a PL-Analyzer *_PL_metrics.json (schema 1) to a record.

    These are Presentation semantics: half-height FWHM above an estimated
    baseline after light smoothing. The adapter keeps that label and the
    metric_semantics text; it must not feed these numbers into a generic FWHM
    field. sample_name is a display name, not a stable sample ID; excitation
    and temperature move into conditions when the source recorded them.
    """
    _require(isinstance(payload, dict), "PL export must be a JSON object")
    schema = payload.get("schema_version")
    _require(schema == 1, f"Unsupported PL schema_version: {schema!r}; expected 1")
    metrics = payload.get("metrics")
    _require(isinstance(metrics, dict), "PL metrics must be an object")
    _require(metrics.get("algorithm_version") == 1,
             "Unsupported PL metrics algorithm_version; expected 1")
    semantics = payload.get("metric_semantics")
    _require(isinstance(semantics, str) and semantics.strip(),
             "PL export must keep its metric_semantics declaration")
    name = payload.get("sample_name")
    _require(isinstance(name, str) and name.strip(), "PL sample_name must be a nonempty string")
    metadata = payload.get("source_metadata", {})
    _require(isinstance(metadata, dict), "PL source_metadata must be an object")

    def condition(key):
        value = metadata.get(key)
        return value if isinstance(value, str) and value.strip() else None

    return {
        "adapter": "pl",
        "adapter_version": PL_ADAPTER_VERSION,
        "source_tool": "PL-Analyzer",
        "source_schema_version": schema,
        "source_sample_id": name,
        "source_input": _text_provenance(payload, "PL"),
        "conditions": {
            "excitation_laser": condition("Laser"),
            "excitation_power": condition("Power"),
            "temperature": condition("Temperature"),
        },
        "method": {
            "name": "presentation-half-height-fwhm",
            "semantics": semantics,
            "smoothing_sigma_points": _number(metrics["smoothing_sigma_points"],
                                              "PL smoothing_sigma_points"),
        },
        "results": {
            "peak_wavelength_nm": _number(metrics["peak_wavelength_nm"], "PL peak_wavelength_nm"),
            "presentation_fwhm_nm": _number(metrics["presentation_fwhm_nm"],
                                            "PL presentation_fwhm_nm"),
            "peak_energy_ev": _number(metrics["peak_energy_ev"], "PL peak_energy_ev"),
            "snr_estimate": _number(metrics["snr_estimate"], "PL snr_estimate"),
        },
        "warnings": list(metrics.get("quality_flags") or []),
    }


def _text_provenance(payload, tool):
    """Keep the raw spectrum file name the source tool recorded, if any."""
    file_name = payload.get("source_file")
    if file_name is None:
        return None
    _require(isinstance(file_name, str) and file_name.strip(),
             f"{tool} source_file must be a nonempty string")
    return {"file": file_name}


def adapt_beam(payload):
    """Map a laser-beam-qa result_summary.json to a record.

    The current export has no top-level schema_version, so the adapter pins the
    known 0.1.0 layout by detection (run_id + gaussian-caustic divergence
    fields) and states its own version. Incomplete scans stay records with an
    incomplete status — they are not promoted to passing results. Full/half
    angles and waist diameters are kept as separate named quantities.
    """
    _require(isinstance(payload, dict), "Beam export must be a JSON object")
    _require("schema_version" not in payload,
             "Beam export unexpectedly declares schema_version; update the beam adapter")
    for field in ("run_id", "sample_id", "scan_status", "full_angle_x_mrad"):
        _require(field in payload, f"Beam export is missing {field}; unknown format")
    divergence = payload.get("divergence_result", {})
    _require(isinstance(divergence, dict), "Beam divergence_result must be an object")
    model = divergence.get("model")
    _require(model in ("D(z)=sqrt(D0^2+S^2*(z-z0)^2)", "far_field_linear"),
             f"Unsupported beam fit model: {model!r}")
    status = payload.get("scan_status")
    _require(status in ("complete", "incomplete", "in_progress"),
             f"Unknown beam scan_status: {status!r}")

    def value(field):
        return _optional_number(payload.get(field), f"Beam {field}")

    return {
        "adapter": "beam",
        "adapter_version": BEAM_ADAPTER_VERSION,
        "source_tool": "laser-beam-qa",
        "source_schema_version": None,
        "source_software_version": None,
        "source_sample_id": payload.get("sample_id"),
        "source_input": None,
        "run_id": payload.get("run_id"),
        "conditions": {
            "scan_status": status,
            "measurement_status": payload.get("measurement_status"),
            "calibration_id": payload.get("calibration", {}).get("calibration_id")
            if isinstance(payload.get("calibration"), dict) else None,
        },
        "method": {
            "name": model,
            "fit_r2_x": value("fit_r2_x"),
            "fit_r2_y": value("fit_r2_y"),
            "valid_points_count": _optional_int(payload.get("valid_points_count"),
                                                "Beam valid_points_count"),
        },
        "results": {
            "full_angle_x_mrad": value("full_angle_x_mrad"),
            "full_angle_y_mrad": value("full_angle_y_mrad"),
            "half_angle_x_mrad": value("half_angle_x_mrad"),
            "half_angle_y_mrad": value("half_angle_y_mrad"),
            "waist_diameter_x_um": value("waist_diameter_x_um"),
            "waist_diameter_y_um": value("waist_diameter_y_um"),
        },
        "judgement": payload.get("final_judgement"),
        "warnings": [str(error.get("message") or error.get("error_code"))
                     for error in payload.get("error_list", [])
                     if isinstance(error, dict)] if status != "complete" else [],
    }


def adapt_spectrum(payload):
    """Map a spectral-analysis.json spacing screen (schema 0.1.0) to a record.

    The export has no stable device ID or temperature; the manifest must
    supply them. The adapter keeps the spacing-rule semantics (a screening
    rule, not mode-locking certification) and exposes per-threshold comb
    counts. Spacings and selected peaks stay in the source payload, not here.
    """
    _require(isinstance(payload, dict), "Spectral export must be a JSON object")
    schema = payload.get("schema_version")
    _require(schema == "0.1.0", f"Unsupported spectral schema_version: {schema!r}; expected '0.1.0'")
    method = payload.get("method")
    _require(method == "spectral-spacing-screen", f"Unsupported spectral method: {method!r}")
    parameters = payload.get("parameters")
    _require(isinstance(parameters, dict), "Spectral parameters must be an object")
    units = payload.get("units")
    _require(units == {"current": "mA", "bias": "V", "wavelength": "nm",
                       "power": "dBm", "spacing": "GHz"},
             "Unexpected spectral units block")
    points = payload.get("points")
    _require(isinstance(points, list) and points, "Spectral export needs at least one point")
    combs = {}
    first = points[0]
    first_current = _number(first["current"], "Spectral current")
    first_bias = _number(first["bias"], "Spectral bias")
    for point in points:
        _require(isinstance(point, dict) and isinstance(point.get("analyses"), dict),
                 "Each spectral point must carry an analyses object")
        current = _number(point["current"], "Spectral current")
        bias = _number(point["bias"], "Spectral bias")
        for key, analysis in point["analyses"].items():
            _require(isinstance(analysis, dict), "Spectral analyses entries must be objects")
            combs[f"{current:g}mA_{bias:g}V_{key}dB"] = {
                "comb_line_count": _optional_int(analysis.get("comb_line_count"),
                                                 "Spectral comb_line_count"),
                "spacing_rule_passed": analysis.get("spacing_rule_passed"),
                "center_wavelength_nm": _optional_number(analysis.get("center_wavelength_nm"),
                                                         "Spectral center_wavelength_nm"),
            }
    spacing_min = _number(parameters["spacing_min_GHz"], "Spectral spacing_min_GHz")
    spacing_max = _number(parameters["spacing_max_GHz"], "Spectral spacing_max_GHz")
    _require(spacing_min < spacing_max, "Spectral spacing range must be nonempty")
    warnings = []
    if len(points) > 1:
        warnings.append(f"Export contains {len(points)} condition points; "
                        "recorded conditions show the first point only")
    return {
        "adapter": "spectrum",
        "adapter_version": SPECTRUM_ADAPTER_VERSION,
        "source_tool": "laser-characterization-tools",
        "source_schema_version": schema,
        "source_sample_id": None,
        "source_input": {"files": [p["filename"] for p in points
                                   if isinstance(p.get("filename"), str)]} if points else None,
        "conditions": {
            "current_mA": first_current,
            "bias_V": first_bias,
        },
        "method": {
            "name": method,
            "spacing_min_GHz": spacing_min,
            "spacing_max_GHz": spacing_max,
            "screening_drop_dB": _number(parameters["screening_drop_dB"],
                                         "Spectral screening_drop_dB"),
            "thresholds_dB": [float(v) for v in parameters["thresholds_dB"]],
        },
        "results": {
            "comb_counts": combs,
            "point_count": len(points),
        },
        "warnings": warnings,
    }


ADAPTERS = {"liv": adapt_liv, "pl": adapt_pl, "beam": adapt_beam, "spectrum": adapt_spectrum}
