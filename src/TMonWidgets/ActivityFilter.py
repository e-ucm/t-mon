"""
Grouping of xAPI statements by the activity they belong to.

SimVA records the activity a statement belongs to twice in its context, both times as
an IRI ending in `/activities/<id>`: the full one, which nests the activity in its
session and study, and the standalone one under `parent`. Reading the id off either is
what lets the dashboard offer one button per activity of a session, and what lets it
leave an activity out of the charts without touching the data it holds.

Only statements carrying such a context are attributed. A statement without one cannot
be placed in an activity, so it is kept only while every activity is on, rather than
being shown in a view the user has just narrowed.
"""
import math

import pandas as pd

# Column names `pandas.json_normalize` gives the context activity arrays, which it keeps
# as lists of objects rather than flattening them. The four groups are all read, so the
# ids offered as buttons and the ids the mask understands always agree.
GROUPING_COLUMN = "context.contextActivities.grouping"
PARENT_COLUMN = "context.contextActivities.parent"
CATEGORY_COLUMN = "context.contextActivities.category"
OTHER_COLUMN = "context.contextActivities.other"
ACTIVITY_COLUMNS = (GROUPING_COLUMN, PARENT_COLUMN, CATEGORY_COLUMN, OTHER_COLUMN)

# Path segment an activity IRI is recognised by, and the position of the id after it.
ACTIVITIES_SEGMENT = "activities"
ACTIVITY_ID_POSITION = -2


def is_missing(value):
    """
    Tell an absent value from a value that happens to be a string.

    `pandas` puts NaN in a cell a statement left out, and `isinstance` sees it as a
    float, so a plain containment test would report every missing cell as containing
    an activity.

    Args:
        value: A cell of a statements DataFrame or a value taken from a statement.

    Returns:
        bool: True when there is nothing there to look at.
    """
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    return False


def activity_id_of_iri(iri):
    """
    Return the activity id an IRI names, or None when it names something else.

    Args:
        iri (str): An activity IRI, either the one nested in a session and study or
            the standalone one.

    Returns:
        str or None: The activity id, or None when the IRI does not end in
            `/activities/<id>`.
    """
    if not iri or not isinstance(iri, str):
        return None
    segments = [segment for segment in iri.split("/") if segment]
    if len(segments) < 2 or segments[ACTIVITY_ID_POSITION] != ACTIVITIES_SEGMENT:
        return None
    return segments[-1]


def activity_ids_of_context_activities(context_activities):
    """
    Return every activity id named by a `contextActivities` value.

    The spec allows the arrays to be absent, to hold a single object, or to hold
    several, and `pandas` leaves a missing array as NaN, so all four shapes are
    accepted here.

    Args:
        context_activities: The `contextActivities` value of a statement, or the
            `grouping`/`parent` cell of a normalized DataFrame.

    Returns:
        set: The activity ids found, empty when the value names none.
    """
    if is_missing(context_activities):
        return set()
    if isinstance(context_activities, dict):
        context_activities = [context_activities]
    if not isinstance(context_activities, (list, tuple)):
        return set()
    found = set()
    for activity in context_activities:
        if not isinstance(activity, dict):
            continue
        identifier = activity_id_of_iri(activity.get("id"))
        if identifier is not None:
            found.add(identifier)
    return found


def statement_activity_ids(statement):
    """
    Return the ids of the activities a statement belongs to.

    Every place a context activity may be named is read, so a statement is attributed
    even when the place SimVA usually uses is missing. The ones that are not an
    `/activities/` IRI, such as the xAPI-SG profile in `category`, carry no id and are
    ignored.

    Args:
        statement (dict): One xAPI statement.

    Returns:
        set: The activity ids, empty when the statement names none.
    """
    if not isinstance(statement, dict):
        return set()
    context = statement.get("context")
    if not isinstance(context, dict):
        return set()
    context_activities = context.get("contextActivities")
    if not isinstance(context_activities, dict):
        return set()
    found = set()
    for group in ("grouping", "parent", "category", "other"):
        found |= activity_ids_of_context_activities(context_activities.get(group))
    return found


def statements_activity_ids(statements):
    """
    Return the activity ids present in a list of statements, in the order they appear.

    Reading the statements themselves is what makes the button row follow the data:
    an activity only shows up once it has produced at least one statement, so an
    activity that is still waiting for its first one is not offered as a choice.

    Args:
        statements (list): The xAPI statements currently loaded.

    Returns:
        list: The distinct activity ids, first seen first.
    """
    known = []
    seen = set()
    for statement in statements or []:
        for identifier in statement_activity_ids(statement):
            if identifier not in seen:
                seen.add(identifier)
                known.append(identifier)
    return known


def filter_df_by_activities(df, hidden=None):
    """
    Leave out the rows of the activities that are deactivated.

    A row survives when any of its activities is on, so a statement shared between two
    activities stays as long as one of them is. A row that belongs to no activity
    survives only while every activity is on, since it cannot be placed in any of the
    ones being hidden.

    Args:
        df (pandas.DataFrame): The normalized statements.
        hidden (list, optional): The ids of the activities to leave out.

    Returns:
        tuple: (the rows to show, the ids of the activities the data names). Both are
            the input untouched when the data carries no activity at all, or when the
            hidden ids name nothing in it.
    """
    hidden = set(hidden or [])
    known = []
    for column in ACTIVITY_COLUMNS:
        if column in df.columns:
            for cell in df[column]:
                for identifier in activity_ids_of_context_activities(cell):
                    if identifier not in known:
                        known.append(identifier)
    # Ids that name no activity of this data are left out: they are what a link to
    # another session carries, and hiding nothing is the only safe reading of them.
    hidden = hidden & set(known)
    if not known or not hidden:
        return df, known
    shown = set(known) - hidden
    mask = pd.Series(False, index=df.index)
    for column in ACTIVITY_COLUMNS:
        if column in df.columns:
            mask = mask | df[column].map(
                lambda cell: bool(activity_ids_of_context_activities(cell) & shown)
            )
    return df[mask], known
