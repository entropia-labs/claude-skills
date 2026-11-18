"""Check a converted NDA before the customer uploads it to Entropia.

    python3 verify.py <out.docx>

Exits 0 when nothing blocks the upload. The layout check needs LibreOffice (`soffice`)
and `pypdfium2`; without them it says the layout is not verified.
"""

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checks import coloured_tags, packaging_problems, template_problems  # noqa: E402

TAG_IN_PDF = re.compile(r"\{\{(?:s1|entropia)\|[^{}]*\}\}")
NBSP_WIDTH_PT = 2.92  # Arial at 10.5 pt; close enough to size a pad


def render(path: str, folder: str) -> str | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        return None
    profile = f"file://{folder}/profile"
    subprocess.run(
        [soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", folder, path],
        capture_output=True,
        timeout=180,
        env={**os.environ, "HOME": folder},
    )
    pdf = os.path.join(folder, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    return pdf if os.path.exists(pdf) else None


def layout_problems(pdf_path: str) -> list[str]:
    import pypdfium2

    problems = []
    boxes = []
    document = pypdfium2.PdfDocument(pdf_path)
    for number, page in enumerate(document, start=1):
        page_width, page_height = page.get_size()
        textpage = page.get_textpage()
        text = textpage.get_text_range(0, textpage.count_chars())
        for match in TAG_IN_PDF.finditer(text):
            tag = match.group(0)
            flat = tag.replace("\r", "").replace("\n", "")
            parts = flat.strip("{}").split("|")
            label = parts[-1] if parts[1] == "text" else flat
            if "\n" in tag or "\r" in tag:
                problems.append(
                    f"page {number}: {label} breaks across two lines, so Youtrust ignores it. "
                    "Change the `pad` of a field earlier on that line so this anchor starts on a line where it fits"
                )
                continue
            first = textpage.get_charbox(match.start())
            left = first[0]
            top = page_height - max(textpage.get_charbox(i)[3] for i in range(match.start(), match.end()))
            after = match.end()
            while after < len(text) and text[after] in "  ":
                after += 1
            gap = None
            if after < len(text) and text[after] not in "\r\n":
                gap = textpage.get_charbox(after)[0] - left
            if parts[1] == "text":
                width, height = int(parts[3]), int(parts[4])
                if gap is not None and gap + 2 < width:
                    missing = math.ceil((width - gap) / NBSP_WIDTH_PT)
                    problems.append(
                        f"page {number}: {label} is {width} pt wide but its gap is {gap:.0f} pt, so it covers the next words. "
                        f"Raise its `pad` by {missing}, or set its `width` to {gap:.0f}"
                    )
            elif parts[1] == "signature":
                width, height = int(parts[2]), int(parts[3])
            else:
                continue
            if left + width > page_width:
                problems.append(f"page {number}: {label} runs off the page: lower its `width` or move it")
            boxes.append((number, label, left, top, width, height))
        textpage.close()
        page.close()
    document.close()
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            same_page = a[0] == b[0]
            if same_page and a[2] < b[2] + b[4] and b[2] < a[2] + a[4] and a[3] < b[3] + b[5] and b[3] < a[3] + a[5]:
                problems.append(
                    f"page {a[0]}: {a[1]} and {b[1]} overlap. If they sit on lines next to each other, "
                    "set `line_pt: 19` on the fields of that paragraph"
                )
    return problems


def main(path: str) -> int:
    blocking = []
    problems, tags = template_problems(path)
    blocking += [f"Entropia would refuse the upload: {p}" for p in problems]
    blocking += [f"Youtrust would refuse the file: {p}" for p in packaging_problems(path)]
    blocking += [f"visible to the signer: {t}" for t in coloured_tags(path)]

    with tempfile.TemporaryDirectory() as folder:
        try:
            import pypdfium2  # noqa: F401
        except ImportError:
            pdf = None
            layout_note = "layout not verified: install pypdfium2 (`pip install pypdfium2`)"
        else:
            pdf = render(path, folder)
            layout_note = None if pdf else "layout not verified: LibreOffice (`soffice`) is not available"
        if pdf:
            blocking += layout_problems(pdf)

    print(f"anchors: {len(tags['anchors'])} ({', '.join(sorted(set(tags['anchors'])))}); Entropia values: {', '.join(tags['placeholders']) or 'none'}")
    for item in blocking:
        print(f"PROBLEM {item}")
    print(layout_note or "layout verified with LibreOffice")
    print("OK: ready to upload" if not blocking else f"{len(blocking)} problem(s) to fix")
    return 1 if blocking else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
