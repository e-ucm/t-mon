"""
Roles carried by the signed-in SimVA user.

SimVA issues a fixed set of Keycloak roles: ``administrator``, ``researcher``,
``teaching-assistant``, ``teacher``, ``student`` and ``default-role``. T-Mon only
needs to know whether the user may change the deployed default dashboard, which
is the ``administrator`` role, but the whole set is read so other screens can
reuse it without another provider lookup.
"""
import base64
import json

ROLE_ADMINISTRATOR = "administrator"

# The roles SimVA issues. Kept together so a typo is visible in one place.
KNOWN_ROLES = (
    "administrator",
    "researcher",
    "teaching-assistant",
    "teacher",
    "student",
    "default-role",
)


def roles_from_claims(claims):
    """
    Read role names out of an OIDC profile or access-token payload.

    Keycloak may put them at the top level, under ``realm_access.roles``, under
    ``resource_access.<client>.roles``, or (for some deployments) under ``groups``.
    All four shapes are accepted; anything else is ignored.

    Args:
        claims (dict): The decoded profile or token payload.

    Returns:
        set: The role names it carries.
    """
    if not isinstance(claims, dict):
        return set()
    roles = set()
    for value in (claims.get("roles"), claims.get("groups"),
                  (claims.get("realm_access") or {}).get("roles")):
        if isinstance(value, list):
            roles.update(str(role) for role in value if role)
    resources = claims.get("resource_access") or {}
    if isinstance(resources, dict):
        for resource in resources.values():
            if isinstance(resource, dict) and isinstance(resource.get("roles"), list):
                roles.update(str(role) for role in resource["roles"] if role)
    return roles


def _token_claims(token):
    """Decode the payload of a JWT the OIDC provider already accepted."""
    if not isinstance(token, str) or token.count(".") != 2:
        return {}
    payload = token.split(".")[1]
    try:
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, UnicodeDecodeError):
        return {}
    return claims if isinstance(claims, dict) else {}


def current_roles():
    """The role names carried by the current login, or an empty set."""
    try:
        from flask import session
    except ImportError:
        return set()
    try:
        profile = session.get("oidc_auth_profile") or {}
        token = (session.get("oidc_auth_token") or {}).get("access_token")
    except RuntimeError:
        # Outside a request there is no login to read, which is not an error.
        return set()
    roles = roles_from_claims(profile)
    roles |= roles_from_claims(_token_claims(token))
    return roles


def is_admin():
    """Whether the signed-in user may edit the deployed default dashboard."""
    return ROLE_ADMINISTRATOR in current_roles()
