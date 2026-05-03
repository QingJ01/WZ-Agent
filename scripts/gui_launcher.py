from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

src_root_str = str(SRC_ROOT)
if src_root_str not in sys.path:
    sys.path.insert(0, src_root_str)

from wzry_ai.app.gui_launcher import main as _packaged_main


def main(argv=None) -> int:
    return _packaged_main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
