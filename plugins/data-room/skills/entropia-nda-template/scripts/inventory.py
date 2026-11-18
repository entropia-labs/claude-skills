"""List what an NDA template needs before it can be signed through Entropia.

    python3 inventory.py <template.docx> [inventory.json]

Prints every value to fill in (F1, F2, ...), the anchors and Entropia values already in
the file, and the problems that would stop an upload or a signature.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checks import coloured_tags, packaging_problems, template_problems  # noqa: E402
from docx_model import candidates, read_parts  # noqa: E402

KIND_LABELS = {
    "bracket": "[bracket]",
    "dots": "dotted line",
    "underscores": "underscores",
    "blank": "blank space",
    "label": "label with nothing after it",
}


def main(path: str, out: str | None) -> None:
    found = candidates(read_parts(path))
    problems, tags = template_problems(path)
    report = {
        "fields": [c.__dict__ for c in found],
        "anchors": tags["anchors"],
        "entropia_values": tags["placeholders"],
        "template_problems": problems,
        "packaging_problems": packaging_problems(path),
        "visible_tags": coloured_tags(path),
    }
    print(f"{len(found)} field(s) to decide:")
    for c in found:
        where = "" if c.part == "word/document.xml" else f" ({c.part.removeprefix('word/').removesuffix('.xml')})"
        print(f"  {c.id:>4}  {KIND_LABELS[c.kind]:<28} {c.context}{where}")
    print(f"anchors already in the file: {', '.join(tags['anchors']) or 'none'}")
    print(f"Entropia values already in the file: {', '.join(tags['placeholders']) or 'none'}")
    for title, items in (
        ("template problems", problems),
        ("packaging problems (fixed by convert.py)", report["packaging_problems"]),
        ("tags a signer would see (made white by convert.py)", report["visible_tags"]),
    ):
        if items:
            print(f"{title}:")
            for item in items:
                print(f"  - {item}")
    if out:
        with open(out, "w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
