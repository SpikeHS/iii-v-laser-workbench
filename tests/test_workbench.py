import json
from pathlib import Path
import shutil
import tempfile
import unittest

from workbench import load_project, main, render_report


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples", self.root / "example")
        self.path = self.root / "example/project.json"

    def change(self, edit):
        project = json.loads(self.path.read_text(encoding="utf-8"))
        edit(project)
        self.path.write_text(json.dumps(project), encoding="utf-8")

    def test_portable_example_and_html_escaping(self):
        self.change(lambda p: p.update(title="<script>alert(1)</script>"))
        project, records = load_project(self.path)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0][0]["entity_id"], "SIM-W001")
        report = render_report(project, records)
        self.assertIn("&lt;script&gt;", report)
        self.assertNotIn("<script>", report)
        self.assertIn(records[0][2], report)

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
