import datetime
import json
# only for demo
import sys
import os
import io
import base64
from dataclasses import dataclass
import traceback
import ProcessxAPISGStatement
from dash import html
#
# 
#
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

#
# Loads either JSON-statement-per-line or JSON-array-of-statements from a str
# Updates progress in progress by calling progress.value from 0.0 to 1.0 (=finished)
# err_output & info_output can be either
#    None (= no output), 
#    a list (= ouput strings get appended), or
#    an object o where with o.output: print() is valid
#
def load_from_string(str, progress, info_output, err_output, players_info, timeformats):
    def log(target, o_str):
        if type(target) is None:
            pass
        elif type(target) is list:
            target.append(o_str)
        else:
            with target.output:
                print(o_str)
    total=0
    count=0
    try:
        start_time = datetime.datetime.now()
        if is_json_and_not_list(str.partition('\n')[0]):
            total=len(str.splitlines())
            log(info_output, f"... 1st line is valid JSON; interpreting as one-statement-per-line ({total} statement(s))")
            # 1st line is well-formed json, and not json list of statements; assume 1-statement-per-line
            for s in str.splitlines():
                progress.value=count/total
                count+=1
                ProcessxAPISGStatement.process_xapisg_statement(json.loads(s), players_info, timeformats)
        else:
            log(info_output, "... interpreting as statement-array")
            # attempt to process all of it as a single JSON document
            statements = json.loads(str)
            total = len(statements)
            log(info_output, f"... parsed correctly as json array, total statements = {total}")
            for s in statements:
                progress.value=count/total
                count+=1
                ProcessxAPISGStatement.process_xapisg_statement(s, players_info, timeformats)
    except Exception as e:
        log(err_output, 
            f"ERROR loading at line/statement {count}/{total}: {e}\n"
            f"Full error:\n~~~\n{''.join(traceback.format_exception(e))}\n~~~\n"
            f"File must contain EITHER 1 statement (in JSON) per line, or be a well-formed JSON of statements. Please select another file.")
        return e
    progress.value=1.0
    log(info_output, f"... processed {count}/{total} statement(s) in {datetime.datetime.now() - start_time}. Displaying visualizations ...")
    return players_info

timeformats=['%Y-%m-%dT%H:%M:%SZ','%Y-%m-%dT%H:%M:%S.%fZ']
players_info = {}

def load_players_info_from_file(file):
    with open(file, encoding="utf-8") as f:
        str = f.read()
        progress = Progress(0)
        out, err = [], []
        load_from_string(str, progress, out, err, players_info, timeformats)
        print(f"Info log ({len(out)} lines):\n", '\n'.join(out))
        if len(err) > 0:
            print(f"ERRORS FOUND ({len(err)} lines):\n", '\n'.join(err))
            sys.exit(-1)
    return players_info

def load_players_info_from_content(filecontent, filename, date):
    content_type, content_string = filecontent.split(',')
    decoded = base64.b64decode(content_string)
    progress = Progress(0)
    out, err = [], []
    try:
        if 'json' in filename:
            load_from_string(decoded, progress, out, err, players_info, timeformats)
    except Exception as e:
        print(e)
        return html.Div(
            html.Div([
                'There was an error processing this file.'
            ]),
            html.Div(out),
            html.Div(err),
        ])
    return html.Div([
        html.H5(filename),
        html.H6(datetime.datetime.fromtimestamp(date)),
        html.Div(out),
        html.Hr(),  # horizontal line
        # For debugging, display the raw contents provided by the web browser
        html.Div('Raw Content'),
        html.Pre(filecontent[0:200] + '...', style={
            'whiteSpace': 'pre-wrap',
            'wordBreak': 'break-all'
        })
    ])