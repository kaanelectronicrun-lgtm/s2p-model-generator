#!/usr/bin/env python3
"""Package a clean source release into releases/s2p-<version>.zip.

Includes source, docs, examples and tests; excludes generated outputs, caches,
temp files and VCS. Version is read from src/s2p_tool/__init__.py (single source).

    python make_release.py
"""
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))

INCLUDE_FILES = ["run.py", "plot_error.py", "make_release.py", "_entry.py",
                 "requirements.txt", "README.md", "GUIDE.md", "CHANGELOG.md",
                 "TODO.md", "OTHER_MACHINE_TEST.md"]
INCLUDE_DIRS = ["src", "tests", "components"]
EXCLUDE_DIRS = {"__pycache__", ".git", "outputs", ".pytest_cache"}
EXCLUDE_EXT = {".pyc", ".pyo"}


def _version() -> str:
    txt = open(os.path.join(ROOT, "src", "s2p_tool", "__init__.py"),
               encoding="utf-8").read()
    return re.search(r'__version__\s*=\s*"([^"]+)"', txt).group(1)


def _keep(path: str) -> bool:
    parts = set(path.replace("\\", "/").split("/"))
    if parts & EXCLUDE_DIRS:
        return False
    return os.path.splitext(path)[1] not in EXCLUDE_EXT


def main() -> None:
    ver = _version()
    rel_dir = os.path.join(ROOT, "releases")
    os.makedirs(rel_dir, exist_ok=True)
    out = os.path.join(rel_dir, f"s2p-{ver}.zip")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in INCLUDE_FILES:
            p = os.path.join(ROOT, f)
            if os.path.isfile(p):
                z.write(p, os.path.join(f"s2p-{ver}", f))
                n += 1
        for d in INCLUDE_DIRS:
            for base, dirs, files in os.walk(os.path.join(ROOT, d)):
                dirs[:] = [x for x in dirs if x not in EXCLUDE_DIRS]
                for fn in files:
                    full = os.path.join(base, fn)
                    rel = os.path.relpath(full, ROOT)
                    if _keep(rel):
                        z.write(full, os.path.join(f"s2p-{ver}", rel))
                        n += 1
    size = os.path.getsize(out) / 1024
    print(f"[OK] {out}  ({n} files, {size:.0f} KB)")


if __name__ == "__main__":
    main()
