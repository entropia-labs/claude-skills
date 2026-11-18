# Reference

## Actions

| Action | What the signer sees | Use for |
|---|---|---|
| `text` | an empty box to type in, required by default | any value the signer knows: company details, representative, date and place of signature |
| `entropia` | a value they cannot edit, filled by Entropia | `counterparty_name` (the signer's first and last name from their Entropia profile, the person who signs, never their company) and `project_code_name` (the data room's name) |
| `signature` | the signature box | a place to sign or initial, when the template has no signature anchor there |
| `delete` | nothing | a note meant for whoever prepares the template, such as `[Anchor: signature]` |
| `keep` | the text as written | text that only looks like a field, such as a dotted leader in a table of contents |

`entropia` prints the value exactly as stored: offer `project_code_name` only when the data room's name is the text the sentence needs (a property name, a project name), and confirm with the customer. A signer cannot correct an `entropia` value; offer `text` when they might need to.

A value that appears twice (the company name in the parties and again above the signature) becomes two fields the signer fills twice: Youtrust does not link fields. Point that out. For the signer's own name (`Name:` in the signature block), offer `counterparty_name`.

## Plan format

```json
{
  "fields": {
    "F1": {"action": "text", "name": "Company", "question": "Company", "instruction": "LegalName", "max_length": 80, "width": 160, "pad": 14},
    "F2": {"action": "entropia", "key": "counterparty_name", "pad": 6},
    "F3": {"action": "signature", "width": 180, "height": 70},
    "F4": {"action": "delete"},
    "F5": {"action": "keep"}
  }
}
```

- `name`: unique per document, letters, digits and `_`, starting with a letter.
- `question` (shown in the empty box) and `instruction` (shown as help): one word each, no space, `|`, `{` or `}`. A space or a `|` lets the line break inside the anchor. Accents and `°` are fine.
- `max_length`, `width` (pt), `height` (pt, default 15), `optional` (default `false`).
- `pad`: white non-breaking spaces after the tag, about 2.9 pt each, to widen the gap in the sentence.
- `line_pt`: exact line spacing for the field's paragraph; `19` when fields sit on lines next to each other.
- `whiten_existing_tags` (top level, default `true`): makes every anchor and Entropia value already in the template white with no shading.

## Sizing

| Value | `max_length` | `width` |
|---|---|---|
| date `DD/MM/YYYY` | 10 | 95 |
| time | 5 | 90 |
| number, registration, phone | 20 | 100 |
| city | 40 | 100 |
| role | 50 | 130 |
| person or company name, email | 60–80 | 160 |
| address, property description | 120 | 220 |

Start with `pad` 0 and let `verify.py` give the exact `pad` or `width` each gap needs.

## Why each rule

- **One line per anchor.** Youtrust reads anchors from its own PDF render of the document and ignores one that breaks across two lines, with no error. A line may break after `|`, so `convert.py` writes text anchors in 5 pt type, about 100 pt wide, and the plan keeps spaces out of them.
- **The gap.** The field box is drawn over the anchor's place in the line. The 5 pt anchor leaves a small gap, so `pad` widens it to the field's `width`; a gap narrower than the field means the box covers the next words.
- **Height 15.** One line of text in a Youtrust field: font 10 × line height 1.5. A taller box reaches the next line.
- **Overlap.** With ordinary line spacing, lines are about 13–15 pt apart, so 15 pt boxes on lines next to each other overlap. `line_pt: 19` spaces that paragraph's lines without changing where they break.
- **Entropia values at normal size.** Entropia places its value from the tag's position, fitted for text at normal size, so `convert.py` keeps the tag's size and makes it white. The printed value is sized to fit, and can run past a short gap: widen the gap with `pad`.
- **White tags.** Anything not white, or on a shaded background, shows on the signed document.
- **Clean package.** Youtrust checks that a `.docx` is a Word document from its first bytes. Some editors save it with extra bytes after the first entry, and it then reads as a plain zip: Youtrust refuses the upload and the member sees "We could not open the agreement for signature". `convert.py` always writes a fresh package.

## What Entropia and Youtrust report

| Message | Cause | Fix |
|---|---|---|
| No text can be read from this NDA | a scanned document | the Word source |
| An anchor in this NDA is broken | an anchor split across lines, an unknown kind, or not `s1` | convert again; verify |
| This NDA asks for '…', which is not a value Entropia fills in | an `{{entropia|…}}` key other than the two above | use `text`, or one of the two keys |
| This NDA has no signature anchor | no `{{s1|signature|…}}` | add a `signature` action where the signer signs |
| We could not open the agreement for signature (member, at signing) | most often the package: Youtrust refused the file | run `verify.py` on the uploaded file; convert it again |
