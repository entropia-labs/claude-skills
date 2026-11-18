"""Build the zip a customer uploads in Claude: one folder per skill, SKILL.md at its root.

    python3 scripts/build_zip.py
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "plugins", "data-room", "skills")
DIST = os.path.join(ROOT, "dist")

os.makedirs(DIST, exist_ok=True)
for skill in sorted(os.listdir(SKILLS)):
    source = os.path.join(SKILLS, skill)
    target = os.path.join(DIST, f"{skill}.zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder, folders, files in os.walk(source):
            folders[:] = sorted(f for f in folders if f != "__pycache__")
            for name in sorted(files):
                path = os.path.join(folder, name)
                archive.write(path, os.path.join(skill, os.path.relpath(path, source)))
    print(f"built {os.path.relpath(target, ROOT)}")
