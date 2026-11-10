"""
Trust of the deployment's private certificate authority.

A SIMVA deployment signs every service it fronts (Keycloak, SimVA API, LRS, MinIO)
with its own root CA, so the dashboard must be told to trust that CA or every
HTTPS request it makes fails with
ssl.SSLCertVerificationError: self-signed certificate in certificate chain.

The tests pin down where the trust anchor is read from, and what it must not do:
verification is never disabled, only pointed at the deployment's CA. The network
half of the story (requests carrying verify=ca_file) is pinned by the constructor
tests, since every request the browser makes goes through the resolved self.ca_file.
"""

import json
import os

import pytest
from jwt import JWT, jwk_from_dict

from SimvaBrowser.KeycloakClient import KeycloakClient
from SimvaBrowser.SimvaBrowser import SimvaBrowser

# Key material for the access tokens the tests carry. The browser decodes them
# without verifying (do_verify=False), so any valid JWK will do.
TEST_JWK=jwk_from_dict({"kty": "oct", "k": "c2VjcmV0"})


def make_auth():
    """An auth payload carrying an access token SimvaBrowser can decode."""
    token=JWT().encode({"sub": "user"}, TEST_JWK, alg="HS256")
    return {"oidc_auth_token": {"access_token": token}}


def write_secrets(path, web=None):
    """Write a minimal secrets file, with the given `web` section merged in."""
    secrets={
        "web": web or {},
        "simva": {"api_url": "https://simva-api.example.org/"},
        "lrs": {},
    }
    path.write_text(json.dumps(secrets))
    return path


@pytest.fixture
def ca_file(tmp_path):
    """An existing file standing in for the deployment's root CA."""
    ca=tmp_path / "rootCA.pem"
    ca.write_text("not a real certificate, but a file that exists")
    return ca


@pytest.fixture
def clean_ca_env(monkeypatch):
    """The environment of a fresh deployment, with no CA bundle preset."""
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)


def make_browser(monkeypatch, tmp_path, web=None, **kwargs):
    """A SimvaBrowser built against a temp secrets file, without any network."""
    secrets=write_secrets(tmp_path / "client_secrets.json", web)
    # The constructor normally reaches the SimVA API and MinIO; the CA resolution
    # happens before any of that, so those calls are stubbed out here.
    monkeypatch.setattr(SimvaBrowser, "_check_health_endpoint", lambda self: None)
    monkeypatch.setattr(SimvaBrowser, "_load_selected_studies_from_simva_api", lambda self: None)
    monkeypatch.setattr(SimvaBrowser, "_update_files", lambda self: None)
    return SimvaBrowser(make_auth(), client_secret_file=str(secrets), **kwargs)


def test_simvabrowser_trusts_ca_from_secrets(monkeypatch, tmp_path, ca_file):
    browser=make_browser(monkeypatch, tmp_path, web={"ssl_cert_file": str(ca_file)})
    assert browser.ca_file == str(ca_file)


def test_simvabrowser_explicit_ca_file_wins_over_secrets(monkeypatch, tmp_path, ca_file):
    explicit=tmp_path / "explicit.pem"
    explicit.write_text("another bundle")
    browser=make_browser(
        monkeypatch, tmp_path,
        web={"ssl_cert_file": str(ca_file)},
        ca_file=str(explicit),
    )
    assert browser.ca_file == str(explicit)


def test_simvabrowser_drops_missing_ca_file(monkeypatch, tmp_path):
    # A bundle that is not there must fall back to default verification instead of
    # failing every later request with an OSError on the missing file.
    browser=make_browser(
        monkeypatch, tmp_path, web={"ssl_cert_file": "/nowhere/rootCA.pem"}
    )
    assert browser.ca_file is None


def test_simvabrowser_without_ssl_cert_file_keeps_default(monkeypatch, tmp_path):
    browser=make_browser(monkeypatch, tmp_path, web={})
    assert browser.ca_file is None


def test_keycloak_client_publishes_ca_bundle(clean_ca_env, tmp_path, ca_file):
    secrets=write_secrets(tmp_path / "keycloak_secrets.json", web={
        "client_id": "tmon",
        "client_secret": "secret",
        "issuer": "https://sso.example.org/realms/simva",
        "ssl_cert_file": str(ca_file),
    })
    KeycloakClient(client_secret_file=str(secrets), homepage=False)
    assert os.environ["REQUESTS_CA_BUNDLE"] == str(ca_file)
    assert os.environ["SSL_CERT_FILE"] == str(ca_file)


def test_keycloak_client_keeps_deployment_bundle(clean_ca_env, monkeypatch, tmp_path, ca_file):
    # An explicit deployment value stays in control: the secrets file must not
    # override what the environment was already told to trust.
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/deployment/ca.pem")
    secrets=write_secrets(tmp_path / "keycloak_secrets.json", web={
        "client_id": "tmon",
        "client_secret": "secret",
        "issuer": "https://sso.example.org/realms/simva",
        "ssl_cert_file": str(ca_file),
    })
    KeycloakClient(client_secret_file=str(secrets), homepage=False)
    assert os.environ["REQUESTS_CA_BUNDLE"] == "/deployment/ca.pem"


def test_keycloak_client_without_ca_file_sets_nothing(clean_ca_env, tmp_path):
    secrets=write_secrets(tmp_path / "keycloak_secrets.json", web={
        "client_id": "tmon",
        "client_secret": "secret",
        "issuer": "https://sso.example.org/realms/simva",
    })
    KeycloakClient(client_secret_file=str(secrets), homepage=False)
    assert "REQUESTS_CA_BUNDLE" not in os.environ
    assert "SSL_CERT_FILE" not in os.environ
