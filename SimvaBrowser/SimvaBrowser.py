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
        basedir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
        self.secret_file=self._load_secret_file(os.path.join(basedir, client_secret_file))
        self.auth = auth
        self.accept = accept
        self.ca_file = ca_file
        self.accepted_activities=[]
        self.storage_url = self.secret_file.get("minio").get("storage_url")
        self.bucket_name = self.secret_file.get("minio").get("bucket_name")
        self.traces_folder = self.secret_file.get("minio").get("users_folder")
        self.simva_api_url = self.secret_file.get("simva").get("api_url")
        self.delimiter = delimiter
        jwt_parser = JWT()
        self.access_token = jwt_parser.decode(self.auth.get('oidc_auth_token', {}).get("access_token"), do_verify=False)
        
        self._storage_login()
        
        self.base_path = self.traces_folder + self.delimiter + self.access_token['preferred_username'] + self.delimiter
        self.current_path = self.base_path
        self._login_to_simva_api()
        self._load_selected_activities_from_simva_api()
        self._update_files()

    def _load_secret_file(self, file_path):
        with open(file_path, 'r') as file:
            secret_data = json.load(file)
        return secret_data

    def _login_to_simva_api(self):
        admin_username = self.secret_file.get("simva").get("admin_username").lower()
        admin_password = self.secret_file.get("simva").get("admin_password")
        # Define the payload
        payload = {
            "username": f"{admin_username}",
            "password": f"{admin_password}",
        }

        # Make POST request to API and get token
        response = requests.post(f"{self.simva_api_url}/users/login", headers={"Content-Type": "application/json"}, data=json.dumps(payload))

        # Check if the request was successful
        if response.status_code == 200:
            response_data = response.json()
            token = response_data.get("token")
            if token:
                self.jwt = f"{token}"
            else:
                print("Token not found in the response.")
        else:
            print(f"Failed to get token, status code: {response.status_code}")
            print(response.text)

    def _load_selected_activities_from_simva_api(self):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}/activities"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            username = self.access_token.get('preferred_username')
            user_data = [item for item in data if username in item.get("owners",[])]
            gameplay_data = [item for item in user_data if item.get("type") == 'gameplay']
            filtered_ids = [item['id'] + '/' for item in gameplay_data if item.get("extra_data").get("config").get("trace_storage")]
            # Print the result
            print("Data received:", data)
            print("preferred_username:", username)
            print("user_data : ", user_data)
            print("gameplay_data : ", gameplay_data)
            print("filtered_ids : ",filtered_ids)
            self.accepted_activities=filtered_ids
        else:
            print(f"Error: {response.text}")
    
    def _storage_login(self):
        data = {
            'Action': 'AssumeRoleWithWebIdentity',
            'Version': '2011-06-15',
            'DurationSeconds': 3600,
            'WebIdentityToken': self.auth.get('oidc_auth_token', {}).get("access_token")
        }
        response = requests.post(self.storage_url, data=data, verify=self.ca_file)
        print(f"Response : {response.text}")

        if response.status_code != 200:
            print('Problems getting temporary credentials')
            print(response.text)
            return
        
        if 'application/xml' not in response.headers['Content-Type']:
            print('Expected XML response, got:', response.headers['Content-Type'])
            print(response.text)
            return
        
        try:
            ns = {'sts': 'https://sts.amazonaws.com/doc/2011-06-15/'}
            root = ET.fromstring(response.text)
            credentials = root.find('sts:AssumeRoleWithWebIdentityResult', ns).find('sts:Credentials', ns)
            self.access_key_id = credentials.find('sts:AccessKeyId', ns).text
            self.secret_access_key = credentials.find('sts:SecretAccessKey', ns).text
            self.session_token = credentials.find('sts:SessionToken', ns).text
        except ET.ParseError as e:
            print('Error parsing XML response:', e)
            print(response.text)

    def _s3_client(self):
        return boto3.client(
            's3',
            endpoint_url=self.storage_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            aws_session_token=self.session_token,
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
        
    def _list_folders(self, path):
        try:
            s3_client = self._s3_client()
            folder = s3_client.list_objects_v2(Bucket=self.bucket_name,
                                            Prefix=path,
                                            Delimiter=self.delimiter)
            folders = []
            contents = folder.get('CommonPrefixes')
            if contents:
                for o in contents:
                    folders.append(o.get('Prefix')[len(self.current_path):])
            if self.current_path == self.base_path:
                folders=[dir_id for dir_id in folders if dir_id in self.accepted_activities]
            return folders
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
        if self._isdir(self.current_path):
            self.dirs = self._list_folders(self.current_path)
            self.files = self._list_files(self.current_path)

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