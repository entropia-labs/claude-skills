---
name: entropia-nda-template
description: Prepare an NDA or terms document in Word (.docx) for electronic signature in an Entropia data room, through the Youtrust provider. Use when a customer wants their NDA template signable in Entropia, wants its blanks, dotted lines or [bracket] fields turned into fields the signer fills in, or has an NDA that Entropia refuses or that fails to open for signature.
---

# Entropia NDA template

Entropia sends the NDA to each member through Youtrust. Youtrust reads hidden **anchors** in the document (`{{s1|text|…}}`, `{{s1|signature|…}}`) and draws a field where each one sits. Entropia fills in two **Entropia values** itself (`{{entropia|counterparty_name}}`, `{{entropia|project_code_name}}`). This skill turns the customer's template into that format and checks it the way Entropia and Youtrust will.

Talk to the customer in their language, in plain words: they know their NDA, not anchors. Keep their wording of the NDA exactly as it is; only the fields change.

The scripts are in `scripts/` next to this file and need Python 3 only. [REFERENCE.md](REFERENCE.md) holds the plan format, the sizing table, and the rules behind every check: read it before step 2.

## 1. Inventory

Get the template as a `.docx`. A PDF cannot be edited reliably: ask for the Word source.

```
python3 scripts/inventory.py <template.docx> inventory.json
```

It lists every **field** to decide (`F1`, `F2`, …: brackets, dotted lines, underscores, blank spaces, labels with nothing after them), the anchors and Entropia values already present, and the problems that would block an upload.

Done when you have the list and have read each field's context.

## 2. Plan

For every field, propose one action to the customer in a table: field, context, proposed action, and for a text field its question shown to the signer and its width. The actions and how to choose them are in REFERENCE.md. Ask about the cases only the customer can settle: a value typed twice by the signer, a value Entropia could fill (the signer's name, the data room's name), a note meant for a reviewer, where the signature goes when the template has none.

Done when the customer has confirmed an action for every field, and `plan.json` holds them all.

## 3. Convert

```
python3 scripts/convert.py <template.docx> plan.json <template>-entropia.docx
```

It refuses a plan that skips a field or carries an invalid anchor; fix the plan and run it again. The output is always a clean Word package with every tag white.

Done when it writes the file.

## 4. Verify

```
pip install pypdfium2   # once, for the layout check
python3 scripts/verify.py <template>-entropia.docx
```

Each `PROBLEM` line names its fix in plan terms (`pad`, `width`, `line_pt`). Apply it to `plan.json`, then convert and verify again. Changing one field's `pad` moves every anchor after it on the paragraph, so re-verify after each change.

Done when it prints `OK: ready to upload`. When it prints `layout not verified`, the layout check could not run here (no LibreOffice): say so to the customer in step 5, as the test there then carries the whole layout check.

## 5. Hand over

Give the customer the file, and these steps in their language:

1. In the data room, open **Settings > Terms & NDA**, create the document, choose **Electronic signature**, and upload the file. The dialog lists the fields it found.
2. Before inviting members, send the NDA to one test member (for example a second email of their own) and open its signing page: each field sits on its line and the anchors stay invisible.

Done when the customer has the file and the two steps.
