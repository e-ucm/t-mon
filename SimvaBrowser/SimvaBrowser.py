import requests
import xml.etree.ElementTree as ET
import boto3
import boto3.session
from botocore.exceptions import ClientError
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
        self.simva_api_url = self.secret_file.get("simva").get("api_url")
        jwt_parser = JWT()
        self.jwt = self.auth.get('oidc_auth_token', {}).get("access_token")
        self.access_token=jwt_parser.decode(self.jwt, do_verify=False)
        self._load_selected_studies_from_simva_api()

        #MINIO
        self.accept = accept
        self.ca_file = ca_file
        self.storage_url = self.secret_file.get("minio").get("storage_url")
        self.bucket_name = self.secret_file.get("minio").get("bucket_name")
        self.access_key_id = self.secret_file.get("minio").get("access_key_id")
        self.secret_access_key = self.secret_file.get("minio").get("secret_access_key")
        self.traces_folder = self.secret_file.get("minio").get("output_folder")
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
        url = f"{self.simva_api_url}studies/{self.actual_study.get("_id")}/tests/{testId}"
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

    #MINIO
    def _s3_client(self):
        return boto3.client(
            's3',
            endpoint_url=self.storage_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            verify=self.ca_file
        )

    def _list_files(self, path):
        studyId,testId,path=self._getStudyIdTestIdAndUpdatedPathFromPath(path)
        print("updated path : "+path)
        try:
            s3_client = self._s3_client()
            folder = s3_client.list_objects_v2(Bucket=self.bucket_name,
                                            Prefix=path,
                                            Delimiter=self.delimiter)
            files = []
            contents = folder.get('Contents')
            print(f"Folder : {folder}")
            if contents:
                for o in contents:
                    files.append(o.get('Key')[len(path):])
            print("Files at {path} :")
            print(files)
            return files
        except ClientError as e:
            print(f"An error occurred: {e}")
            if e.response['Error']['Code'] == 'AccessDenied':
                print("Access denied.")
            return []

    def get_file_content(self, path):
        studyId,testId,path=self._getStudyIdTestIdAndUpdatedPathFromPath(path)
        try:
            s3_client = self._s3_client()
            file = s3_client.get_object(Bucket=self.bucket_name, Key=path)
            return path, file['Body'].read()
        except ClientError as e:
            print(f"An error occurred: {e}")
            if e.response['Error']['Code'] == 'AccessDenied':
                print("Access denied.")
            return path, []

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
                    else:
                        self.actual_activity=None
                else:
                    self.actual_test=None
            else:
                self.actual_study=None
        if self.current_level == 0:
            print(studyDirs)
            self.dirs=studyDirs
        elif self.current_level == 2:
            print(self.actual_study)
            print(testDirs)
            self.dirs=testDirs
        elif self.current_level == 3:
            print(self.actual_test)
            print(activityDirs)
            self.dirs=activityDirs
        else:
            self.dirs=[]
            self.files=self._list_files(self.current_path)

    def _reset_browser(self):
        self.current_path=self.base_path
        self.current_level=0
        
        self.actual_study=None
        self.actual_activity=None
        self.actual_test=None
        self.actual_selected_file=None

        self.accepted_tests=[]
        self.accepted_activities=[]

    def file_exists(self, path):
        """
        Check if a file exists in the S3 bucket at the given path.

        :param path: The path of the file in the S3 bucket.
        :return: True if the file exists, False otherwise.
        """
        studyId,testId,path=self._getStudyIdTestIdAndUpdatedPathFromPath(path)
        status=False
        error={"Code":"", "Message":"", "Key": ""}
        if studyId in [study.get("_id") for study in self.accepted_studies]:
            try:
                s3_client = self._s3_client()
                file = s3_client.get_object(Bucket=self.bucket_name, Key=path)
                file['Body'].read()
                status=True
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    error=e.response['Error']
                else:
                    print(f"An error occurred: {e}")
                    error=e.response['Error']
        else:
            self._reset_browser()
            self._update_files()
            error={"Code":"AccessDenied", "Message":"You cannot access data from this study."}
        return path, status, error