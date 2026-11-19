import importlib

import pytest

# Every module either application loads, either at import time or on demand: pages,
# widgets and their shared helpers. A module that first fails here would fail the
# same way on the very server it ships on, so it fails the build too.
MODULES = [
    "LoadProcessStatements",
    "TMonApp",
    "TMonSimvaApp",
    "TMonWidgets.ActivityFilter",
    "TMonWidgets.ChartBuilder",
    "TMonWidgets.DefaultDashboard",
    "TMonWidgets.EmptyFigure",
    "TMonWidgets.GraphTypes",
    "TMonWidgets.MultiSelector",
    "TMonWidgets.PageConfig",
    "TMonWidgets.SimvaBrowserWidget",
    "TMonWidgets.TMonWidget",
    "TMonWidgets.UploadWidget",
    "SimvaBrowser.KeycloakClient",
    "SimvaBrowser.MinioAdminBrowser",
    "SimvaBrowser.MinioBrowser",
    "SimvaBrowser.SimvaBrowser",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    importlib.import_module(module_name)
