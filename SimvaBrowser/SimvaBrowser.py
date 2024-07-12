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
        self.simva_api_url = self.secret_file.get("simva").get("api_url")
        jwt_parser = JWT()
        self.jwt = self.auth.get('oidc_auth_token', {}).get("access_token")
        self.access_token=jwt_parser.decode(self.jwt, do_verify=False)
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

    #SIMVA API Logged
    def _load_selected_studies_from_simva_api(self):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}studies"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("STUDY : Data received:", data)
            self.accepted_studies=data
            self.study_directories=[{"id":dir.get("_id") + "/","name": dir.get('name')} for dir in self.accepted_studies]
        else:
            print(f"Error: {response.text}")

    def _get_accepted_study_from_id(self, studyId):
        study=[study for study in self.accepted_studies if study.get("_id") == studyId]
        if len(study)>0:
            return study[0]
        return None
    
    def _get_accepted_test_from_id(self, testId):
        test=[test for test in self.accepted_tests if test.get("_id") == testId]
        if len(test)>0:
            return test[0]
        return None

    def _get_accepted_activity_from_id(self, activityId):
        activity=[activity for activity in self.accepted_activities if activity.get("_id") == activityId]
        if len(activity)>0:
            return activity[0]
        return None
    
    def _load_selected_test_from_simva_api(self, testId):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}studies/{self.actual_study.get('_id')}/tests/{testId}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("TEST : Data received:", data)
            return data
        else:
            print(f"Error: {response.text}")
            return None

    def _load_selected_activity_from_simva_api(self, activityId):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}activities/{activityId}"
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
        url = f"{self.simva_api_url}activities/{activityId}/presignedurl"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("PRESIGNED URL : Data received:", data)
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

    def _list_activities_from_test(self, test):
        activities=[]
        if test is not None:
            for activityId in test.get("activities"):
                print("Activity :"+ activityId)
                activity=self._load_selected_activity_from_simva_api(activityId)
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

    def _update_files(self):
        self.files = []
        self.dirs = []
        self.added_path=self.current_path.replace(self.base_path, "").split("/")
        self.current_level=len(self.current_path.replace(self.base_path, "").split("/"))
        print("AddedPath")
        print(self.added_path)
        studyDirs=[{"id":dir.get("_id") + "/","name": dir.get('name')} for dir in self.accepted_studies]
        if self.current_level >= 1:
            actual_study_id=self.added_path[0]
            if actual_study_id not in [study.get("_id") for study in self.accepted_studies]:
                self._reset_browser()
            if self.current_level >= 2:
                self.actual_study=self._get_accepted_study_from_id(actual_study_id)
                self.accepted_tests=self._list_test_from_study(self.actual_study)
                print(self.accepted_tests)
                testDirs=[{"id":dir.get("_id") + "/","name": dir.get('name')} for dir in self.accepted_tests]
                if self.current_level >=3:
                    actual_test_id=self.added_path[1]
                    self.actual_test=self._get_accepted_test_from_id(actual_test_id)
                    self.accepted_activities=self._list_activities_from_test(self.actual_test)
                    activityDirs=[{"id":dir.get("_id") + "/","name": dir.get('name')} for dir in self.accepted_activities]
                    self.dirs=activityDirs
                    if self.current_level >=4:
                        actual_activity_id=self.added_path[2]
                        self.actual_activity=self._load_selected_activity_from_simva_api(actual_activity_id)
                        result=self._get_minio_url_from_simva_api(actual_activity_id)
                        self.actual_file_url=result.get("url") if result is not None else None
                    else:
                        self.actual_activity=None
                else:
                    self.actual_test=None
            else:
                self.actual_study=None
        if self.current_level == 0:
            print(studyDirs)
            self.dirs=studyDirs
            self.files=[]
            self.actual_file_url=None
        elif self.current_level == 2:
            print(self.actual_study)
            print(testDirs)
            self.dirs=testDirs
            self.files=[]
            self.actual_file_url=None
        elif self.current_level == 3:
            print(self.actual_test)
            print(activityDirs)
            self.dirs=activityDirs
            self.files=[]
            self.actual_file_url=None
        else:
            if self._isdir(path=self.current_path):
                self.dirs=[]
                self.files=["traces.json"] if self.actual_file_url is not None else []
            else:
                self.dirs=[]
                self.files=[]

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