"""Apply a confirmed plan to an NDA template.

    python3 convert.py <in.docx> <plan.json> <out.docx>

The plan names an action for every field `inventory.py` found. See REFERENCE.md for its format.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_model import (  # noqa: E402
    ENTROPIA_KEYS,
    TAG,
    Edit,
    candidates,
    font_size,
    paragraphs,
    read_parts,
    restyle,
    rewrite,
    text_run,
    write_clean_docx,
)

ACTIONS = {"text", "entropia", "signature", "delete", "keep"}
ANCHOR_VALUE = re.compile(r"[^\s|{}]+")
FIELD_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
# A small anchor fits on its line: Youtrust ignores an anchor that wraps, and `|` lets a line break.
ANCHOR_HALF_POINTS = 10
NBSP = " "


def fail(message: str) -> None:
    sys.exit(f"plan refused: {message}")


def validate(plan: dict, found: list) -> dict:
    fields = plan.get("fields", {})
    ids = {c.id for c in found}
    missing = sorted(ids - fields.keys(), key=lambda i: int(i[1:]))
    if missing:
        fail(f"no action for {', '.join(missing)}: give every field an action, `keep` included")
    unknown = sorted(fields.keys() - ids)
    if unknown:
        fail(f"{', '.join(unknown)} are not fields of this document: run inventory.py again")
    names = []
    for field_id, spec in fields.items():
        action = spec.get("action")
        if action not in ACTIONS:
            fail(f"{field_id}: action must be one of {sorted(ACTIONS)}")
        if action == "text":
            for key in ("question", "instruction"):
                if not ANCHOR_VALUE.fullmatch(str(spec.get(key, ""))):
                    fail(f"{field_id}: {key} must be one word, with no space, `|`, `{{` or `}}`")
            if not FIELD_NAME.fullmatch(str(spec.get("name", ""))):
                fail(f"{field_id}: name must be letters, digits or `_`, starting with a letter")
            names.append(spec["name"])
            if int(spec.get("width", 0)) < 24 or int(spec.get("max_length", 0)) < 1:
                fail(f"{field_id}: width must be at least 24 and max_length at least 1")
        if action == "entropia" and spec.get("key") not in ENTROPIA_KEYS:
            fail(f"{field_id}: key must be one of {sorted(ENTROPIA_KEYS)}")
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        fail(f"field names must be unique: {', '.join(duplicates)}")
    return fields


def anchor_for(spec: dict) -> str:
    action = spec["action"]
    if action == "text":
        optional = "t" if spec.get("optional") else "f"
        return (
            f"{{{{s1|text|{int(spec['max_length'])}|{int(spec['width'])}|{int(spec.get('height', 15))}"
            f"|{spec['question']}|{spec['instruction']}|{optional}|{spec['name']}}}}}"
        )
    if action == "entropia":
        return f"{{{{entropia|{spec['key']}}}}}"
    return f"{{{{s1|signature|{int(spec.get('width', 180))}|{int(spec.get('height', 70))}}}}}"


def replacement(spec: dict, source_rpr: str) -> str:
    action = spec["action"]
    if action in ("delete", "keep"):
        return ""
    size = ANCHOR_HALF_POINTS if action == "text" else font_size(source_rpr)
    tag = text_run(restyle(source_rpr, color="FFFFFF", size_half_points=size, plain=True), anchor_for(spec))
    pad = int(spec.get("pad", 0))
    if pad:
        tag += text_run(restyle(source_rpr, color="FFFFFF", plain=True), NBSP * pad)
    return tag


def source_rpr(paragraph, position: int) -> str:
    offset = 0
    last = ""
    for _, _, run in paragraph.runs:
        if not run.opaque:
            last = run.rpr
        if offset <= position < offset + len(run.chars) and not run.opaque:
            return run.rpr
        offset += len(run.chars)
    return last


def with_line_spacing(paragraph_xml: str, points: int) -> str:
    """Exact spacing, so a 15 pt field box never reaches into the line below."""
    twips = points * 20
    spacing = f'w:line="{twips}" w:lineRule="exact"'
    found = re.search(r"<w:spacing\b[^>]*/>", paragraph_xml)
    if found:
        tag = re.sub(r'\s*w:line(?:Rule)?="[^"]*"', "", found.group(0))
        tag = tag.replace("<w:spacing", f"<w:spacing {spacing}", 1)
        return paragraph_xml[: found.start()] + tag + paragraph_xml[found.end() :]
    if "<w:pPr>" in paragraph_xml:
        return paragraph_xml.replace("<w:pPr>", f"<w:pPr><w:spacing {spacing}/>", 1)
    opening = paragraph_xml.index(">") + 1
    return paragraph_xml[:opening] + f"<w:pPr><w:spacing {spacing}/></w:pPr>" + paragraph_xml[opening:]


def convert(source: str, plan_path: str, target: str) -> None:
    parts = read_parts(source)
    found = candidates(parts)
    with open(plan_path, encoding="utf-8") as plan_file:
        plan = json.load(plan_file)
    fields = validate(plan, found)

    edits: dict[tuple[str, int], list[Edit]] = {}
    spacing: dict[tuple[str, int], int] = {}
    by_paragraph = {(p.part, p.index): p for part in parts for p in paragraphs(part, parts[part])}
    for candidate in found:
        spec = fields[candidate.id]
        if spec["action"] == "keep":
            continue
        key = (candidate.part, candidate.paragraph)
        paragraph = by_paragraph[key]
        rpr = source_rpr(paragraph, candidate.start)
        edits.setdefault(key, []).append(Edit(candidate.start, candidate.end, replacement(spec, rpr)))
        if spec.get("line_pt"):
            spacing[key] = int(spec["line_pt"])

    if plan.get("whiten_existing_tags", True):
        for key, paragraph in by_paragraph.items():
            replaced = [(e.start, e.end) for e in edits.get(key, [])]
            for match in TAG.finditer(paragraph.text):
                if not any(a < match.end() and match.start() < b for a, b in replaced):
                    edits.setdefault(key, []).append(Edit(match.start(), match.end(), whiten=True))

    new_parts = {}
    for part, xml in parts.items():
        for paragraph in reversed(paragraphs(part, xml)):
            key = (part, paragraph.index)
            if key not in edits and key not in spacing:
                continue
            new_xml = rewrite(paragraph, edits.get(key, []))
            if key in spacing:
                new_xml = with_line_spacing(new_xml, spacing[key])
            xml = xml[: paragraph.start] + new_xml + xml[paragraph.end :]
        new_parts[part] = xml
    write_clean_docx(source, target, new_parts)
    done = sum(1 for spec in fields.values() if spec["action"] != "keep")
    print(f"wrote {target}: {done} field(s) converted, {len(fields) - done} kept as they were")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    convert(*sys.argv[1:])
