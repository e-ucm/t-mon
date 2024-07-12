# imports from actually useful code
import numpy as np
import copy
import math
import datetime

#
# ProcessxAPISGStatement.ipynb
#
#***timestampTotimedate* function** to tranform the timestamp in datetime
#Inputs:
#* timestamp : the time in a string
#* timeformats : an array of timeformat witch match the timestamp with
#
#Output:
#* return t : dateTime
#* raise TimeFormatError : in case of the timestamp not in timeformat array
def timestampTotimedate(timestamp, timeformats):
    t=None
    for timeformat in timeformats:
        try:
           t = datetime.datetime.strptime(timestamp, timeformat)
        except ValueError:
            pass
    if t==None:
        str="TimeFormatError : This timestamp don't match with formats in "
        for format in timeformats:
            str+=format+" "
        raise TimeFormatError(timestamp, str)
    else:
        return t
    
class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class TimeFormatError(Error):
    """Exception raised for errors in timeformat.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

# template with default information for each player
template_player_info = {
    "game_started": False, "game_completed": False,
    "interactions":{}, # dict of interactions
    "game_progress_per_time": [], # list of pairs (game progress, timestamp)
    "completables_scores": {}, # dict completable : last score
    "completables_progress": {}, # list of pairs completable : last progress
    "completables_times": {}, # dict completable: (start, end)
    "alternatives": {}, # dict alternative: list of pairs (response, correct (T/F))
    "action_type_interaction":{}, # dict of action type interactions
    "accessible":{}, # dict of accessible
    "videos_seen": [], # list of videos seen (accessed) by player
    "videos_skipped": [], # list of videos skipped by player
    "selected_menus":{} # dict of menus and response selected
}

#***process_xapisg_statement* function** receives an xAPI-SG statement and updates the dictionary of players information
#
#
#Inputs:
#* data : xAPI-SG statement
#* players_info: dictionary with players info
#* timeformats: list of timeformats for timestamp
def process_xapisg_statement(data, players_info, timeformats):
    # available keys in statement
    keys = data.keys()

    ## extracting fields from xAPI-SG statement
    # actor field
    if "actor" in keys:
        if "name" in data["actor"].keys():
            actor_name = data["actor"]["name"]

            if actor_name not in players_info.keys():
                players_info[actor_name] = copy.deepcopy(template_player_info)

            player_info = players_info[actor_name]

    # verb field
    if "verb" in keys:
        if "id" in data["verb"].keys():
            verb_id = data["verb"]["id"]
            # process verb field
            verb_xapi = np.array(verb_id.split("/"))[-1]

    # object field
    if "object" in keys:
        if "id" in data["object"].keys():
            object_id = data["object"]["id"]
            # process object id field
            object_id_name = np.array(object_id.split("/"))[-1]
        if "definition" in data["object"].keys() and "type" in data["object"]["definition"].keys():
            object_type = data["object"]["definition"]["type"]
            # process object type field
            object_type_xapi = np.array(object_type.split("/"))[-1]
    action_type=None
    # result field
    if "result" in keys:
        if "extensions" in data["result"].keys():
            if "response" in data["result"].keys():
                result_response = data["result"]["response"]
            res = data["result"]["extensions"]
        else:
            res = data["result"]
        if "success" in res.keys():
            result_success = res["success"]
        if "response" in res.keys():
            result_response = res["response"]
        if "progress" in res.keys():
            result_progress = res["progress"]
        elif "https://w3id.org/xapi/seriousgames/extensions/progress" in res.keys():
            result_progress = res["https://w3id.org/xapi/seriousgames/extensions/progress"]
        if "score" in res.keys():
            if(isinstance(res["score"],dict)):
                result_score = res["score"]["raw"]
            else:
                result_score = res["score"]
        if "action_type" in res.keys():
            action_type=res["action_type"]

    # timestamp field
    if "timestamp" in keys:
        timestamp = data["timestamp"]
        try:
            t=timestampTotimedate(timestamp, timeformats)
        except TimeFormatError as e:
            print(e)
        
    ## update values
    try:
        # initialized traces
        if verb_xapi.lower()=="initialized":
            if object_type_xapi.lower()=="serious-game":
                player_info["game_started"] = True
                if timestamp: player_info["game_progress_per_time"].append([0,t])

            if timestamp: player_info["completables_times"][object_id_name] = (t, 0) # (start, end) times

        # completed traces
        elif verb_xapi.lower()=="completed":
            if object_type_xapi.lower()=="serious-game":
                player_info["game_completed"] = True
                if timestamp: player_info["game_progress_per_time"].append([1,t])

            if timestamp and object_id_name in player_info["completables_times"].keys():
                prev = player_info["completables_times"][object_id_name][0]
                player_info["completables_times"][object_id_name] = (prev, t) # update end time
            if object_id_name and timestamp and result_score:
                player_info["completables_scores"][object_id_name] = result_score
                
        # progressed traces
        elif verb_xapi.lower()=="progressed":
            if object_type_xapi.lower()=="serious-game" and timestamp and result_progress:
                player_info["game_progress_per_time"].append([result_progress,t])
                if result_progress==1:
                    player_info['game_completed'] = True
                    
            if verb_xapi.lower()=="progressed" and object_id_name and result_progress:
                if not object_id_name in player_info["completables_progress"].keys():
                    player_info["completables_progress"][object_id_name]=[]
                player_info["completables_progress"][object_id_name].append([result_progress,t])
                
        # interacted and used traces
        elif verb_xapi.lower()=="interacted" or verb_xapi.lower()=="used":
            if action_type!=None:
                if not object_type_xapi in player_info["action_type_interaction"].keys():
                    player_info["action_type_interaction"][object_type_xapi]={}

                if not object_id_name in player_info["action_type_interaction"][object_type_xapi].keys():
                    player_info["action_type_interaction"][object_type_xapi][object_id_name]={}
                    
                if not action_type in player_info["action_type_interaction"][object_type_xapi][object_id_name].keys():
                    player_info["action_type_interaction"][object_type_xapi][object_id_name][action_type]=[]
                    
                player_info["action_type_interaction"][object_type_xapi][object_id_name][action_type].append(t)
                
            else:
                if not object_type_xapi in player_info["interactions"].keys():
                    player_info["interactions"][object_type_xapi]={}
                    
                if not object_id_name in player_info["interactions"][object_type_xapi].keys():
                    player_info["interactions"][object_type_xapi][object_id_name]=[]
                    
                player_info["interactions"][object_type_xapi][object_id_name].append(t)
                
        # selected traces
        elif verb_xapi.lower()=="selected":
            if object_type_xapi.lower()=="alternative":
                if object_id_name and result_response and result_success is not None: # success = false is valid!
                    if object_id_name in player_info["alternatives"].keys():
                        player_info["alternatives"][object_id_name].append((result_response, result_success))
                    else:
                        player_info["alternatives"][object_id_name] = [(result_response, result_success)]
                        
            elif object_type_xapi.lower()=="menu":
                if result_response:
                    if not object_id_name in player_info["selected_menus"].keys():
                        player_info["selected_menus"][object_id_name]={}
                    if not result_response in player_info["selected_menus"][object_id_name].keys():
                        player_info["selected_menus"][object_id_name][result_response]=[]
                    if timestamp:
                        t=timestampTotimedate(timestamp, timeformats)
                        player_info["selected_menus"][object_id_name][result_response].append(t)
        # accessed traces
        elif verb_xapi.lower()=="accessed":
            if object_type_xapi.lower()=="cutscene" and object_id_name:
                player_info["videos_seen"].append(object_id_name)
            elif object_type_xapi.lower()=="accessible" and object_id_name:
                if not object_id_name in player_info["accessible"].keys():
                    player_info["accessible"][object_id_name]=[]
                t=timestampTotimedate(timestamp, timeformats)
                player_info["accessible"][object_id_name].append(t)
        # skipped traces
        elif verb_xapi.lower()=="skipped":
            if object_type_xapi.lower()=="cutscene" and object_id_name:
                player_info["videos_skipped"].append(object_id_name)
    except NameError:
        pass#%% md
