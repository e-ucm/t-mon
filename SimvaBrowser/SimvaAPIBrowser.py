import requests
from jwt import JWT
import os
import json

class SimvaBrowser:
    def __init__(self, auth, client_secret_file="client_secrets.json"):
        basedir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
        self.secret_file=self._load_secret_file(os.path.join(basedir, client_secret_file))
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
        self._load_selected_activities_from_simva_api()

    def _load_secret_file(self, file_path):
        with open(file_path, 'r') as file:
            secret_data = json.load(file)
        return secret_data

    def _load_selected_studies_from_simva_api(self):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}studies"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            username = self.access_token.get('preferred_username')
            user_data = [item for item in data if username in item.get("owners",[])]
            # Print the result
            print("STUDY : Data received:", data)
            print("preferred_username:", username)
            print("user_data : ", user_data)
            self.accepted_studies=user_data
        else:
            print(f"Error: {response.text}")

    def _load_selected_activities_from_simva_api(self):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}activities"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            username = self.access_token.get('preferred_username')
            user_data = [item for item in data if username in item.get("owners",[])]
            gameplay_data = [item for item in user_data if item.get("type") == 'gameplay']
            filtered = [item for item in gameplay_data if item.get("extra_data").get("config").get("trace_storage")]
            # Print the result
            print("ACTIVITIES : Data received:", data)
            print("preferred_username:", username)
            print("user_data : ", user_data)
            print("gameplay_data : ", gameplay_data)
            print("filtered : ",filtered)
            self.accepted_activities=filtered
        else:
            print(f"Error: {response.text}")
    
    def _load_selected_test_from_simva_api(self, testId):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}tests/{testId}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("TEST : Data received:", data)
            return data
        else:
            print(f"Error: {response.text}")


    def _load_selected_activity_from_simva_api(self, activityId):
        headers = {'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = f'Bearer {self.jwt}'
        url = f"{self.simva_api_url}activities:{activityId}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Print the result
            print("ACTIVITY : Data received:", data)
            return data
        else:
            print(f"Error: {response.text}")
    
    
#folders=[{"id":dir.get("_id") + "/","name": dir.get('name')} for dir in self.accepted_activities if dir.get("_id") + "/" in folders]
#if self.current_path == self.base_path:
#    self.actual_study=None
#    self.actual_activity=None
#    self.actual_selected_file=None
#else:
#    added_path=self.current_path.replace(self.base_path, "").split("/")
#    if len(added_path)>=1 and added_path[0] not in [activity.get("_id") for activity in self.accepted_activities]:
#        self.current_path=self.base_path
#        self.actual_study=None
#        self.actual_activity=None
#        self.actual_selected_file=None
#    else:
#        actual_activity_id=added_path[0] if len(added_path)>=1 else None
#        actual_activity_name = [item.get("name") for item in self.accepted_activities if item.get("_id") == actual_activity_id]
#        self.actual_activity=f"{actual_activity_name[0]} - {actual_activity_id}" if len(actual_activity_name)>0 else None
#        actual_study_id=added_path[1] if len(added_path)>=2 else None
#        actual_study_name = [item.get("name") for item in self.accepted_studies if item.get("_id") == actual_study_id]
#        self.actual_study=f"{actual_study_name[0]} - {actual_study_id}" if len(actual_study_name)>0 else None
#        self.actual_selected_file=added_path[1] if len(added_path)==2 else None
#        print("Added Path :")
#        print(added_path)
        