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
    if str is None or not str.strip():
        log(err_output,
            "ERROR: no content to load. The selected source returned no data.")
        return ValueError("no content to load")
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
                processxapisgdata(s, xapiData)
        else:
            log(info_output, "... interpreting as statement-array")
            # attempt to process all of it as a single JSON document
            statements = json.loads(str)
            total = len(statements)
            log(info_output, f"... parsed correctly as json array, total statements = {total}")
            for s in statements:
                progress.value=count/total
                count+=1
                processxapisgdata(s, xapiData)
    except Exception as e:
        log(err_output, 
            f"ERROR loading at line/statement {count}/{total}: {e}\n"
            f"Full error:\n~~~\n{traceback.format_exc()}\n~~~\n"
            f"File must contain EITHER 1 statement (in JSON) per line, or be a well-formed JSON of statements. Please select another file.")
        return e
    progress.value=1.0
    log(info_output, f"... processed {count}/{total} statement(s) in {datetime.now() - start_time}. Displaying visualizations ...")

def load_players_info_from_file(file, xapiData, out, err):
    log(out, f"{file}")
    with open(file, encoding="utf-8") as f:
        str = f.read()
        load_from_string(str, xapiData, out, err)
        print(f"Info log ({len(out)} lines):\n" + "\n".join(out))
        if len(err) > 0:
            print(f"ERRORS FOUND ({len(err)} lines):\n" + "\n".join(err))
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

def processxapisgdata(statement, xapiData):
    # Extract the `id` from the first category object
    if "context" in statement and "contextActivities" in statement["context"] and "category" in statement["context"]["contextActivities"] and len(statement["context"]["contextActivities"]["category"]) > 0:
        statement["context"]["contextActivities"]["category"] = statement["context"]["contextActivities"]["category"][0]["id"]
    resolve_actor_name(statement)
    xapiData.append(statement)


# xAPI identifies an actor either by `actor.name` (xAPI 1.0.2) or by
# `actor.account.name` (xAPI 2.0, where the identity lives in an Account object).
ACTOR_NAME_COLUMN = "actor.name"
ACTOR_ACCOUNT_NAME_COLUMN = "actor.account.name"


def resolve_actor_name(statement):
    """
    Give an xAPI statement an `actor.name` whatever actor shape it uses.

    Copies `actor.account.name` up to `actor.name` when only the xAPI 2.0 Account
    form is present, so both statement versions normalize to the same columns. An
    existing `actor.name` always wins, since it is the more specific value.
    """
    actor = statement.get("actor")
    if not isinstance(actor, dict):
        return statement
    if actor.get("name"):
        return statement
    account = actor.get("account")
    if isinstance(account, dict) and account.get("name"):
        actor["name"] = account["name"]
    return statement


def resolve_actor_name_column(df):
    """
    Guarantee an `actor.name` column on a normalized statements DataFrame.

    pd.json_normalize splits the two actor shapes into separate columns, so a data
    set mixing xAPI 1.0.2 and 2.0 statements ends up with NaNs in both. This coalesces
    them into the single `actor.name` column the visualisations and selectors use.

    Returns the DataFrame unchanged when neither column exists, so unrelated errors
    are not masked.
    """
    if ACTOR_ACCOUNT_NAME_COLUMN not in df.columns:
        return df
    if ACTOR_NAME_COLUMN not in df.columns:
        df[ACTOR_NAME_COLUMN] = df[ACTOR_ACCOUNT_NAME_COLUMN]
    else:
        df[ACTOR_NAME_COLUMN] = df[ACTOR_NAME_COLUMN].where(
            df[ACTOR_NAME_COLUMN].notna(), df[ACTOR_ACCOUNT_NAME_COLUMN]
        )
    return df


def _sub_columns_of(items):
    """Collect the union of leaf column names produced by normalizing `items`."""
    columns = []
    for item in items:
        for column in pd.json_normalize([item]).columns:
            if column not in columns:
                columns.append(column)
    return columns


def _join_sub_values(item, sub_column):
    """
    Render one normalized item's value for `sub_column` as a display string.

    Returns None when the item has no such field, which happens when the array mixes
    objects of different shapes: the sub-columns are the union across all entries, so
    an individual entry may lack some of them.
    """
    normalized = pd.json_normalize([item])
    if sub_column not in normalized.columns:
        return None
    value = normalized[sub_column]
    if value.empty or pd.isna(value.iloc[0]):
        return None
    return str(value.iloc[0])


def flatten_for_display(df, max_items=25):
    """
    Turn nested statement cells into sub-columns a Dash DataTable can render.

    pd.json_normalize leaves nested xAPI values as Python objects, most notably
    `context.contextActivities.parent`, which the spec defines as an array. Dash's
    DataTable only accepts string, number or boolean cells, so those objects are
    rejected at render time. Lists of objects become real sub-columns
    (`...parent.id`, `...parent.definition.name.en-US`, ...) whose values are joined
    with ", " when an array holds several entries, and single objects expand the same
    way.

    The row count is deliberately preserved: the DataTable shares its DataFrame with
    the charts, and exploding the arrays would duplicate statements and corrupt every
    count, so only the display copy is flattened.

    Args:
        df: The normalized statements DataFrame.
        max_items (int): Cap on array entries read per cell, bounding the work and
            the width of a single cell when a statement carries very long arrays.

    Returns:
        pandas.DataFrame: A new DataFrame with scalar cells only.
    """
    out = df.copy()
    for column in list(df.columns):
        series = df[column]
        present = series.dropna()
        if present.empty:
            continue
        sample = present.iloc[0]

        if isinstance(sample, dict):
            objects = [value for value in present if isinstance(value, dict)]
            if not objects:
                continue
            for sub_column in _sub_columns_of(objects):
                out[f"{column}.{sub_column}"] = [
                    _join_sub_values(value, sub_column) if isinstance(value, dict) else None
                    for value in series
                ]
            out = out.drop(columns=[column])

        elif isinstance(sample, list):
            objects = [
                item
                for value in present if isinstance(value, list)
                for item in value[:max_items] if isinstance(item, dict)
            ]
            if objects:
                for sub_column in _sub_columns_of(objects):
                    out[f"{column}.{sub_column}"] = [
                        ", ".join(filter(None, (
                            _join_sub_values(item, sub_column) for item in value[:max_items]
                        ))) or None
                        if isinstance(value, list) else None
                        for value in series
                    ]
            else:
                out[column] = [
                    ", ".join(str(item) for item in value) if isinstance(value, list) and value else None
                    for value in series
                ]
            out = out.drop(columns=[column])

    return out