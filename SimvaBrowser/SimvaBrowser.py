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
        self.accepted_activities=[]
        self.accepted_studies=[]
        self.actual_activity=None
        self.actual_study=None
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
        else:
            print(f"Error: {response.text}")

    def _get_accepted_study_from_id(self, studyId):
        study=[study for study in self.accepted_studies if study.get("_id") == studyId]
        if len(study)>0:
            return study[0]
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

    def _list_activities_from_study(self, study):
        activities=[]
        if study is not None:
            print(study)
            for testid in study.get("tests"):
                print("Test :"+ testid)
                test=self._load_selected_test_from_simva_api(testid)
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
                    files.append(o.get('Key')[len(self.current_path):])
            return files
        except ClientError as e:
            print(f"An error occurred: {e}")
            if e.response['Error']['Code'] == 'AccessDenied':
                print("Access denied. Check your IAM policies and bucket policies.")
            return []

    def get_file_content(self, path):
        try:
            s3_client = self._s3_client()
            file = s3_client.get_object(Bucket=self.bucket_name, Key=path)
            return file['Body'].read()
        except ClientError as e:
            print(f"An error occurred: {e}")
            if e.response['Error']['Code'] == 'AccessDenied':
                print("Access denied. Check your IAM policies and bucket policies.")
            return []

    def _isdir(self, path):
        return path.endswith(self.delimiter)

    def _update_files(self):
        self.files = []
        self.dirs = []
        self.added_path=self.current_path.replace(self.base_path, "").split("/")
        self.current_level=len(self.current_path.replace(self.base_path, "").split("/"))
        print("AddedPath")
        print(self.added_path)
        studyDirs=[{"id":dir.get("_id") + "/","name": dir.get('name')} for dir in self.accepted_studies]
        if self._isdir(self.current_path):
            if self.current_level == 1:
                self.dirs=studyDirs
                self.actual_study=None
                self.accepted_activities=[]
            elif self.current_level >= 2:
                actual_study_id=self.added_path[0]
                self.actual_activity=None
                if actual_study_id not in [study.get("_id") for study in self.accepted_studies]:
                    self.current_path=self.base_path
                    self.current_level=0
                    self.actual_study=None
                    self.actual_activity=None
                    self.actual_selected_file=None
                    self.dirs=studyDirs
                else:
                    self.actual_study=self._get_accepted_study_from_id(actual_study_id)
                if self.current_level == 2:
                    self.accepted_activities=self._list_activities_from_study(self.actual_study)
                    activityDirs=[{"id":dir.get("_id") + "/","name": dir.get('name')} for dir in self.accepted_activities]
                    self.dirs=activityDirs
                else:
                    actual_activity_id=self.added_path[1]
                    self.actual_activity=self._load_selected_activity_from_simva_api(actual_activity_id)
                    self.files=self._list_files(self.current_path)
            self.files=self._list_files(self.current_path)

    def file_exists(self, path):
        """
        Check if a file exists in the S3 bucket at the given path.

        :param path: The path of the file in the S3 bucket.
        :return: True if the file exists, False otherwise.
        """
        try:
            s3_client = self._s3_client()
            file = s3_client.get_object(Bucket=self.bucket_name, Key=path)
            file['Body'].read()
            return True, ""
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False, e.response['Error']
            else:
                print(f"An error occurred: {e}")
                return False, e.response['Error']