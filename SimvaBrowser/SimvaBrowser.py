from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
import re

import requests
from jwt import JWT
import os
import json


# Keys under which an LRS may wrap the statement list in its response body.
LRS_STATEMENT_KEYS = ("statements", "data", "results")

# Keys under which an LRS advertises the next page of statements.
LRS_MORE_KEYS = ("more_url", "more")

# Version announced to the LRS on every statements request. The header is not
# optional there: a request without it is rejected instead of answered.
LRS_API_VERSION = "2.0.0"

# Path of the xAPI prefix, and of the statements resource under it. The endpoint in
# the secrets file may or may not already carry the prefix.
LRS_XAPI_PATH = "xapi"
LRS_STATEMENTS_PATH = "statements"

# Upper bound on pages followed for a single query. A malformed LRS that keeps
# advertising a next page would otherwise loop forever. The bound is generous on
# purpose: an LRS that caps a page at a few dozen statements needs thousands of
# pages to return a whole classroom session, and stopping halfway would silently
# truncate the very data the read is for.
LRS_MAX_PAGES = 500

# How far back each incremental query reaches behind the previous one, in seconds.
# An LRS can index a statement a moment after it was stored, so a window closed at
# "now" would step over it and never return it. Re-reading a short tail catches such
# late arrivals on a later poll; the statements seen again are dropped by identity,
# so the overlap costs a request and not a duplicate.
LRS_LAG_SECONDS = 60

# Seconds any single LRS request may take. A read walks a chain of pages, so one
# request that never answers would leave the dashboard waiting on it forever, and a
# read that gives up is retried with the very same window on the next poll anyway.
LRS_REQUEST_TIMEOUT = 30


def extract_statements(payload):
    """
    Return the list of xAPI statements carried by an LRS payload.

    An LRS answers either with a bare statement array or with an envelope such as
    {"statements": [...]}, and this module also accumulates its own plain arrays, so
    all three shapes are accepted.

    Args:
        payload: A list of statements, an envelope dict, or None.

    Returns:
        list: The statements. A dict carrying no known envelope key is returned as a
            single element list, so a lone statement is never silently dropped.
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in LRS_STATEMENT_KEYS:
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload]
    return []


def statement_identity(statement):
    """
    Build a stable identity for an xAPI statement, used to deduplicate polls.

    Prefers the statement id, which the LRS guarantees unique per statement. Falls back
    to a hash of the whole statement for statements without an id, so polling still
    converges instead of growing the data set without bound.
    """
    if isinstance(statement, dict):
        identifier = statement.get("id")
        if identifier:
            return f"id:{identifier}"
        return "hash:" + json.dumps(statement, sort_keys=True, default=str)
    return "hash:" + json.dumps(statement, sort_keys=True, default=str)


def merge_statements(existing, incoming):
    """
    Merge newly polled statements into the ones already held.

    Dedupes on statement identity, keeping the incoming copy on collision so an
    updated statement replaces its earlier version, and orders the result by
    timestamp so the charts and the data table stay chronological.

    Args:
        existing: Statements already loaded for the current selection.
        incoming: Statements returned by the latest poll.

    Returns:
        tuple: (merged statements, count of statements that were actually new).
    """
    merged = {}
    for statement in extract_statements(existing):
        merged[statement_identity(statement)] = statement
    known = set(merged)
    added = 0
    for statement in extract_statements(incoming):
        identity = statement_identity(statement)
        if identity not in known:
            added += 1
        merged[identity] = statement

    def sort_key(statement):
        timestamp = statement.get("timestamp") if isinstance(statement, dict) else None
        # Statements without a timestamp sort last, keeping the rest chronological.
        return (timestamp is None, timestamp or "")

    return sorted(merged.values(), key=sort_key), added


def next_lrs_page_url(data, base_url=None):
    """
    Return the URL of the next batch of statements advertised by an LRS result.

    An xAPI `statements` response is a Multi-Statements LRS Result: besides the
    statements it may carry a `more` (xAPI 1.0.2) or `more_url` (xAPI 2.0) key holding
    the URL of the following page, and the client is expected to follow it until it is
    absent. Some LRS also express it as a link object, so a few shapes are accepted.

    Args:
        data: A decoded LRS response body.
        base_url (str, optional): Used to resolve a relative `more` value.

    Returns:
        str or None: The absolute next-page URL, or None when this is the last page.
    """
    if not isinstance(data, dict):
        return None
    for key in LRS_MORE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value if value.startswith("http") else _join_url(base_url, value)
        if isinstance(value, dict):
            for nested in ("href", "url", "more_url", "more"):
                if isinstance(value.get(nested), str) and value[nested]:
                    return value[nested]
    return None


def _join_url(base_url, path):
    """Resolve a relative LRS page path against the API base."""
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def lrs_origin_url(url):
    """
    Return the scheme and host of a URL, the base a relative `more` page resolves on.

    An LRS advertises the next batch of statements as a path
    (`/xapi/statements?...`), which only means something against the very server
    that handed it over.

    Args:
        url (str): An absolute URL.

    Returns:
        str or None: The origin, or None when the URL is missing or not absolute.
    """
    if not url:
        return None
    parts = urlsplit(str(url).strip())
    if not parts.scheme or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def lrs_statements_url(endpoint):
    """
    Return the statements URL of the LRS at `endpoint`, or None if it is unusable.

    The endpoint may be configured as the bare host, as the host plus the xAPI
    prefix, or with that prefix already in lower case. The prefix is recognised
    whatever its case and normalised to lower case, because the LRS routes are case
    sensitive and only answer the lower case spelling, while a path of any other
    shape is kept as written.

    Args:
        endpoint (str): The `lrs.endpoint` value from the secrets file.

    Returns:
        str or None: The absolute statements URL, or None when the endpoint is
            missing or is not an absolute URL.
    """
    if not endpoint:
        return None
    parts = urlsplit(str(endpoint).strip())
    if not parts.scheme or not parts.netloc:
        print(f"LRS : endpoint {endpoint!r} is not an absolute URL, the LRS cannot be read directly")
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    if segments and segments[-1].lower() == LRS_XAPI_PATH:
        segments[-1] = LRS_XAPI_PATH
    else:
        segments.append(LRS_XAPI_PATH)
    origin = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
    return f"{origin}{'/'.join(segments)}/{LRS_STATEMENTS_PATH}"


def simva_statement_iri(external_url, *ids):
    """
    Build the activity IRI that SimVA files a statement under.

    SimVA groups the statements of an activity under its own activity URL and those
    of a whole session under the session URL, repeating both in the grouping of
    every statement's context, which is what an LRS query on them matches.

    Args:
        external_url (str): The SimVA external URL, the deployment domain without
            any service subdomain.
        *ids: The path segments identifying the simlet, session and activity, in
            that order, dropping the ones a level does not have.

    Returns:
        str or None: The IRI, or None when the external URL or any of the ids is
            missing. A gap is never closed, since dropping one would address some
            other activity and return its statements in its place.
    """
    base = (external_url or "").strip().rstrip("/")
    if not base:
        return None
    if any(part is None or part == "" for part in ids):
        return None
    return "/".join([base] + [str(part).strip("/") for part in ids])


def utcnow():
    """
    Current UTC time.

    Kept as a function so tests can drive the clock instead of reaching into the
    datetime class, which cannot be patched.
    """
    return datetime.now(timezone.utc)


def parse_lrs_instant(text):
    """
    Parse an ISO 8601 instant into an aware UTC datetime, or None if unreadable.

    Avoids datetime.fromisoformat, which needs Python 3.7. The offset is applied
    explicitly rather than dropped, so a value such as 11:00:00+02:00 is correctly
    read as 09:00:00Z instead of being mistaken for UTC.
    """
    if not text:
        return None
    candidate = text.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    offset = timedelta(0)
    # An offset sits after the time part; the date itself also contains dashes, so
    # only look for one beyond the "T".
    body, separator, tail = candidate.partition("T")
    if separator:
        match = re.search(r"([+-])(\d{2}):?(\d{2})$", tail)
        if match:
            sign = -1 if match.group(1) == "-" else 1
            offset = sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3)))
            tail = tail[:match.start()]
    try:
        parsed = datetime.strptime(f"{body}T{tail}"[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return (parsed - offset).replace(tzinfo=timezone.utc)


def format_lrs_instant(moment):
    """Render an aware datetime as the UTC instant the LRS expects."""
    return moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


class SimvaBrowser:
    """
    A browser interface for interacting with the SimVA (SimVascular) API.

    This class provides methods to navigate studies, tests, activities, and
    retrieve files and LRS (Learning Record Store) data from a SimVA instance.

    Typical usage:

        browser = SimvaBrowser(auth)
        studies = browser.accepted_studies
        browser.select_study(study_id)
        tests = browser.accepted_tests
        browser.select_test(test_id)
        activities = browser.accepted_activities
        browser.select_activity(activity_id)
        file_content = browser.get_file_content()
    """

    def __init__(self, auth, accept='.json', ca_file=None, delimiter='/', client_secret_file="client_secrets.json"):
        """
        Initialize the browser and load the initial SimVA data.

        Loads the client secrets, decodes the OIDC access token, probes the API health
        endpoint to resolve the correct endpoint names, loads the accepted studies and
        performs the initial file listing.

        Args:
            auth (dict): Authentication payload, expected to contain an
                'oidc_auth_token' mapping with an 'access_token' entry.
            accept (str): Accepted content type for trace files.
            ca_file (str, optional): Path to a CA bundle used for MinIO requests.
            delimiter (str): Path delimiter used to build the virtual paths.
            client_secret_file (str): Name of the secrets file, resolved relative to
                the parent directory of this module.
        """
        #GENERAL
        basedir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
        self.secret_file=self._load_secret_file(os.path.join(basedir, client_secret_file))

        #SIMVA
        self.auth = auth
        self.study_directories=[]
        self.accepted_studies=[]
        self.accepted_tests=[]
        self.accepted_activities=[]
        self.actual_study=None
        self.actual_test=None
        self.actual_activity=None
        self.actual_selected_file=None
        self.actual_file_url=None
        self.lrs_data=None
        self.lrs_error=None
        self.analysis_ready=False
        self.analysis_is_activity=None
        self.analysis_object_id=None
        self.until_time=None
        self.from_time=None
        self.health_ok=False
        self.simlet_endpoint=None
        self.session_endpoint=None
        self.activity_endpoint=None
        self.simva_api_url = self.secret_file.get("simva").get("api_url")
        # Statements are read from the LRS itself, with the credentials it gives for
        # that purpose, instead of asking the SimVA API to proxy them: the API only
        # serves what a signed-in user may see and hands it over a page at a time,
        # while the LRS answers the whole query and answers it completely.
        lrs_config=self.secret_file.get("lrs") or {}
        # Optional tuning for the incremental LRS reads; sensible default when absent.
        try:
            self.lrs_lag_seconds=max(0, int(lrs_config.get("lrs_lag_seconds", LRS_LAG_SECONDS)))
        except (TypeError, ValueError):
            self.lrs_lag_seconds=LRS_LAG_SECONDS
        self.lrs_statements_url=lrs_statements_url(lrs_config.get("endpoint"))
        self.lrs_origin=lrs_origin_url(self.lrs_statements_url)
        self.lrs_username=lrs_config.get("username")
        self.lrs_password=lrs_config.get("password")
        # The IRIs SimVA stores its statements under are built from the deployment
        # domain, which the API host only carries as a subdomain.
        self.simva_external_url=self._get_simva_external_url()
        self.lrs_direct=bool(
            self.lrs_statements_url
            and self.lrs_username
            and self.lrs_password
            and self.simva_external_url
        )
        if self.lrs_direct:
            print(
                f"LRS : statements will be read from {self.lrs_statements_url} as {self.lrs_username} "
                f"(statement IRIs under {self.simva_external_url})"
            )
        else:
            missing=[name for name, value in (
                ("lrs.endpoint", self.lrs_statements_url),
                ("lrs.username", self.lrs_username),
                ("lrs.password", self.lrs_password),
                ("simva.external_url", self.simva_external_url),
            ) if not value]
            print(
                f"LRS : {', '.join(missing)} not set in the secrets file, statements will be read "
                "through the SimVA API instead of the LRS itself"
            )
        jwt_parser = JWT()
        self.jwt = self.auth.get('oidc_auth_token', {}).get("access_token")
        self.access_token=jwt_parser.decode(self.jwt, do_verify=False)
        self._check_health_endpoint()
        self._load_selected_studies_from_simva_api()

        #MINIO
        self.accept = accept
        self.ca_file = ca_file
        self.traces_folder = "output"
        self.delimiter = delimiter
        self.base_path = self.traces_folder + self.delimiter
        self.current_path = self.base_path
        self.current_level = 0

        self._update_files()
    
    #GENERAL 
    def _load_secret_file(self, file_path):
        """
        Load secret data from a JSON file.

        Args:
            file_path (str): Path to the JSON secret file.

        Returns:
            dict: Parsed secret data containing configuration values.
        """
        with open(file_path, 'r') as file:
            secret_data = json.load(file)
        return secret_data

    def _get_simva_external_url(self):
        """
        Resolve the SimVA external URL, the base every statement IRI is built from.

        SimVA files its statements under the deployment domain itself, without the
        service subdomain, so `https://simva-api.example.org/` and the IRIs
        `https://example.org/simlets/48/sessions/73` share nothing but that domain.
        The value is read from `simva.external_url` when the secrets file carries it,
        and otherwise derived by dropping the first label of the API host, which is
        how the SimVA stack names its subdomains.

        Returns:
            str or None: The external URL without a trailing slash, or None when it
                is neither configured nor derivable.
        """
        configured=(self.secret_file.get("simva") or {}).get("external_url")
        if configured:
            return str(configured).strip().rstrip("/")
        parts=urlsplit(str(self.simva_api_url or "").strip())
        if not parts.scheme or not parts.netloc or not parts.hostname:
            return None
        labels=parts.hostname.split(".")
        if len(labels) < 2:
            print(
                f"LRS : cannot work out the SimVA external URL from {self.simva_api_url!r}, "
                "set simva.external_url in client_secrets.json to read the LRS directly"
            )
            return None
        return urlunsplit((parts.scheme, ".".join(labels[1:]), "", "", ""))

    def _get_statement_iri(self, objectId, is_activity):
        """
        Return the IRI SimVA files the statements of the current selection under.

        An activity's statements are grouped under its own activity URL and a whole
        session's under the session URL, and an LRS query on either IRI with
        `related_activities` returns them all.

        Args:
            objectId (str): The id of the object to read, an activity id or a
                session id depending on `is_activity`.
            is_activity (bool): True for a single activity, False for a session.

        Returns:
            str or None: The IRI, or None when the study, test or external URL is
                missing, in which case no query can address this selection.
        """
        simlet_id=self._get_id_from_object(self.actual_study, 'simlet', 'id')
        if is_activity:
            session_id=self._get_id_from_object(self.actual_test, 'session', 'id')
            return simva_statement_iri(
                self.simva_external_url, "simlets", simlet_id, "sessions", session_id, "activities", objectId
            )
        return simva_statement_iri(self.simva_external_url, "simlets", simlet_id, "sessions", objectId)

    def _check_health_endpoint(self):
        """
        Decide which SimVA API dialect this server speaks.

        A 200 from the health endpoint means the current API, whose resources are
        simlets/sessions/activities and whose statements come from the LRS. Anything
        else is treated as the legacy API, which exposes studies/tests and stores its
        traces in MinIO.

        That fallback is silent by nature and easy to fall into: a server that has
        moved, renamed or protected its health route answers non-200 and every
        statement request then goes to MinIO instead. The outcome is therefore always
        logged, and `simva.use_lrs` in the secrets file overrides the probe for a
        server known to speak the current API. Only set it on such a server, since it
        also changes the field names read from every response.
        """
        health_url = f"{self.simva_api_url}health"
        headers = {'Content-Type': 'application/json'}
        print("HEALTH : Checking health endpoint...")
        try:
            response = requests.get(health_url, headers=headers, timeout=5)
            self.health_ok = (response.status_code == 200)
            if self.health_ok:
                print("HEALTH : current SimVA API detected, statements will be read from the LRS")
            else:
                print(
                    f"HEALTH : {health_url} answered {response.status_code}, falling back to the "
                    "legacy API (studies/tests, traces from MinIO). If this server does speak the "
                    "current API, set simva.use_lrs to true in client_secrets.json."
                )
        except Exception as e:
            self.health_ok = False
            print(
                f"HEALTH : {health_url} could not be reached ({e}), falling back to the legacy API "
                "(studies/tests, traces from MinIO). If this server does speak the current API, "
                "set simva.use_lrs to true in client_secrets.json."
            )
        forced = (self.secret_file.get("simva") or {}).get("use_lrs")
        if forced is not None:
            self.health_ok = bool(forced)
            print(f"HEALTH : simva.use_lrs={forced} in the secrets file forces health_ok={self.health_ok}")
        if self.health_ok:
            self.simlet_endpoint = "simlets"
            self.session_endpoint = "sessions"
        else:
            self.simlet_endpoint = "studies"
            self.session_endpoint = "tests"
        self.activity_endpoint = "activities"

    def _get_id_from_object(self, object, type, name):
        """
        Extract an ID or name from a SimVA API response object.

        Args:
            object (dict): The API response object.
            type (str): The type of object ('simlet', 'session', or 'activity').
            name (str): Either 'id' or 'name' to extract.

        Returns:
            The requested id or name value, or None if not found.

        Raises:
            ValueError: If name is not 'id' or 'name', or type is invalid when health_ok.
        """
        if object is None:
            return None
        if not name in ["id", "name"]:
            raise ValueError("Invalid name parameter. Must be 'id' or 'name'.")
        if self.health_ok:
            if type not in ["simlet", "session", "activity"]:
                raise ValueError("Invalid type parameter. Must be 'simlet', 'session', or 'activity'.")
            value = object.get(f"{type}_{name}")
            if value is not None:
                return value
            else:
                print(f"Warning: {type}_{name} not found in object. Returning None.")
                return None
        else:
            return object.get(f"_{name}")
        
    #SIMVA API Logged
    def _load_selected_studies_from_simva_api(self):
        """
        Load accepted studies from the SimVA API.

        Sends a GET request to the simlets endpoint with JWT authorization.
        Populates accepted_studies and study_directories from the response.

        Sets:
            self.accepted_studies (list): List of study objects from the API.
            self.study_directories (list): List of directories with study id/name.
        """
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}{self.simlet_endpoint}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("STUDY : Data received:", data)
            self.accepted_studies=data
            self.study_directories=[{"id":f"{self._get_id_from_object(dir, 'simlet', 'id')}/","name": self._get_id_from_object(dir, 'simlet', 'name')} for dir in self.accepted_studies]
        else:
            print(f"Error: {response.text}")

    def _load_selected_simlet_tests_list_from_simva_api(self):
        """
        Load selected simlet tests list from the SimVA API.

        Retrieves tests for the currently selected study/simlet.

        Args:
            None (uses self.actual_study to get the simlet id)

        Returns:
            list or None: List of test objects, or None if simlet id is not available.
        """
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        actual_simlet_id=self._get_id_from_object(self.actual_study, 'simlet', 'id')
        print(f"actual_simlet_id: {actual_simlet_id}")
        if actual_simlet_id is None:
            return []
        url = f"{self.simva_api_url}{self.simlet_endpoint}/{actual_simlet_id}/{self.session_endpoint}"
        print(f"URL for tests: {url}")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Error: {response.text}")
            return None
    
    def _list_test_from_study(self, study):
        """
        List tests from a study object.

        Args:
            study (dict): A study object containing a 'tests' list.

        Returns:
            list: List of test objects loaded from the API.
        """
        tests=[]
        if study is not None:
            print(study)
            for testid in study.get("tests"):
                print("Test :"+ testid)
                test=self._load_selected_test_from_simva_api(testid)
                if test is not None:
                    tests.append(test)
        return tests

    def _load_selected_test_from_simva_api(self, testId):
        """
        Load a selected test from the SimVA API.

        Args:
            testId (str): The ID of the test to retrieve.

        Returns:
            dict or None: The test data if found, None otherwise.
        """
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        actual_simlet_id=self._get_id_from_object(self.actual_study, 'simlet', 'id')
        url = f"{self.simva_api_url}{self.simlet_endpoint}/{actual_simlet_id}/{self.session_endpoint}/{testId}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("TEST : Data received:", data)
            return data
        else:
            print(f"Error: {response.text}")
            return None

    def _load_selected_test_activities_from_simva_api(self, testId):
        """
        Load selected test activities from the SimVA API.

        Args:
            testId (str): The ID of the test whose activities to retrieve.

        Returns:
            dict or None: The activity data if found, None otherwise.
        """
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        actual_simlet_id=self._get_id_from_object(self.actual_study, 'simlet', 'id')
        if self.health_ok:
            url = f"{self.simva_api_url}{self.simlet_endpoint}/{actual_simlet_id}/{self.session_endpoint}/{testId}/activities"
        else:
            url = f"{self.simva_api_url}/activities"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("ACTIVITY : Data received:", data)
            return data
        else:
            print(f"Error: {response.text}")
            return None

    def _get_minio_url_from_simva_api(self, activityId):
        """
        Get a presigned URL from the SimVA API for an activity.

        Args:
            activityId (str): The ID of the activity.

        Returns:
            dict or None: The response containing a presigned URL, or None on error.
        """
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}{self.activity_endpoint}/{activityId}/presignedurl"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("PRESIGNED URL : Data received:", data)
            return data
        else:
            print(f"Error: {response.text}")
            return None

    def _get_lrs_statements(self, objectId, is_activity=True):
        """
        Get the xAPI statements of one activity or of a whole session.

        The statements are read from the LRS itself whenever the secrets file holds
        credentials for it: the query carries the IRI SimVA files the selection under
        and every page the LRS advertises through `more` is followed, so nothing is
        left behind. A deployment without those credentials falls back to the SimVA
        API route that proxies the same query.

        Each answer is a Multi-Statements LRS Result and only the first page of it:
        the rest is walked through the `more` cursor the response carries.

        The call is incremental: the previous upper bound is reused as the next lower
        bound, so repeated calls only fetch what arrived since the last successful one.
        The watermark advances only after every page has been read, so a failure part
        way through re-reads the whole window next time instead of skipping statements.

        Args:
            objectId (str): The ID of the object to query. An activity id when
                `is_activity` is True, a test/session id otherwise.
            is_activity (bool): True to query a single activity, False to query the
                whole session (test) the currently selected study owns.

        Returns:
            list or None: All statements read across every page, or None if any request
                in the chain failed.
        """
        auth=None
        if self.lrs_direct:
            iri=self._get_statement_iri(objectId, is_activity)
            if iri is None:
                print(
                    f"LRS : no statement IRI for {'activity' if is_activity else 'session'} {objectId}, "
                    "the study, test or simva.external_url is missing"
                )
                self.lrs_error = "the study or test of this selection is not known, so the LRS cannot be queried for it"
                return None
            url=self.lrs_statements_url
            page_base=self.lrs_origin
            headers={'Content-Type': 'application/json', 'X-Experience-API-Version': LRS_API_VERSION}
            auth=(self.lrs_username, self.lrs_password)
            # `related_activities` also matches the IRIs a statement repeats in its
            # context, which is where SimVA records the activity and the session, and
            # `ascending` keeps the pages in order, so the merge and the charts see
            # the statements in the order they happened.
            params={"activity": iri, "related_activities": "true", "ascending": "true"}
        else:
            headers = {'Content-Type': 'application/json'}
            if self.jwt:
                headers['Authorization'] = f'Bearer {self.jwt}'
            page_base=self.simva_api_url
            params={}
            if is_activity:
                url = f"{self.simva_api_url}{self.activity_endpoint}/{objectId}/lrs/statements"
            else:
                actual_simlet_id = self._get_id_from_object(self.actual_study, 'simlet', 'id')
                url = f"{self.simva_api_url}{self.simlet_endpoint}/{actual_simlet_id}/{self.session_endpoint}/{objectId}/lrs/statements"
        # Build the window without touching the stored watermark, so a failed request
        # leaves the previous window to be retried instead of being skipped.
        # Both bounds trail the current time by the configured lag, so each query
        # re-reads a short tail behind the last one. An LRS may index a statement just
        # after it lands, and a window closed at "now" would step over that statement
        # and never return it; the overlap brings it back on a later poll, where
        # deduplication by statement identity keeps the data set clean.
        previous_until = self.until_time
        lag=timedelta(seconds=self.lrs_lag_seconds)
        # The first read of a selection is not incremental, so it goes right up to the
        # current time: holding back the newest seconds there would leave a live
        # activity, whose whole history is younger than the lag, with no data at all.
        # Later reads trail the clock by the lag and reach back before the previous
        # upper bound, so a statement the LRS indexed late is returned again; the
        # statements seen twice are dropped by identity, so the overlap costs a
        # request and never a duplicate.
        now_text = format_lrs_instant(utcnow() - (lag if previous_until is not None else timedelta(0)))
        params["until"] = now_text
        if previous_until is not None:
            # If the stored watermark cannot be read back, fall back to a full read
            # rather than querying a window we cannot bound.
            previous = parse_lrs_instant(previous_until)
            if previous is None:
                print(f"LRS watermark {previous_until!r} is unreadable; reading the full history")
            else:
                # `since` rather than its xAPI 2.0 spelling `from`, which several LRS
                # deployments accept and then match nothing against, answering an empty
                # page as if the activity had produced no statement at all.
                params["since"] = format_lrs_instant(previous - lag)
        print(f"LRS request {url} params={params} (lag={self.lrs_lag_seconds}s)")
        try:
            response = requests.get(url, headers=headers, params=params, auth=auth, timeout=LRS_REQUEST_TIMEOUT)
        except Exception as e:
            print(f"LRS request failed for {url}: {e}")
            self.lrs_error = f"the LRS could not be reached ({e})"
            return None
        if response.status_code != 200:
            print(f"LRS request for {url} returned {response.status_code}: {response.text}")
            self.lrs_error = f"the LRS answered {response.status_code} for {url}"
            return None

        data=response.json()
        statements = extract_statements(data)
        pages = 1
        visited = {url}
        # The next page already carries the window, so it is requested verbatim
        # instead of re-applying the window on top of the LRS cursor.
        next_url = next_lrs_page_url(data, page_base)
        while next_url is not None:
            if next_url in visited:
                print(f"LRS advertises an already visited page ({next_url}); stopping to avoid a loop")
                break
            if pages >= LRS_MAX_PAGES:
                print(f"LRS pagination stopped after {LRS_MAX_PAGES} pages; remaining statements are not fetched")
                break
            visited.add(next_url)
            page = self._fetch_lrs_page(next_url, headers, auth)
            if page is None:
                self.lrs_error = f"page {pages + 1} of the LRS result could not be reached ({next_url})"
                return None
            if page.status_code != 200:
                print(f"LRS page {next_url} returned {page.status_code}: {page.text}")
                self.lrs_error = f"page {pages + 1} of the LRS result answered {page.status_code} ({next_url})"
                return None
            data = page.json()
            statements.extend(extract_statements(data))
            pages += 1
            next_url = next_lrs_page_url(data, page_base)

        # Only now is the whole window proven to be read, so commit the watermark.
        self.from_time = previous_until
        self.until_time = now_text
        self.lrs_error = None
        print(f"LRS DATA : {len(statements)} statement(s) over {pages} page(s)")
        return statements

    def _fetch_lrs_page(self, url, headers, auth=None):
        """
        Fetch one `more` page exactly as the LRS handed it over, authenticated the
        same way as the first request.

        The cursor already carries the whole query, so the URL is used verbatim: no
        parameter is added, removed or rewritten. The request repeats the credentials
        of the query that produced it, so a `more` page is authorised exactly like
        the first one whether it resolved on the LRS or back through the API.

        Args:
            url (str): The `more` value, resolved against its server but otherwise
                untouched.
            headers (dict): The headers of the originating request, version included.
            auth (tuple, optional): The credentials of the originating request, the
                LRS ones for a direct read and None through the API.

        Returns:
            The response, or None if the request failed, be it an unreachable host or
            an LRS that took longer than LRS_REQUEST_TIMEOUT to answer.
        """
        try:
            return requests.get(url, headers=headers, auth=auth, timeout=LRS_REQUEST_TIMEOUT)
        except Exception as e:
            print(f"LRS page request failed for {url}: {e}")
            return None

    def _list_activities_from_test(self, test):
        """
        List activities from a test object.

        Args:
            test (dict): A test object containing an 'activities' list.

        Returns:
            list: List of activity objects that have type 'gameplay' with trace_storage enabled.
        """
        activities=[]
        if test is not None:
            for activityId in test.get("activities"):
                print("Activity :"+ activityId)
                activity=self._load_selected_test_activities_from_simva_api(activityId)
                print(activity)
                if activity is not None:
                    if activity.get("type") == 'gameplay' and activity.get("extra_data").get("config").get("trace_storage"):
                        activities.append(activity)
        return activities
    
    def _isdir(self, path):
        """
        Check if a path represents a directory.

        Args:
            path (str): The path to check.

        Returns:
            bool: True if the path ends with the delimiter (indicating a directory), False otherwise.
        """
        return path.endswith(self.delimiter)

    def _getStudyIdTestIdAndUpdatedPathFromPath(self, path):
        """
        Extract study ID, test ID, and updated path from a full path.

        Splits the path relative to base_path into study ID, test ID, and remaining path.

        Args:
            path (str): The full path to parse.

        Returns:
            tuple: (studyId, testId, path) where studyId and testId are strings or None,
                   and path is the remaining path after removing study and test IDs.
        """
        added_path=path.replace(self.base_path, "").split("/")
        studyId=None
        testId=None
        if len(added_path) >= 1:
            studyId=added_path[0]
            path=path.replace(studyId + "/", "")
        if len(added_path) >= 2:
            testId=added_path[1]
            path=path.replace(testId + "/", "")
        return studyId, testId, path

    def get_file_content_from_url(self):
        """
        Get file content from the actual file URL.

        Sends an HTTP GET request to the stored actual_file_url and returns the
        content along with the current path.

        Returns:
            tuple: (current_path, content) where content is the file text or None on error.
        """
        if self.actual_file_url is not None:
            try:
                # Send an HTTP GET request to the provided URL
                response = requests.get(self.actual_file_url)
                
                # Raise an exception if the request was unsuccessful (HTTP code other than 200)
                response.raise_for_status()
                print("get_file_content_from_url :")
                print(self.actual_file_url)
                
                # Return the content of the file as text
                return self.current_path, response.text
            
            except requests.exceptions.RequestException as e:
                print(f"Error fetching file content: {e}")
                return self.current_path, None
        else: 
            return self.current_path, None
        
    def get_lrs_content(self):
        """
        Serialize the LRS statements of the current selection for analysis.

        Returns the statements as a JSON document, using the same string contract as
        get_file_content_from_url so both can feed load_from_string directly.

        Returns:
            str or None: The statements as a JSON string, or None when no LRS data
                has been fetched for the current selection.
        """
        if self.lrs_data is None:
            return None
        return json.dumps(extract_statements(self.lrs_data))

    def _get_session_traces_content(self):
        """
        Build the analysis content for a whole session from its activity trace files.

        Used as a fallback when the session level LRS endpoint is unavailable: walks
        every accepted activity, resolves its presigned MinIO URL and concatenates the
        retrieved statements.

        Returns:
            str or None: The concatenated statements as a JSON string, or None when no
                trace could be retrieved for any activity.
        """
        statements=[]
        for activity in self.accepted_activities or []:
            activity_id=self._get_id_from_object(activity, 'activity', 'id')
            if activity_id is None:
                continue
            result=self._get_minio_url_from_simva_api(activity_id)
            if result is None:
                continue
            url=result.get("url")
            if not url:
                continue
            try:
                response=requests.get(url)
                response.raise_for_status()
                data=response.json()
            except Exception as e:
                print(f"Error fetching traces for activity {activity_id}: {e}")
                continue
            statements.extend(extract_statements(data))
        if not statements:
            return None
        return json.dumps(statements)

    def get_analysis_content(self):
        """
        Get the content to analyse for the current selection.

        On a server that speaks the current SimVA API the LRS is the only source, and
        its statements are used as they are: no MinIO lookup is made, so a problem in
        the LRS is reported as such instead of being masked by a trace file from a
        store this deployment may not even use. Only a legacy server, recognised by a
        failed health check, falls back to the presigned trace file and then to the
        trace files of every activity in the session.

        Returns:
            tuple: (current_path, content) where content is a JSON string, or None
                when no content is available.
        """
        content = self.get_lrs_content()
        if content is not None:
            return self.current_path, content
        if not self.health_ok:
            if self.analysis_is_activity and self.actual_file_url is None:
                activity_id=self._get_id_from_object(self.actual_activity, 'activity', 'id')
                if activity_id is not None:
                    result=self._get_minio_url_from_simva_api(activity_id)
                    self.actual_file_url=result.get("url") if result is not None else None
            current_path, content = self.get_file_content_from_url()
            if content is not None:
                return current_path, content
            if not self.analysis_is_activity:
                content = self._get_session_traces_content()
                if content is not None:
                    return self.current_path, content
        return self.current_path, None

    def _update_files(self):
        """
        Update the browser's file and directory listing based on the current path.

        Navigates the directory structure based on the added_path relative to base_path.
        Updates self.files, self.dirs, self.actual_study, and self.actual_file_url accordingly.

        If added_path has more than 1 element, navigates into study directory.
        Otherwise resets to root level with study directories displayed.
        """
        self.files = []
        self.dirs = []
        self.added_path=self.current_path.replace(self.base_path, "").split("/")
        self.current_level=len(self.current_path.replace(self.base_path, "").split("/"))
        print("AddedPath : " + str(self.added_path))
        print("CurrentLevel : " + str(self.current_level))
        studyDirs=[{"id": f"{self._get_id_from_object(dir, 'simlet', 'id')}/","name": self._get_id_from_object(dir, 'simlet', 'name')} for dir in self.accepted_studies]
        if len(self.added_path) > 1:
            self._update_study()
        else:
            self.actual_study=None
            self.dirs=studyDirs
            self.files=[]
            self.actual_file_url=None

    def _reset_browser(self):
        """
        Reset the browser to the initial state.

        Resets the current path to base_path, clears all selected study/test/activity
        and file state, and clears accepted tests and activities lists.
        """
        self.current_path=self.base_path
        self.current_level=0
        
        self.actual_study=None
        self.actual_activity=None
        self.actual_test=None
        self.actual_selected_file=None
        self.actual_file_url=None
        self.lrs_data=None
        self.analysis_ready=False
        self.analysis_is_activity=None
        self.until_time=None
        self.from_time=None
        
        self.accepted_tests=[]
        self.accepted_activities=[]

    def _update_study(self):
        """
        Update the browser state for a study/simlet selection.

        Navigates to the study specified by added_path[0], loads its tests,
        and prepares test directories for browsing.

        Sets:
            self.actual_study: The selected study object.
            self.accepted_tests: List of test objects for the study.
            self.dirs: Test directories with id/name.
        """
        print(f"self.current_level: {self.current_level} - Study/Simlet")
        actual_study_id=self.added_path[0]
        print(f"actual_study_id: {actual_study_id}")
        print(f"self.accepted_studies: {self.accepted_studies}")
        actual_studies=[study for study in self.accepted_studies if f"{self._get_id_from_object(study, 'simlet', 'id')}" == f"{actual_study_id}"]
        if actual_studies is not None and len(actual_studies) > 0:
            self.actual_study=actual_studies[0]
            print(f"self.actual_study: {self.actual_study}")
            if self.health_ok:
                self.accepted_tests=self._load_selected_simlet_tests_list_from_simva_api()
            else:
                self.accepted_tests=self._list_test_from_study(self.actual_study)
            print(f"self.accepted_tests: {self.accepted_tests}")
            testDirs=[{"id":f"{self._get_id_from_object(dir, 'session', 'id')}/", "name": self._get_id_from_object(dir, 'session', 'name')} for dir in self.accepted_tests]
            print(f"testDirs: {testDirs}")
            print(f"self.added_path: {self.added_path}")
            self.dirs=testDirs
            self.files=[]
            if actual_study_id is not None:
                print(f"self.current_level: {self.current_level} - Study/Test")
                self._update_tests()
        else:
            self._reset_browser()

    def _update_tests(self):
        """
        Update the browser state for a test selection.

        Navigates to the test specified by added_path[1], loads its activities,
        and prepares activity directories for browsing.

        Sets:
            self.actual_test: The selected test object.
            self.accepted_activities: List of activity objects for the test.
            self.dirs: Activity directories with id/name.
        """
        actual_test_id=self.added_path[1]
        print(f"actual_test_id: {actual_test_id}")
        print(f"self.accepted_tests: {self.accepted_tests}")
        actual_tests=[test for test in self.accepted_tests if f"{self._get_id_from_object(test, 'session', 'id')}" == f"{actual_test_id}"]
        print(f"actual_tests: {actual_tests}")
        if actual_tests is not None and len(actual_tests) > 0:
            self.actual_test=actual_tests[0]
            print(f"self.actual_test: {self.actual_test}")
            if self.health_ok:
                self.accepted_activities=self._load_selected_test_activities_from_simva_api(actual_test_id)
            else:
                self.accepted_activities=self._list_activities_from_test(self.actual_test)
            print(f"self.accepted_activities: {self.accepted_activities}")
            activityDirs=[{"id":f"{self._get_id_from_object(dir, 'activity', 'id')}/","name": self._get_id_from_object(dir, 'activity', 'name')} for dir in self.accepted_activities]
            print(f"activityDirs: {activityDirs}")
            self.dirs=activityDirs
            self.dirs.append({"id":"Analysis","name":"Complete session"})
            self.files=[]
            if actual_test_id is not None:
                self._update_activities()  
        else:
            self.actual_test=None
            self.actual_activity=None
            print(f"self.current_level: {self.current_level} - No Activity selected")
            print(f"self.actual_test: {self.actual_test}")
            self.actual_file_url=None

    def _update_activities(self):
        """
        Update the browser state for an activity selection.

        Navigates to the activity specified by added_path[2]. If the activity ID is
        "Analysis", prepares the session level analysis. Otherwise, retrieves the
        presigned URL and file information for the activity.

        Whenever the selection is directly analysable, the corresponding LRS
        statements are fetched into self.lrs_data and the selection is flagged with
        self.analysis_ready so the caller can launch the analysis right away:
        is_activity=False for the session level "Analysis" entry, is_activity=True
        when a single activity is selected.

        Sets:
            self.actual_activity: The selected activity object.
            self.actual_file_url: Presigned URL for accessing activity traces.
            self.dirs: Directory listing (empty for activities).
            self.files: List of files available (traces.json or "Run analysis").
            self.lrs_data: LRS statements for the session or the activity, None otherwise.
            self.analysis_ready: True when the current selection can be analysed.
            self.analysis_is_activity: True for an activity, False for a session.
            self.analysis_object_id: The id the statements were queried with, reused by polling.
        """
        print(f"self.current_level: {self.current_level} - Activities")
        actual_activity_id=self.added_path[2]
        self.analysis_ready=False
        self.analysis_is_activity=None
        self.analysis_object_id=None
        self.lrs_data=None
        self.lrs_error=None
        # Every new selection is read from scratch: carrying the previous window over
        # would make the next object's own history invisible to the incremental query.
        self.until_time=None
        self.from_time=None
        if actual_activity_id == "Analysis":
            self.actual_activity=None
            self.actual_file_url=None
            self.dirs=[]
            self.files=[]
            payload=self._get_lrs_statements(objectId=self.added_path[1], is_activity=False)
            self.analysis_object_id=self.added_path[1]
            # Keep None on failure so get_analysis_content can still fall back to traces.
            self.lrs_data=None if payload is None else merge_statements([], payload)[0]
            self.analysis_ready=True
            self.analysis_is_activity=False
            return
        print(f"actual_activity_id: {actual_activity_id}")
        print(f"self.accepted_activities: {self.accepted_activities}")
        actual_activities=[activity for activity in self.accepted_activities if f"{self._get_id_from_object(activity, 'activity', 'id')}" == f"{actual_activity_id}"]
        if actual_activities is not None and len(actual_activities) > 0:
            self.actual_activity=actual_activities[0]
            print(f"actual_activity_id: {actual_activity_id}")
            print(f"self.actual_activity: {self.actual_activity}")
            if self.health_ok:
                self.dirs=[]
                self.files=[]
                payload=self._get_lrs_statements(objectId=actual_activity_id, is_activity=True)
                self.analysis_object_id=actual_activity_id
                self.lrs_data=None if payload is None else merge_statements([], payload)[0]
                self.analysis_ready=True
                self.analysis_is_activity=True
            else: 
                result=self._get_minio_url_from_simva_api(actual_activity_id)
                self.actual_file_url=result.get("url") if result is not None else None
                if self._isdir(path=self.current_path):
                    self.dirs=[]
                    self.files=["traces.json"] if self.actual_file_url is not None else []
                else:
                    self.dirs=[]
                    self.files=[]