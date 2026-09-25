import requests
from jwt import JWT
import os
import json

class SimvaBrowser:
    def __init__(self, auth, accept='.json', ca_file=None, delimiter='/', client_secret_file="client_secrets.json"):
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
        self.health_ok=False
        self.simlet_endpoint=None
        self.session_endpoint=None
        self.activity_endpoint=None
        self.simva_api_url = self.secret_file.get("simva").get("api_url")
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
        with open(file_path, 'r') as file:
            secret_data = json.load(file)
        return secret_data

    def _check_health_endpoint(self):
        health_url = f"{self.simva_api_url}health"
        headers = {'Content-Type': 'application/json'}
        print("HEALTH : Checking health endpoint...")
        try:
            response = requests.get(health_url, headers=headers, timeout=5)
            self.health_ok = (response.status_code == 200)
            self.simlet_endpoint="simlets"
            self.session_endpoint="sessions"
            self.activity_endpoint="activities"
        except Exception:
            self.health_ok = False
            self.simlet_endpoint="studies"
            self.session_endpoint="tests"
            self.activity_endpoint="activities"

    def _get_id_from_object(self, object, type, name):
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

    def _list_activities_from_test(self, test):
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
        return path.endswith(self.delimiter)

    def _getStudyIdTestIdAndUpdatedPathFromPath(self,path):
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
        
    def _update_files(self):
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
        self.current_path=self.base_path
        self.current_level=0
        
        self.actual_study=None
        self.actual_activity=None
        self.actual_test=None
        self.actual_selected_file=None
        self.actual_file_url=None

        self.accepted_tests=[]
        self.accepted_activities=[]

    def _update_study(self):
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
        print(f"self.current_level: {self.current_level} - Activities")
        actual_activity_id=self.added_path[2]
        if actual_activity_id == "Analysis":
            self.actual_activity=None
            self.actual_file_url=None
            self.dirs=[]
            self.files=["Run analysis"]
        print(f"actual_activity_id: {actual_activity_id}")
        print(f"self.accepted_activities: {self.accepted_activities}")
        actual_activities=[activity for activity in self.accepted_activities if f"{self._get_id_from_object(activity, 'activity', 'id')}" == f"{actual_activity_id}"]
        if actual_activities is not None and len(actual_activities) > 0:
            self.actual_activity=actual_activities[0]
            print(f"actual_activity_id: {actual_activity_id}")
            print(f"self.actual_activity: {self.actual_activity}")
            result=self._get_minio_url_from_simva_api(actual_activity_id)
            self.actual_file_url=result.get("url") if result is not None else None
            if self._isdir(path=self.current_path):
                self.dirs=[]
                self.files=["traces.json"] if self.actual_file_url is not None else []
            else:
                self.dirs=[]
                self.files=[]