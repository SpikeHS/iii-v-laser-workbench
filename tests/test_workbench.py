import json
from pathlib import Path
import shutil
import tempfile
import unittest

from adapters import adapt_beam, adapt_liv, adapt_pl, adapt_spectrum
from workbench import load_project, main, render_report


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples", self.root / "example")
        self.path = self.root / "example/project.json"
        self.liv = next(record for record in json.loads(self.path.read_text(encoding="utf-8"))["measurements"]
                        if record["id"] == "LIV-001")

    def change(self, edit):
        project = json.loads(self.path.read_text(encoding="utf-8"))
        edit(project)
        self.path.write_text(json.dumps(project), encoding="utf-8")

    def record(self, project, snapshots):
        return next(r for r, _, _ in snapshots if r["id"] == "LIV-001")

    def test_portable_example_and_html_escaping(self):
        self.change(lambda p: p.update(title="<script>alert(1)</script>"))
        project, records = load_project(self.path)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0][0]["entity_id"], "SIM-W001")
        report = render_report(project, records)
        self.assertIn("&lt;script&gt;", report)
        self.assertNotIn("<script>", report)
        self.assertIn(records[0][2], report)

    def test_liv_adapter_parses_real_export(self):
        record = self.record(*load_project(self.path))
        adapted = record["adapted"]
        self.assertEqual(adapted["source_tool"], "laser-characterization-tools")
        self.assertEqual(adapted["source_schema_version"], "0.1.0")
        self.assertEqual(adapted["source_sample_id"], "SIM-D001")
        self.assertEqual(adapted["conditions"]["measurement_mode"], "CW")
        self.assertAlmostEqual(adapted["results"]["threshold_estimate_mA"], 20.0, places=6)
        self.assertAlmostEqual(adapted["results"]["slope_efficiency_mW_per_mA"], 0.4, places=6)
        self.assertIn("threshold_estimate_mA", render_report(*load_project(self.path)))

    def test_liv_manifest_fills_missing_temperature(self):
        record = self.record(*load_project(self.path))
        self.assertEqual(record["conditions"]["temperature_C"], 25)
        self.assertEqual(record["conditions"]["measurement_mode"], "CW")

    def test_liv_conflicting_conditions_rejected(self):
        self.change(lambda p: self.liv_entry(p).update(conditions={"measurement_mode": "pulsed"}))
        with self.assertRaisesRegex(ValueError, "Conflicting measurement_mode"):
            load_project(self.path)

    def liv_entry(self, project):
        return next(m for m in project["measurements"] if m["id"] == "LIV-001")

    def test_liv_adapter_rejects_wrong_schema(self):
        payload = json.loads((self.root / "example/results/liv_export.json").read_text(encoding="utf-8"))
        payload["schema_version"] = "9.9.9"
        with self.assertRaisesRegex(ValueError, "Unsupported LIV schema_version"):
            adapt_liv(payload)

    def test_liv_adapter_rejects_non_cw(self):
        payload = json.loads((self.root / "example/results/liv_export.json").read_text(encoding="utf-8"))
        payload["measurement_mode"] = "pulsed"
        with self.assertRaisesRegex(ValueError, "CW"):
            adapt_liv(payload)

    def load(self, name):
        return json.loads((self.root / f"example/results/{name}").read_text(encoding="utf-8"))

    def test_pl_adapter_keeps_presentation_semantics(self):
        adapted = next(r for r, _, _ in load_project(self.path)[1] if r["id"] == "PL-001")["adapted"]
        self.assertEqual(adapted["source_tool"], "PL-Analyzer")
        self.assertEqual(adapted["method"]["name"], "presentation-half-height-fwhm")
        self.assertIn("not Raw Peak", adapted["method"]["semantics"])
        self.assertAlmostEqual(adapted["results"]["peak_wavelength_nm"], 1300.0, places=3)
        self.assertEqual(adapted["conditions"]["excitation_laser"], "532 nm")
        self.assertEqual(adapted["conditions"]["temperature"], "300 K")

    def test_pl_adapter_rejects_wrong_schema(self):
        payload = self.load("pl_export.json")
        payload["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "Unsupported PL schema_version"):
            adapt_pl(payload)

    def test_beam_adapter_keeps_angles_and_status(self):
        adapted = next(r for r, _, _ in load_project(self.path)[1] if r["id"] == "BEAM-001")["adapted"]
        self.assertEqual(adapted["source_tool"], "laser-beam-qa")
        self.assertEqual(adapted["conditions"]["scan_status"], "complete")
        self.assertEqual(adapted["conditions"]["calibration_id"], "calibration_40x_example")
        self.assertAlmostEqual(adapted["results"]["full_angle_x_mrad"], 7.996, places=2)
        self.assertAlmostEqual(adapted["results"]["full_angle_y_mrad"], 10.0, places=2)
        self.assertIn("full_angle", json.dumps(adapted["results"]))
        self.assertIn("half_angle", json.dumps(adapted["results"]))
        self.assertEqual(adapted["judgement"], "PASS")

    def test_beam_adapter_rejects_unknown_model(self):
        payload = self.load("beam_export.json")
        payload["divergence_result"]["model"] = "mystery"
        with self.assertRaisesRegex(ValueError, "Unsupported beam fit model"):
            adapt_beam(payload)

    def test_beam_adapter_keeps_incomplete_scan_visible(self):
        payload = self.load("beam_export.json")
        payload["scan_status"] = "incomplete"
        payload["measurement_status"] = "incomplete"
        payload["error_list"] = [{"error_code": "E_SCAN_ABORTED", "message": "scan aborted"}]
        adapted = adapt_beam(payload)
        self.assertEqual(adapted["conditions"]["scan_status"], "incomplete")
        self.assertIn("scan aborted", adapted["warnings"])

    def test_spectrum_adapter_keeps_spacing_rule_semantics(self):
        adapted = next(r for r, _, _ in load_project(self.path)[1] if r["id"] == "SPECTRUM-001")["adapted"]
        self.assertEqual(adapted["method"]["name"], "spectral-spacing-screen")
        self.assertEqual(adapted["method"]["spacing_min_GHz"], 195.0)
        self.assertEqual(adapted["conditions"]["current_mA"], 100.0)
        combs = adapted["results"]["comb_counts"]
        self.assertEqual(combs["100mA_1V_6dB"]["comb_line_count"], 5)
        self.assertTrue(combs["100mA_1V_6dB"]["spacing_rule_passed"])
        self.assertEqual(combs["100mA_1V_3dB"]["comb_line_count"], 3)

    def test_spectrum_adapter_rejects_wrong_units(self):
        payload = self.load("spectrum_export.json")
        payload["units"]["power"] = "mW"
        with self.assertRaisesRegex(ValueError, "units"):
            adapt_spectrum(payload)

    def test_spectrum_adapter_warns_on_multiple_condition_points(self):
        payload = self.load("spectrum_export.json")
        payload["points"].append(dict(payload["points"][0], id="p1", current=140, bias=2))
        adapted = adapt_spectrum(payload)
        self.assertEqual(adapted["results"]["point_count"], 2)
        self.assertTrue(any("2 condition points" in w for w in adapted["warnings"]))

    def test_reject_duplicate_source_file(self):
        self.change(lambda p: p["measurements"].append(
            {"id": "LIV-002", "entity_id": "SIM-D001", "modality": "liv", "data_kind": "synthetic",
             "conditions": {}, "source": "results/liv_export.json"}))
        with self.assertRaisesRegex(ValueError, "Duplicate source file"):
            load_project(self.path)

    def test_reject_unknown_entity(self):
        self.change(lambda p: p["measurements"][0].update(entity_id="missing"))
        with self.assertRaisesRegex(ValueError, "Unknown entity"):
            load_project(self.path)

    def test_reject_parent_cycle(self):
        self.change(lambda p: p["entities"][0].update(parent_id="SIM-D001"))
        with self.assertRaisesRegex(ValueError, "cycle"):
            load_project(self.path)

    def test_reject_duplicate_id(self):
        self.change(lambda p: p["entities"].append(dict(p["entities"][0])))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_project(self.path)

    def test_reject_path_escape(self):
        self.change(lambda p: p["measurements"][0].update(source="../outside.json"))
        with self.assertRaisesRegex(ValueError, "escapes"):
            load_project(self.path)

    def test_report_does_not_overwrite_input(self):
        original = self.path.read_bytes()
        with self.assertRaises(SystemExit):
            main(["report", str(self.path), "--out", str(self.path)])
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
