import requests
import xml.etree.ElementTree as ET
import boto3
import boto3.session
from botocore.exceptions import ClientError
from jwt import JWT
import os
import json

class MinioBrowser:
    def __init__(self, auth, accept='.json', ca_file=None, delimiter='/', client_secret_file="client_secrets.json"):
        basedir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
        self.secret_file=self._load_secret_file(os.path.join(basedir, client_secret_file))
        self.auth=auth
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

        jwt_parser = JWT()
        self.jwt = self.auth.get('oidc_auth_token', {}).get("access_token")
        self.access_token=jwt_parser.decode(self.jwt, do_verify=False)
        self._update_files()

    def _load_secret_file(self, file_path):
        with open(file_path, 'r') as file:
            secret_data = json.load(file)
        return secret_data

    def _storage_login(self):
        data = {
            'Action': 'AssumeRoleWithWebIdentity',
            'Version': '2011-06-15',
            'DurationSeconds': 3600,
            'WebIdentityToken': self.auth.get('oidc_auth_token', {}).get("access_token")
        }
        print(f"Data : {data}")
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
            folders=[{"id":dir_id,"name": dir_id} for dir_id in folders]
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
        self.current_level=len(self.current_path.replace(self.base_path, "").split("/"))
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