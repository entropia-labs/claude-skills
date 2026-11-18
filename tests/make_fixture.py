"""Build a small synthetic NDA with every kind of field the skill must find.

    python3 tests/make_fixture.py tests/fixture-nda.docx
"""

import sys
import zipfile

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
RPR = '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="21"/></w:rPr>'
SHADED = '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:b/><w:color w:val="C00000"/><w:sz w:val="21"/><w:shd w:val="clear" w:color="auto" w:fill="FFF2AC"/></w:rPr>'


def run(text: str, rpr: str = RPR) -> str:
    return f'<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r>'


def paragraph(*runs: str) -> str:
    return f"<w:p>{''.join(runs)}</w:p>"


BODY = "".join(
    [
        paragraph(run("ACCORD DE CONFIDENTIALITÉ")),
        paragraph(run("Entre la société "), run("[RAISON "), run("SOCIALE]", SHADED), run(", située au "), run("……………………………"), run(".")),
        paragraph(run("Représentée par "), run("__________"), run(" en sa qualité de"), run("            "), run("ci-après « le Destinataire »."))
        ,
        paragraph(run("Le projet {{entropia|project_code_name}} est confidentiel.")),
        paragraph(run("Nom :")),
        paragraph(run("{{s1|signature|180|70}}", SHADED)),
    ]
)
DOCUMENT = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{BODY}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>'
CONTENT_TYPES = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'


def build(path: str) -> None:
    """Packed the way some editors save: content types last, extra bytes in a header."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        first = zipfile.ZipInfo("_rels/.rels", date_time=(2020, 1, 1, 0, 0, 0))
        first.extra = b"\xfe\xca" + (512).to_bytes(2, "little") + bytes(512)
        archive.writestr(first, RELS, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("word/document.xml", DOCUMENT)
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)


if __name__ == "__main__":
    build(sys.argv[1])
