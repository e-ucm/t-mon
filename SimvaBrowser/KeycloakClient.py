import json
import logging
import os
from flask import Flask, redirect, url_for, session, request
from flask_oidc import OpenIDConnect
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class KeycloakClient:
    def __init__(self, client_secret_file="client_secrets.json", homepage = True):
        self.flaskServer = Flask(__name__)
        self.flaskServer.wsgi_app = ProxyFix(self.flaskServer.wsgi_app, x_for=1, x_host=1, x_port=1, x_proto=1, x_prefix=1)
        basedir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
        self.flaskServer.config.update({
            'SECRET_KEY': 'SomethingNotEntirelySecret',
            'TESTING': True,
            'DEBUG': True,
            'OIDC_CLIENT_SECRETS': os.path.join(basedir, client_secret_file),
            'OIDC_ID_TOKEN_COOKIE_SECURE': False,
            'OIDC_USER_INFO_ENABLED': True,
            'OIDC_OPENID_REALM': 'simva',
            'OIDC_SCOPES': ['openid', 'email', 'profile', 'roles', 'web-origins'],
            'OIDC_INTROSPECTION_AUTH_METHOD': 'client_secret_post'
        })
        self.oidc = OpenIDConnect(self.flaskServer)
        issuer_url = self.oidc.client_secrets.get('issuer')
        client_id = self.oidc.client_secrets.get('client_id')
        httpSecure= "https" if self.oidc.client_secrets.get('SECURE', "False") == "true" else "http"
        host=self.oidc.client_secrets.get('HOST', '0.0.0.0')
        port=self.oidc.client_secrets.get('PORT', 8050)
        self.accountpage=f"{issuer_url}/account?referrer={client_id}&referrer_uri={httpSecure}://{host}:{port}"
        self.homepage="/"
        if homepage:
            @self.flaskServer.route(self.homepage)
            def home():
                print(f"Accessing route /")
                if self.oidc.user_loggedin:
                    user_info = session.get('oidc_auth_profile', {})
                    user_id = user_info.get('sub')
                    email = user_info.get('email')
                    preferred_username = user_info.get('preferred_username')
                    redirect_uri = url_for('home', _external=True)
                    return (f"""Hello {preferred_username}, your email is {email} and your user_id is {user_id}!
                       <ul>
                         <li><a href="{self.accountpage}{redirect_uri}">Account</a></li>
                         <li><a href="/logoutkeycloak">Logout</a></li>
                       </ul>""")
                else:
                    return f'Welcome anonymous, <a href="{url_for("login")}">Log in</a>'
        self.login="/login"
        @self.flaskServer.route(self.login)
        @self.oidc.require_login
        def login():
            if homepage:
                redirect_uri = f"{url_for('home', _external=True)}"
            else:
                redirect_uri = request.base_url.replace(self.login,self.homepage)
            print(f"Accessing route /login")
            return redirect(redirect_uri)
        
        self.apiroute='/api'
        @self.flaskServer.route(self.apiroute, methods=['POST'])
        @self.oidc.accept_token(require_token=True, scopes_required=['openid'])
        def api():
            """OAuth 2.0 protected API endpoint accessible via AccessToken"""
            print(f"Accessing route /api")
            user_info = session.get('oidc_auth_profile', {})
            preferred_username = user_info.get('preferred_username')
            return json.dumps({'hello': f"Welcome {preferred_username}"})
        
        self.logoutroute='/logoutkeycloak'
        @self.flaskServer.route(self.logoutroute)
        def logoutkeycloak():
            """Performs local logout by removing the session cookie."""
            print(f"Accessing route /logoutkeycloak")
            if homepage:
                redirect_uri = f"{url_for('home', _external=True)}"
            else:
                redirect_uri = request.base_url.replace(self.logoutroute,self.homepage)
            
            issuer_url = self.oidc.client_secrets.get('issuer')
            logger.debug(f'Received logout request. Redirect URI: {redirect_uri}, Issuer URL: {issuer_url}')
            if self.oidc.user_loggedin:
                # Get the ID token from the session (assuming it's stored in 'id_token' key)
                auth_token = session.get('oidc_auth_token', {})
                logger.debug(auth_token)
                id_token = auth_token.get('id_token')
                logger.debug(f'User logged in. Id token: {id_token}')

                # Log out locally
                self.oidc.logout()
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
   flask = KeycloakClient()
   flask.flaskServer.run(debug=True, port=5000)