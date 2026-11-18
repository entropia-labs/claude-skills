"""The checks Entropia and Youtrust run on an NDA template, run here before the customer uploads it."""

import shutil
import struct
import subprocess
import zipfile

from docx_model import ANCHOR, ANCHOR_OPENING, ENTROPIA_KEYS, PLACEHOLDER, TAG, paragraphs, read_parts


def template_problems(path: str) -> tuple[list[str], dict]:
    """The rules Entropia applies when the NDA is uploaded with electronic signature."""
    problems = []
    anchors: list[str] = []
    placeholders: list[str] = []
    for part, xml in read_parts(path).items():
        for paragraph in paragraphs(part, xml):
            for line in paragraph.text.split("\n"):
                intact = {m.start(): m for m in ANCHOR.finditer(line)}
                for opening in ANCHOR_OPENING.finditer(line):
                    match = intact.get(opening.start())
                    end = line.find("}}", opening.start())
                    fragment = line[opening.start() : end + 2 if end != -1 else None]
                    if match is None:
                        problems.append(f"broken anchor (unknown kind, or split): {fragment}")
                    elif match.group("signer") != "1":
                        problems.append(f"anchor for signer {match.group('signer')}: Entropia adds one signer, so use s1: {fragment}")
                    else:
                        anchors.append(match.group("kind"))
                for match in PLACEHOLDER.finditer(line):
                    if match.group("key") in ENTROPIA_KEYS:
                        placeholders.append(match.group("key"))
                    else:
                        problems.append(f"unknown Entropia value '{match.group('key')}': use one of {', '.join(ENTROPIA_KEYS)}")
    if "signature" not in anchors:
        problems.append("no signature anchor: the signer would have nowhere to sign")
    return problems, {"anchors": anchors, "placeholders": placeholders}


def packaging_problems(path: str) -> list[str]:
    """Youtrust reads the type of a .docx from its first bytes and refuses a file that reads as a plain zip."""
    problems = []
    with zipfile.ZipFile(path) as archive:
        infos = sorted(archive.infolist(), key=lambda i: i.header_offset)
        if infos and infos[0].filename != "[Content_Types].xml":
            problems.append(f"the first zip entry is {infos[0].filename}, not [Content_Types].xml")
    with open(path, "rb") as file:
        data = file.read()
    for info, following in zip(infos, infos[1:] + [None]):
        name_length, extra_length = struct.unpack("<HH", data[info.header_offset + 26 : info.header_offset + 30])
        if extra_length:
            problems.append(f"zip entry {info.filename} carries {extra_length} extra bytes in its header")
        data_end = info.header_offset + 30 + name_length + extra_length + info.compress_size
        if following is not None and following.header_offset - data_end > 16:
            problems.append(f"{following.header_offset - data_end} unexplained bytes after zip entry {info.filename}")
    if shutil.which("file"):
        mime = subprocess.run(["file", "-b", "--mime-type", path], capture_output=True, text=True).stdout.strip()
        if mime != "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            problems.append(f"`file` reads this document as {mime}, not as a Word document")
    return problems


def coloured_tags(path: str) -> list[str]:
    """Tags a signer would see: written in a colour other than white, or on a shaded background."""
    visible = []
    for part, xml in read_parts(path).items():
        for paragraph in paragraphs(part, xml):
            position = 0
            spans = [(m.start(), m.end(), m.group(0)) for m in TAG.finditer(paragraph.text)]
            for _, _, run in paragraph.runs:
                first, last = position, position + len(run.chars)
                position = last
                for start, end, tag in spans:
                    if start < last and end > first and "".join(run.chars).strip():
                        white = 'w:val="FFFFFF"' in run.rpr or 'w:val="ffffff"' in run.rpr
                        shaded = "<w:shd" in run.rpr or "<w:highlight" in run.rpr
                        if not white or shaded:
                            visible.append(tag)
    return sorted(set(visible))
