# Entropia skills for Claude

Skills that help Entropia customers prepare their documents for an [Entropia](https://entropia.io) data room, with Claude.

## Skills

| Skill | What it does |
|---|---|
| [`entropia-nda-template`](plugins/data-room/skills/entropia-nda-template/SKILL.md) | Turns an NDA in Word into a template Entropia can send for electronic signature through Youtrust: the blanks, dotted lines and `[bracket]` fields become fields the signer fills in, or values Entropia fills, and the file is checked the way Entropia and Youtrust check it. |

## Install

**Claude and Claude Cowork.** Download `entropia-nda-template.zip` from the [latest release](../../releases/latest), then upload it in Claude's settings, in the Skills section. Then ask Claude: *"Prepare my NDA for electronic signature in Entropia"* and attach the `.docx`.

**Claude Code.**

```
/plugin marketplace add entropia-labs/claude-skills
/plugin install data-room@entropia
```

## What you need

- Your NDA as a Word `.docx` file. A PDF cannot be edited reliably.
- Python 3. Claude's code environment has it.
- For the layout check: LibreOffice and `pip install pypdfium2`. Without them, Claude tells you, and the test signature in Entropia carries that check.

## Develop

```
python3 -m unittest discover -s tests
python3 scripts/build_zip.py   # writes dist/<skill>.zip
```

The tests run on a synthetic NDA built by `tests/make_fixture.py`. Keep customer documents out of this repository.
