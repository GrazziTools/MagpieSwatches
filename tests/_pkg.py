"""Import the add-on's engine WITHOUT running magpie_swatches/__init__.py.

The package root imports ui/, which imports panels and operators. Engine tests
have no business dragging that in -- and this way the engine stays testable even
while the UI is half-written. We register a synthetic package object whose
__path__ points at the source folder, so relative imports (`from ..constants`)
still resolve normally.
"""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load():
    if "magpie_swatches" not in sys.modules:
        pkg = types.ModuleType("magpie_swatches")
        pkg.__path__ = [str(ROOT / "magpie_swatches")]
        sys.modules["magpie_swatches"] = pkg
    return sys.modules["magpie_swatches"]
