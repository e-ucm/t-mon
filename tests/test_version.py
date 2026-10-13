import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_root_version_is_defined():
    text = (REPO_ROOT / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    assert match, "root __init__.py must define __version__"
    assert re.fullmatch(r"\d+\.\d+\.\d+", match.group(1)), match.group(1)