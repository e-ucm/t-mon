"""T-Mon brand marks, embedded as data URIs.

The header used to point at ``/assets/logo-*.png``. That works when the app is
served at the root, but not when it sits behind a proxy that adds a path prefix:
the browser then asks for the root URL and gets the login page instead of an
image, leaving the alt text on screen. Embedding the bytes here means the logo
renders wherever the app is deployed, with no extra request at all.
"""
import base64
import os

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


def _data_uri(filename, mime="image/png"):
    with open(os.path.join(_ASSETS_DIR, filename), "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


LOGO_SRC = _data_uri("logo-tmon.png")
WORDMARK_SRC = _data_uri("logo-name-tmon.png")

# Icons used by the SIMVA-style header. Embedded like the logo so a proxy that
# breaks `/assets/...` cannot leave empty image boxes in the bar.
USER_ICON_SRC = _data_uri("user.png")
POWER_ICON_SRC = _data_uri("power-button-off.png")
INFO_ICON_SRC = _data_uri("information.png")
CONTACT_ICON_SRC = _data_uri("eucm_icon.ico", "image/x-icon")
