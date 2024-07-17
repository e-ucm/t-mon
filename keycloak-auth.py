import json
import logging
import os

from flask import Flask, g, jsonify, redirect, url_for, session
from flask_oidc import OpenIDConnect
import requests

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config.update({
    'SECRET_KEY': 'SomethingNotEntirelySecret',
    'TESTING': True,
    'DEBUG': True,
    'OIDC_CLIENT_SECRETS': os.path.join(basedir, 'client_secrets.json'),
    'OIDC_ID_TOKEN_COOKIE_SECURE': False,
    'OIDC_USER_INFO_ENABLED': True,
    'OIDC_OPENID_REALM': 'simva',
    'OIDC_SCOPES': ['openid', 'email', 'profile'],
    'OIDC_INTROSPECTION_AUTH_METHOD': 'client_secret_post'
})
hosturl = 'http%3A%2F%2Flocalhost%3A5000%2F'

oidc = OpenIDConnect(app)


@app.route('/')
def home():
    print(f"Accessing route /")
    if oidc.user_loggedin:
        user_info = session.get('oidc_auth_profile', {})
        preferred_username = user_info.get('preferred_username')
        return (f"""Hello, {preferred_username}, 
                <a href="{url_for("private")}">See private</a>
                <a href="{url_for("logoutkeycloak")}">Log out</a>""")
    else:
        return f'Welcome anonymous, <a href="{url_for("private")}">Log in</a>'


@app.route('/private')
@oidc.require_login
def private():
    """Example for protected endpoint that extracts private information from the OpenID Connect id_token.
       Uses the accompanied access_token to access a backend service.
    """
    print(f"Accessing route /private")
    issuer_url = oidc.client_secrets.get('issuer')
    client_id = oidc.client_secrets.get('client_id')

    if oidc.user_loggedin:
        user_info = session.get('oidc_auth_profile', {})
        user_id = user_info.get('sub')
        email = user_info.get('email')
        preferred_username = user_info.get('preferred_username')
        try:
            # Use the token stored in session
            access_token = oidc.get_access_token()
            logger.debug(f'access_token=<{access_token}>')
            headers = {'Authorization': f'Bearer {access_token}'}
            # YOLO
            greeting = requests.get('http://localhost:8080/greeting', headers=headers).text
        except:
            logger.debug("Could not access greeting-service")
            greeting = f"Hello {preferred_username}"
    else:
        return jsonify({'error': 'User not logged in'})
    redirect_uri = url_for('private', _external=True)
    return (f"""{greeting} your email is {email} and your user_id is {user_id}!
           <ul>
             <li><a href="/">Home</a></li>
             <li><a href="{issuer_url}/account?referrer={client_id}&referrer_uri={redirect_uri}">Account</a></li>
           </ul>""")

@app.route('/api', methods=['POST'])
@oidc.accept_token(require_token=True, scopes_required=['openid'])
def api():
    """OAuth 2.0 protected API endpoint accessible via AccessToken"""

    print(f"Accessing route /api")
    user_info = session.get('oidc_auth_profile', {})
    preferred_username = user_info.get('preferred_username')
    return json.dumps({'hello': f"Welcome {preferred_username}"})

@app.route('/logoutkeycloak')
@oidc.require_login
def logoutkeycloak():
    """Performs local logout by removing the session cookie."""

    print(f"Accessing route /logoutkeycloak")
    redirect_uri = url_for('home', _external=True)  # Replace 'home' with your home route
    issuer_url = oidc.client_secrets.get('issuer')
    
    logger.debug(f'Received logout request. Redirect URI: {redirect_uri}, Issuer URL: {issuer_url}')
    if oidc.user_loggedin:
        # Get the ID token from the session (assuming it's stored in 'id_token' key)
        auth_token = session.get('oidc_auth_token', {})
        logger.debug(auth_token)
        id_token = auth_token.get('id_token')
        logger.debug(f'User logged in. Id token: {id_token}')

        # Log out locally
        oidc.logout()
        logger.debug('Local logout successful.')

        # Clear the session
        session.clear()
        logger.debug('Session cleared.')

        # Construct the Keycloak logout URL
        keycloak_base_url = f'{issuer_url}/protocol/openid-connect/logout'
        keycloak_logout_url = f'{keycloak_base_url}?id_token_hint={id_token}&post_logout_redirect_uri={redirect_uri}'
        logger.debug(f'Keycloak logout URL: {keycloak_logout_url}')
        return redirect(keycloak_logout_url)
    else:
        logger.debug('User not logged in. Redirecting to home.')
        return redirect(redirect_uri)
 
if __name__ == '__main__':
    app.run()