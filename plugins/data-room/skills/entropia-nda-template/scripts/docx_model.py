"""Read and rewrite the paragraphs of a .docx without a third-party library.

Word splits one visible word across several runs, so placeholders are found on the
paragraph's joined text and every edit is mapped back onto the runs it touches.
"""

import html
import re
import zipfile
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

TEXT_PARTS = re.compile(r"word/(document|header\d*|footer\d*)\.xml")
# Innermost paragraphs only: a text box nests paragraphs inside a paragraph.
PARAGRAPH = re.compile(r"<w:p\b(?:(?!<w:p\b).)*?</w:p>", re.S)
RUN = re.compile(r"<w:r\b[^>]*>(?:(?!</w:r>).)*</w:r>", re.S)
RUN_PROPERTIES = re.compile(r"<w:rPr>.*?</w:rPr>|<w:rPr/>", re.S)
TOKEN = re.compile(
    r"<w:t(?:\s[^>]*)?>(?P<text>[^<]*)</w:t>|<w:t(?:\s[^>]*)?/>"
    r"|(?P<tab><w:tab/>)|(?P<br><w:br(?:\s[^>]*)?/>|<w:cr/>)"
    r"|(?P<skip><w:lastRenderedPageBreak/>|<w:softHyphen/>|<w:noBreakHyphen/>)"
)
OPAQUE = "￼"

TAG = re.compile(r"\{\{[^{}\r\n]*\}\}")
ANCHOR = re.compile(r"\{\{s(?P<signer>\d+)\|(?P<kind>signature|signer_name|text|mention|checkbox)\|[^{}\r\n]*\}\}")
ANCHOR_OPENING = re.compile(r"\{\{s\d+\|")
PLACEHOLDER = re.compile(r"\{\{entropia\|(?P<key>[a-z0-9_]+)\}\}")
ENTROPIA_KEYS = {
    "project_code_name": "the data room name",
    "counterparty_name": "the signer's full name",
}


@dataclass
class Run:
    xml: str
    rpr: str
    chars: list[str] = field(default_factory=list)
    opaque: bool = False


@dataclass
class Paragraph:
    part: str
    index: int
    start: int
    end: int
    xml: str
    runs: list[tuple[int, int, Run]]

    @property
    def text(self) -> str:
        return "".join("".join(run.chars) for _, _, run in self.runs)


def parse_run(xml: str) -> Run:
    rpr_match = RUN_PROPERTIES.search(xml)
    rpr = rpr_match.group(0) if rpr_match else ""
    body = xml[xml.index(">") + 1 : -len("</w:r>")]
    if rpr_match:
        body = body.replace(rpr, "", 1)
    run = Run(xml=xml, rpr=rpr)
    leftover = TOKEN.sub("", body).strip()
    if leftover:
        run.opaque = True
        run.chars = [OPAQUE]
        return run
    for token in TOKEN.finditer(body):
        if token.group("text") is not None:
            run.chars.extend(html.unescape(token.group("text")))
        elif token.group("tab"):
            run.chars.append("\t")
        elif token.group("br"):
            run.chars.append("\n")
    return run


def paragraphs(part: str, xml: str) -> list[Paragraph]:
    found = []
    for index, match in enumerate(PARAGRAPH.finditer(xml)):
        runs = [(m.start(), m.end(), parse_run(m.group(0))) for m in RUN.finditer(match.group(0))]
        found.append(Paragraph(part, index, match.start(), match.end(), match.group(0), runs))
    return found


def read_parts(path: str) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {
            name: archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if TEXT_PARTS.fullmatch(name)
        }


def text_run(rpr: str, text: str) -> str:
    """A run of plain text: tabs and line breaks become their own elements."""
    pieces = []
    for chunk in re.split(r"(\t|\n)", text):
        if chunk == "\t":
            pieces.append("<w:tab/>")
        elif chunk == "\n":
            pieces.append("<w:br/>")
        elif chunk:
            pieces.append(f'<w:t xml:space="preserve">{escape(chunk)}</w:t>')
    return f"<w:r>{rpr}{''.join(pieces)}</w:r>" if pieces else ""


def restyle(rpr: str, *, color: str | None = None, size_half_points: int | None = None, plain: bool = False) -> str:
    """Change a run's colour and size, and drop shading and highlight so a white tag stays invisible."""
    inner = rpr[len("<w:rPr>") : -len("</w:rPr>")] if rpr.startswith("<w:rPr>") else ""
    inner = re.sub(r"<w:shd\b[^>]*/>|<w:highlight\b[^>]*/>", "", inner)
    if plain:
        inner = re.sub(r"<w:(?:b|bCs|i|iCs|u)\b[^>]*/>", "", inner)
    if color is not None:
        inner = re.sub(r"<w:color\b[^>]*/>", "", inner) + f'<w:color w:val="{color}"/>'
    if size_half_points is not None:
        inner = re.sub(r"<w:szCs?\b[^>]*/>", "", inner)
        inner += f'<w:sz w:val="{size_half_points}"/><w:szCs w:val="{size_half_points}"/>'
    return f"<w:rPr>{inner}</w:rPr>" if inner else ""


def font_size(rpr: str, default: int = 21) -> int:
    match = re.search(r'<w:sz w:val="(\d+)"', rpr)
    return int(match.group(1)) if match else default


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    replacement: str = ""
    """Runs inserted at `start`, already rendered as XML."""
    whiten: bool = False
    """Keep the text but make it white, for an existing tag the customer wrote in colour."""


def rewrite(paragraph: Paragraph, edits: list[Edit]) -> str:
    """Apply edits that do not overlap; the paragraph's other XML stays byte for byte."""
    edits = sorted(edits, key=lambda e: (e.start, e.end))
    total = len(paragraph.text)
    out = []
    cursor = 0
    position = 0
    for run_start, run_end, run in paragraph.runs:
        out.append(paragraph.xml[cursor:run_start])
        cursor = run_end
        first, last = position, position + len(run.chars)
        position = last
        here = [e for e in edits if (e.start < last and e.end > first) or (e.start == e.end and first <= e.start < last)]
        if not here:
            out.append(run.xml)
            continue
        if run.opaque:
            raise ValueError(f"an edit in paragraph {paragraph.index} of {paragraph.part} touches an image or a field code")
        rest_rpr = restyle(run.rpr, plain=True) if any(not e.whiten for e in here) else run.rpr
        text = "".join(run.chars)
        offset = 0
        for edit in here:
            local_start = max(edit.start - first, 0)
            local_end = min(edit.end - first, len(text))
            out.append(text_run(rest_rpr, text[offset:local_start]))
            if edit.start >= first:
                out.append(edit.replacement)
            if edit.whiten:
                out.append(text_run(restyle(run.rpr, color="FFFFFF"), text[local_start:local_end]))
            offset = max(offset, local_end)
        out.append(text_run(rest_rpr, text[offset:]))
    out.append(paragraph.xml[cursor:])
    result = "".join(out)
    at_end = "".join(e.replacement for e in edits if e.start == e.end == total)
    if at_end:
        closing = result.rfind("</w:p>")
        result = result[:closing] + at_end + result[closing:]
    return result


def write_clean_docx(source: str, target: str, replaced_parts: dict[str, str]) -> None:
    """A fresh zip, with `[Content_Types].xml` first and no extra fields.

    Signature providers check the type of a .docx from its first bytes. A zip with
    extra data after its first entry, or with the content types last, reads as a plain
    zip, and the provider then refuses the upload as a file whose extension lies.
    """
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        first = [n for n in ("[Content_Types].xml", "_rels/.rels") if n in names]
        order = first + [n for n in names if n not in first]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
            for name in order:
                data = replaced_parts[name].encode("utf-8") if name in replaced_parts else archive.read(name)
                out.writestr(zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0)), data, compress_type=zipfile.ZIP_DEFLATED)


CANDIDATE_PATTERNS = [
    ("bracket", re.compile(r"\[[^\[\]\n]{1,150}\]")),
    ("dots", re.compile(r"[.…](?:[  ]?[.…]){3,}")),
    ("underscores", re.compile(r"_{4,}")),
    ("blank", re.compile(r"[  \t]{6,}")),
]
LABEL_AT_END = re.compile(r"^\s*[^\s:][^\n:]{0,39}?\s*:[  \t]*$")


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    part: str
    paragraph: int
    start: int
    end: int
    text: str
    context: str


def candidates(parts: dict[str, str]) -> list[Candidate]:
    """Every place that looks like a value to fill in, in reading order: document, then headers and footers."""
    found = []
    ordered = sorted(parts, key=lambda name: (name != "word/document.xml", name))
    for part in ordered:
        for paragraph in paragraphs(part, parts[part]):
            text = paragraph.text
            taken = [(m.start(), m.end()) for m in TAG.finditer(text)]
            spans = []
            for kind, pattern in CANDIDATE_PATTERNS:
                for match in pattern.finditer(text):
                    span = (match.start(), match.end())
                    if kind == "dots" and "…" in match.group(0):
                        # A line of `…` keeps the full stop that ends its sentence.
                        span = (match.start(), match.start() + match.group(0).rindex("…") + 1)
                    if any(a < span[1] and span[0] < b for a, b in taken + [s[:2] for s in spans]):
                        continue
                    if kind == "blank" and not text[: span[0]].strip():
                        continue
                    spans.append((span[0], span[1], kind))
            if not spans and LABEL_AT_END.match(text) and not TAG.search(text):
                spans.append((len(text), len(text), "label"))
            for start, end, kind in sorted(spans):
                before = text[max(0, start - 40) : start]
                after = text[end : end + 40]
                shown = text[start:end] if end > start else ""
                found.append(
                    Candidate(
                        id="",
                        kind=kind,
                        part=part,
                        paragraph=paragraph.index,
                        start=start,
                        end=end,
                        text=shown,
                        context=f"{before}⟦{shown}⟧{after}".replace("\n", " ").replace("\t", " "),
                    )
                )
    return [Candidate(**{**c.__dict__, "id": f"F{i}"}) for i, c in enumerate(found, start=1)]
