"""Run with: python3 -m unittest discover -s tests"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "plugins", "data-room", "skills", "entropia-nda-template", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import convert  # noqa: E402
from checks import coloured_tags, packaging_problems, template_problems  # noqa: E402
from docx_model import candidates, read_parts  # noqa: E402
from make_fixture import build  # noqa: E402

PLAN = {
    "fields": {
        "F1": {"action": "entropia", "key": "counterparty_name", "pad": 4},
        "F2": {"action": "text", "question": "Adresse", "instruction": "AdresseComplète", "max_length": 120, "width": 200, "name": "Adresse"},
        "F3": {"action": "text", "question": "Représentant", "instruction": "CivilitéEtNom", "max_length": 60, "width": 150, "name": "Representant", "pad": 10},
        "F4": {"action": "text", "question": "Qualité", "instruction": "Fonction", "max_length": 50, "width": 120, "name": "Qualite", "line_pt": 19},
        "F5": {"action": "keep"},
    }
}


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.folder.name, "nda.docx")
        self.target = os.path.join(self.folder.name, "out.docx")
        self.plan = os.path.join(self.folder.name, "plan.json")
        build(self.source)

    def tearDown(self):
        self.folder.cleanup()

    def convert(self, plan):
        with open(self.plan, "w", encoding="utf-8") as file:
            json.dump(plan, file, ensure_ascii=False)
        with redirect_stdout(io.StringIO()):
            convert.convert(self.source, self.plan, self.target)

    def test_inventory_finds_each_kind_of_field_in_reading_order(self):
        found = candidates(read_parts(self.source))
        self.assertEqual(
            [(c.id, c.kind, c.text) for c in found],
            [
                ("F1", "bracket", "[RAISON SOCIALE]"),
                ("F2", "dots", "……………………………"),
                ("F3", "underscores", "__________"),
                ("F4", "blank", "            "),
                ("F5", "label", ""),
            ],
        )

    def test_source_shows_the_problems_a_customer_template_has(self):
        self.assertTrue(packaging_problems(self.source))
        self.assertEqual(coloured_tags(self.source), ["{{entropia|project_code_name}}", "{{s1|signature|180|70}}"])

    def test_converted_template_passes_every_check(self):
        self.convert(PLAN)
        problems, tags = template_problems(self.target)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(tags["anchors"]), ["signature", "text", "text", "text"])
        self.assertEqual(sorted(tags["placeholders"]), ["counterparty_name", "project_code_name"])
        self.assertEqual([p for p in packaging_problems(self.target) if "`file`" not in p], [])
        self.assertEqual(coloured_tags(self.target), [])
        with zipfile.ZipFile(self.target) as archive:
            self.assertEqual(archive.namelist()[0], "[Content_Types].xml")
            document = archive.read("word/document.xml").decode()
        self.assertIn("{{s1|text|60|150|15|Représentant|CivilitéEtNom|f|Representant}}", document)
        self.assertIn('w:line="380" w:lineRule="exact"', document)
        self.assertNotIn("[RAISON", document)
        self.assertNotIn("FFF2AC", document)

    def test_text_anchor_is_small_and_white_and_padding_follows_it(self):
        self.convert(PLAN)
        with zipfile.ZipFile(self.target) as archive:
            document = archive.read("word/document.xml").decode()
        anchor_run = document[document.rindex("<w:r>", 0, document.index("|Representant}}")) : document.index("|Representant}}")]
        self.assertIn('<w:color w:val="FFFFFF"/>', anchor_run)
        self.assertIn('<w:sz w:val="10"/>', anchor_run)
        self.assertIn(" " * 10, document)

    def test_plan_must_decide_every_field(self):
        partial = {"fields": {k: v for k, v in PLAN["fields"].items() if k != "F5"}}
        with self.assertRaisesRegex(SystemExit, "no action for F5"):
            self.convert(partial)

    def test_plan_refuses_an_anchor_value_with_a_space(self):
        bad = json.loads(json.dumps(PLAN))
        bad["fields"]["F2"]["question"] = "Adresse complète"
        with self.assertRaisesRegex(SystemExit, "question must be one word"):
            self.convert(bad)

    def test_scripts_run_from_any_directory(self):
        result = subprocess.run(
            [sys.executable, "-I", os.path.join(SCRIPTS, "inventory.py"), self.source],
            capture_output=True,
            text=True,
            cwd=self.folder.name,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("5 field(s) to decide", result.stdout)


if __name__ == "__main__":
    unittest.main()
