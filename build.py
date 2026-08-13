#!/usr/bin/env python3
"""Package magpie_swatches/ into a release zip.

    python build.py

Reads the version straight out of blender_manifest.toml (the single source of
truth -- see the family's playbook note on why that file must only ever be
hand-edited, never touched by a scripted find/replace: a version bump that
silently fails to match leaves Blender thinking it already has the "new"
build and it refuses to update). This script only READS that file; it never
writes to it.

Zips the CONTENTS of magpie_swatches/ (not the folder itself), so
blender_manifest.toml lands at the root of the zip -- that is where Blender's
installer expects it. Skips __pycache__ and any other generated cruft.

Run from a clean checkout of the release tag; this script does not verify
that for you (no assumption about the checkout having a .git directory at
all), but a dirty working tree gets zipped as-is, so check `git status` first.
"""

import sys
import zipfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    print("ERROR: Python 3.11+ is required (for tomllib).", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent
PACKAGE_DIR = REPO_ROOT / "magpie_swatches"
MANIFEST = PACKAGE_DIR / "blender_manifest.toml"

# Anything under magpie_swatches/ whose name matches one of these is left out
# of the zip -- build artifacts, never source.
SKIP_NAMES = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def read_version() -> str:
    with MANIFEST.open("rb") as f:
        manifest = tomllib.load(f)
    version = manifest.get("version")
    if not version:
        print(f"ERROR: no 'version' key in {MANIFEST}", file=sys.stderr)
        sys.exit(1)
    return str(version)


def iter_package_files():
    for path in sorted(PACKAGE_DIR.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_NAMES for part in path.parts):
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        yield path


def build() -> Path:
    if not MANIFEST.is_file():
        print(f"ERROR: {MANIFEST} not found -- run this from the repo root.",
              file=sys.stderr)
        sys.exit(1)

    version = read_version()
    out_path = REPO_ROOT / f"magpie_swatches-{version}.zip"

    # Refuse to overwrite. Two house rules meet here: every change ships as
    # its own version, and old zips are kept forever. Silently replacing a
    # zip breaks both at once -- and worse, reinstalling an unchanged version
    # number can leave Blender convinced it already has this build and skip
    # the update, so the bug you are chasing is in a file that never loaded.
    # Bump the version in blender_manifest.toml (by hand, in an editor -- a
    # scripted find/replace that quietly fails to match is exactly how a
    # stale manifest ships) and run again.
    if out_path.exists():
        print(f"ERROR: {out_path.name} already exists.\n"
              f"       Bump 'version' in {MANIFEST.name} and run again -- "
              f"do not overwrite a released zip.", file=sys.stderr)
        sys.exit(1)

    files = list(iter_package_files())
    if not files:
        print("ERROR: no files found under magpie_swatches/ -- refusing to "
              "write an empty zip.", file=sys.stderr)
        sys.exit(1)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            # Relative to PACKAGE_DIR, not REPO_ROOT, so the archive root IS
            # the package contents -- blender_manifest.toml ends up at the
            # zip's own root, exactly where Blender's installer looks.
            zf.write(path, arcname=path.relative_to(PACKAGE_DIR))

    # Self-check: fail loudly rather than ship a zip Blender can't install.
    with zipfile.ZipFile(out_path) as zf:
        names = set(zf.namelist())
    if "blender_manifest.toml" not in names:
        print("ERROR: blender_manifest.toml is not at the zip root -- "
              "something is wrong with the packaging, refusing to ship "
              f"{out_path}.", file=sys.stderr)
        out_path.unlink()
        sys.exit(1)

    print(f"Built {out_path} ({out_path.stat().st_size:,} bytes, "
          f"{len(files)} files, version {version})")
    return out_path


if __name__ == "__main__":
    build()
