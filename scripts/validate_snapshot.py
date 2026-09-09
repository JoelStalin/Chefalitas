from __future__ import annotations

import ast
import re
import sys
import xml.etree.ElementTree as element_tree
from pathlib import Path


root = Path(__file__).resolve().parents[1]
errors: list[str] = []

for python_file in root.joinpath("addons").rglob("*.py"):
    try:
        ast.parse(python_file.read_text(encoding="utf-8"), filename=str(python_file))
    except Exception as error:
        errors.append(f"python:{python_file.relative_to(root)}:{error}")

for xml_file in root.joinpath("addons").rglob("*.xml"):
    try:
        element_tree.parse(xml_file)
    except Exception as error:
        errors.append(f"xml:{xml_file.relative_to(root)}:{error}")

sensitive_assignment = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key)\s*[:=]\s*['\"][^'$<{\"]+"
)
for candidate in root.rglob("*"):
    if not candidate.is_file() or ".git" in candidate.parts or "dist" in candidate.parts:
        continue
    if candidate.suffix.lower() not in {".py", ".js", ".json", ".yml", ".yaml", ".toml", ".ini", ".conf"}:
        continue
    try:
        contents = candidate.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    if sensitive_assignment.search(contents):
        errors.append(f"possible-secret:{candidate.relative_to(root)}")

print(f"validation_errors={len(errors)}")
for error in errors:
    print(error)
sys.exit(bool(errors))
