from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = ROOT / "vendor" / "GALAXEA-A1Z"
for path in (SDK_ROOT, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
