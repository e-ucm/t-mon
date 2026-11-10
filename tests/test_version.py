import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# The package init under src/ holds the version; the CI release check reads it too.
PACKAGE_INIT = REPO_ROOT / "src" / "__init__.py"


def test_package_version_is_defined():
    text = PACKAGE_INIT.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    assert match, "src/__init__.py must define __version__"
    assert re.fullmatch(r"\d+\.\d+\.\d+", match.group(1)), match.group(1)