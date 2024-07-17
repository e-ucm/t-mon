import requests
import xml.etree.ElementTree as ET
import boto3
import boto3.session

from jwt import JWT

class SimvaBrowser:
    def __init__(self, auth, storage_url, accept='.json', ca_file=None, bucket_name='traces', delimiter='/'):
        self.auth = auth
        self.storage_url = storage_url
        self.accept = accept
        self.ca_file = ca_file
        self.bucket_name = bucket_name
        self.delimiter = delimiter
        jwt_parser = JWT()
        self.access_token = jwt_parser.decode(self.auth.get('oidc_auth_token', {}).get("access_token"), do_verify=False)
        
        self._storage_login()
        
        self.base_path = 'users' + self.delimiter + self.access_token['preferred_username'] + self.delimiter
        self.current_path = self.base_path
        
        self._update_files()

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
        
        if 'text/xml' not in response.headers['Content-Type']:
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
        return boto3.resource(
            's3',
            endpoint_url=self.storage_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            aws_session_token=self.session_token,
            region_name='us-east-1',
            config=Config(signature_version='s3v4'),
            verify=self.ca_file
        )

    def _list_files(self, path):
        s3_client = self._s3_client()
        folder = s3_client.list_objects_v2(Bucket=self.bucket_name,
                                           Prefix=path,
                                           Delimiter=self.delimiter)
        files = []
        contents = folder.get('Contents')
        if contents:
            for o in contents:
                files.append(o.get('Key')[len(self.current_path):])
        return files

    def _list_folders(self, path):
        s3_client = self._s3_client()
        folder = s3_client.list_objects_v2(Bucket=self.bucket_name,
                                           Prefix=path,
                                           Delimiter=self.delimiter)
        folders = []
        contents = folder.get('CommonPrefixes')
        if contents:
            for o in contents:
                folders.append(o.get('Prefix')[len(self.current_path):])
        return folders

    def get_file_content(self, path):
        s3_client = self._s3_client()
        file = s3_client.get_object(Bucket=self.bucket_name, Key=path)
        return file['Body'].read()

    def _isdir(self, path):
        return path.endswith(self.delimiter)

    def _update_files(self):
        self.files = []
        self.dirs = []
        if self._isdir(self.current_path):
            self.dirs = self._list_folders(self.current_path)
            self.files = self._list_files(self.current_path)