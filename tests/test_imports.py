import importlib

import pytest

# Every module either application loads, either at import time or on demand: pages,
# widgets, visualisations and their shared helpers. A module that first fails here
# would fail the same way on the very server it ships on, so it fails the build too.
MODULES = [
    "LoadProcessStatements",
    "TMonApp",
    "TMonSimvaApp",
    "TMonWidgets.ActivityFilter",
    "TMonWidgets.ChartBuilder",
    "TMonWidgets.MultiSelector",
    "TMonWidgets.SimvaBrowserWidget",
    "TMonWidgets.TMonWidget",
    "TMonWidgets.UploadWidget",
    "SimvaBrowser.KeycloakClient",
    "SimvaBrowser.MinioAdminBrowser",
    "SimvaBrowser.MinioBrowser",
    "SimvaBrowser.SimvaBrowser",
    "vis.xAPISGPlayersProgress",
    "vis.xAPISGVideosSeenSkipped",
    "vis.xAPISGnoDataToFillVisualization",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    importlib.import_module(module_name)