from datetime import datetime
import json
import pandas as pd
import sys
import base64
from dataclasses import dataclass
import traceback

@dataclass
class Progress:
    """Fools load_from_string, keeps track of progress."""
    value: float

#
# fileBrowserAndUploadButtonToLoadProcessStatements.ipynb
#

def is_json_and_not_list(str):
  try:
    return not isinstance(json.loads(str), list)
  except Exception as e:
    return False

def log(target, o_str):
    if type(target) is None:
        pass
    elif type(target) is list:
        target.append(o_str)
    else:
        with target.output:
            print(o_str)

#
# Loads either JSON-statement-per-line or JSON-array-of-statements from a str
# Updates progress in progress by calling progress.value from 0.0 to 1.0 (=finished)
# err_output & info_output can be either
#    None (= no output), 
#    a list (= ouput strings get appended), or
#    an object o where with o.output: print() is valid
#
# Callback to update progress periodically
def load_from_string(str, xapiData, info_output, err_output):
    progress = Progress(0)
    total=0
    count=0
    try:
        start_time = datetime.now()
        if is_json_and_not_list(str.partition('\n')[0]):
            total=len(str.splitlines())
            log(info_output, f"... 1st line is valid JSON; interpreting as one-statement-per-line ({total} statement(s))")
            # 1st line is well-formed json, and not json list of statements; assume 1-statement-per-line
            statements=str.splitlines()
            for statement in statements:
                s=json.loads(statement)
                progress.value=count/total
                count+=1
                xapiData.append(s)
        else:
            log(info_output, "... interpreting as statement-array")
            # attempt to process all of it as a single JSON document
            statements = json.loads(str)
            total = len(statements)
            log(info_output, f"... parsed correctly as json array, total statements = {total}")
            for s in statements:
                progress.value=count/total
                count+=1
                xapiData.append(s)
    except Exception as e:
        log(err_output, 
            f"ERROR loading at line/statement {count}/{total}: {e}\n"
            f"Full error:\n~~~\n{''.join(traceback.format_exception(e))}\n~~~\n"
            f"File must contain EITHER 1 statement (in JSON) per line, or be a well-formed JSON of statements. Please select another file.")
        return e
    progress.value=1.0
    log(info_output, f"... processed {count}/{total} statement(s) in {datetime.now() - start_time}. Displaying visualizations ...")

def load_players_info_from_file(file, xapiData, out, err):
    log(out, f"{file}")
    with open(file, encoding="utf-8") as f:
        str = f.read()
        load_from_string(str, xapiData, out, err)
        print(f"Info log ({len(out)} lines):\n{'\n'.join(out)}")
        if len(err) > 0:
            print(f"ERRORS FOUND ({len(err)} lines):\n{'\n'.join(err)}")
            sys.exit(-1)

def load_players_info_from_uploaded_content(filecontent, filename, xapiData, out, err):
    log(out, f"{filename}")
    content_type, content_string = filecontent.split(',')
    decoded = base64.b64decode(content_string).decode('utf-8')
    load_from_string(decoded, xapiData, out, err)

def load_players_info_from_content(filecontent, filename, xapiData, out, err):
    log(out, f"{filename}")
    decoded = filecontent.decode('utf-8')
    load_from_string(decoded, xapiData, out, err)