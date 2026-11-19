"""
DataFrame-driven xAPI-SG metrics shared by the visualisation builders.

The original notebooks kept their state in the ``players_info`` dictionary that
``ProcessxAPISGStatement`` filled one statement at a time. The Dash application
has no such dictionary: it holds normalized statements in a DataFrame and
narrows them before a builder is called. This module ports the old aggregation
semantics to that DataFrame so every notebook figure can be rebuilt without
Jupyter widgets, matplotlib figures or mutable module state.
"""
from copy import deepcopy

import pandas as pd

# The fields the notebook plots use, kept in the same shape as the old global
# ``template_player_info`` so the ported builders can be compared with them.
TEMPLATE = {
    "game_started": False,
    "game_completed": False,
    "objects": {},
    "game_progress_per_time": [],
    "completables_scores": {},
    "completables_progress": {},
    "completables_times": {},
    "alternatives": {},
    "action_type_interaction": {},
    "interactions": {},
    "accessible": {},
    "videos_seen": [],
    "videos_skipped": [],
    "selected_menus": {},
}


def _pick_column(df, names=(), suffixes=(), contains=()):
    """Find the normalized column holding a field, across xAPI statement shapes."""
    for name in names:
        if name in df.columns:
            return name
    for column in df.columns:
        lowered = str(column).lower()
        if any(lowered.endswith(str(suffix).lower()) for suffix in suffixes):
            return column
        if any(str(part).lower() in lowered for part in contains):
            return column
    return None


def _columns(df):
    """Map the field names the builders use to columns actually in ``df``."""
    return {
        "actor": _pick_column(df, ["actor.name", "actor.account.name"]),
        "verb": _pick_column(df, ["verb.id"]),
        "object_id": _pick_column(df, ["object.id"]),
        "object_type": _pick_column(df, ["object.definition.type"]),
        "timestamp": _pick_column(df, ["timestamp"]),
        "response": _pick_column(df, ["result.response"], suffixes=["/response"]),
        "success": _pick_column(df, ["result.success"], suffixes=["/success"]),
        "progress": _pick_column(
            df, ["result.progress"], suffixes=["/progress", ".progress"]),
        "score": _pick_column(
            df, ["result.score", "result.score.raw"],
            suffixes=["/score", "/score.raw", ".score", ".score.raw"]),
        "action_type": _pick_column(
            df, ["result.action_type", "result.extensions.action_type"],
            contains=["action_type"]),
    }


def _value(record, columns, name):
    """Read one cell, treating pandas missing values as absent."""
    column = columns.get(name)
    if column is None:
        return None
    value = record.get(column)
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        # A nested list or dict is not a scalar; it is not a field we plot.
        return None
    return value


def _last_segment(value):
    """The lower-case final path segment xAPI-SG uses for verbs and types."""
    if value is None:
        return ""
    return str(value).rstrip("/").split("/")[-1].strip().lower()


def _number(value):
    """Read a numeric result value, including one stored as a string."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(number) else number


def is_success(value):
    """Whether a recorded response was correct, across xAPI result shapes."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        return bool(value)
    return str(value or "").strip().lower() in ("true", "1", "yes")


def _timestamp(value):
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    return None if pd.isna(parsed) else parsed


def _duration_minutes(start, end):
    """Minutes between two parsed timestamps, or None when the pair is incomplete."""
    if start is None or end is None or pd.isna(start) or pd.isna(end):
        return None
    return round((end - start).total_seconds() / 60.0, 3)


def players_info(df):
    """Build per-player metrics from normalized statements.

    Args:
        df (pandas.DataFrame): The normalized, already filtered statements.

    Returns:
        dict: Player name to metrics. Missing or unknown fields are skipped, so a
        partial statement never stops the other visualisations from building.
    """
    info = {}
    if df is None or getattr(df, "empty", True):
        return info
    columns = _columns(df)
    records = list(enumerate(df.to_dict("records")))
    # A session may stream statements out of order. Sort them before folding so
    # a completed event that arrives first still follows its initialization and
    # the metrics do not depend on the order in which statements were received.
    timestamp_column = columns.get("timestamp")
    if timestamp_column:
        def order(pair):
            _, record = pair
            parsed = _timestamp(record.get(timestamp_column))
            return (parsed is None, parsed.value if parsed is not None else 0, pair[0])
        records.sort(key=order)
    for _, record in records:
        actor = _value(record, columns, "actor")
        if actor is None or str(actor) == "":
            continue
        player = info.setdefault(str(actor), deepcopy(TEMPLATE))

        verb = _last_segment(_value(record, columns, "verb"))
        object_id = _value(record, columns, "object_id")
        object_type = _last_segment(_value(record, columns, "object_type"))
        object_key = str(object_id) if object_id is not None else ""
        timestamp = _timestamp(_value(record, columns, "timestamp"))
        response = _value(record, columns, "response")
        success = _value(record, columns, "success")
        progress = _number(_value(record, columns, "progress"))
        score = _number(_value(record, columns, "score"))
        action_type = _value(record, columns, "action_type")

        if object_key:
            if object_type:
                player["objects"].setdefault(object_type, [])
                if object_key not in player["objects"][object_type]:
                    player["objects"][object_type].append(object_key)

        if verb == "initialized":
            if object_type == "serious-game":
                player["game_started"] = True
                if timestamp is not None:
                    player["game_progress_per_time"].append([0, timestamp])
            if object_key:
                player["completables_times"][object_key] = [timestamp, None]

        elif verb == "completed":
            if object_type == "serious-game":
                player["game_completed"] = True
                if timestamp is not None:
                    player["game_progress_per_time"].append([1, timestamp])
            if object_key and object_key in player["completables_times"]:
                player["completables_times"][object_key][1] = timestamp
            if object_key and score is not None:
                player["completables_scores"][object_key] = score

        elif verb == "progressed":
            if object_type == "serious-game" and progress is not None and timestamp is not None:
                player["game_progress_per_time"].append([progress, timestamp])
                if progress == 1:
                    player["game_completed"] = True
            if object_key and progress is not None and timestamp is not None:
                player["completables_progress"].setdefault(object_key, [])
                player["completables_progress"][object_key].append([progress, timestamp])

        elif verb in ("interacted", "used"):
            if action_type:
                (player["action_type_interaction"]
                 .setdefault(object_type, {})
                 .setdefault(object_key, {})
                 .setdefault(str(action_type), []))
                if timestamp is not None:
                    (player["action_type_interaction"][object_type][object_key]
                     [str(action_type)].append(timestamp))
            else:
                (player["interactions"]
                 .setdefault(object_type, {})
                 .setdefault(object_key, []))
                if timestamp is not None:
                    player["interactions"][object_type][object_key].append(timestamp)

        elif verb == "selected":
            if object_type == "alternative" and object_key:
                player["alternatives"].setdefault(object_key, [])
                player["alternatives"][object_key].append((response, success))
            elif object_type == "menu" and object_key and response is not None:
                (player["selected_menus"]
                 .setdefault(object_key, {})
                 .setdefault(str(response), []))
                if timestamp is not None:
                    player["selected_menus"][object_key][str(response)].append(timestamp)

        elif verb == "accessed":
            if object_type == "cutscene" and object_key:
                player["videos_seen"].append(object_key)
            elif object_type == "accessible" and object_key:
                player["accessible"].setdefault(object_key, [])
                if timestamp is not None:
                    player["accessible"][object_key].append(timestamp)

        elif verb == "skipped":
            if object_type == "cutscene" and object_key:
                player["videos_skipped"].append(object_key)

    return info


def _ids_from_info(info, kind):
    """Target ids of one kind, in first-seen order."""
    objects = set()
    for player in info.values():
        for name, ids in (player.get("objects") or {}).items():
            if (kind == "game" and name == "serious-game"
                    or kind == "video" and name == "cutscene"
                    or kind == "completable" and name == "level"
                    or kind == "alternative" and name == "alternative"
                    or kind == "accessible" and name == "accessible"
                    or kind == "menu" and name == "menu"):
                objects.update(ids)

    if kind == "completable":
        for player in info.values():
            objects.update((player.get("completables_progress") or {}).keys())
            objects.update((player.get("completables_scores") or {}).keys())
            objects.update((player.get("completables_times") or {}).keys())
    elif kind == "completable-change":
        for player in info.values():
            for identifier, values in (player.get("completables_progress") or {}).items():
                if _is_change_series(values):
                    objects.add(identifier)
    elif kind == "alternative":
        for player in info.values():
            objects.update((player.get("alternatives") or {}).keys())
    elif kind == "item":
        for player in info.values():
            for items in (player.get("interactions") or {}).values():
                objects.update(items.keys())
    elif kind == "action-type":
        for player in info.values():
            for items in (player.get("action_type_interaction") or {}).values():
                for actions in items.values():
                    objects.update(actions.keys())
    elif kind == "accessible":
        for player in info.values():
            objects.update((player.get("accessible") or {}).keys())
    elif kind == "menu":
        for player in info.values():
            objects.update((player.get("selected_menus") or {}).keys())
    return [identifier for identifier in sorted(objects) if identifier]


def ids_from_info(info, kind):
    """Target ids from metrics already built by :func:`players_info`."""
    return _ids_from_info(info, kind)


def target_ids(df, kind):
    """Ids a target selector should offer for ``kind``."""
    return ids_from_info(players_info(df), kind)


def short_label(target):
    """Readable name for a target id, using the legacy last-segment form."""
    if target is None:
        return ""
    return str(target).rstrip("/").split("/")[-1]


def canonical_target(info, kind, target):
    """Accept both the full object id and the notebook's last-segment id."""
    if not target:
        return None
    identifiers = _ids_from_info(info, kind)
    if target in identifiers:
        return target
    for identifier in identifiers:
        if short_label(identifier) == str(target):
            return identifier
    return str(target)


def _is_change_series(values):
    """Progress series the old notebook treated as increase/decrease data."""
    numbers = [_number(value[0]) for value in values if value]
    return bool(numbers) and any(
        number is None or number < 0 or number > 1 for number in numbers)


def game_rows(info):
    """Yield ``player``, ``started`` and ``completed`` for each player."""
    for player, values in sorted(info.items()):
        yield {
            "player": player,
            "started": bool(values.get("game_started")),
            "completed": bool(values.get("game_completed")),
        }


def completable_progress_rows(info, target=None, only_changes=False):
    """Yield progress samples with ``player``, ``completable``, ``progress``, ``time``."""
    kind = "completable-change" if only_changes else "completable"
    selected = canonical_target(info, kind, target)
    for player, values in sorted(info.items()):
        for completable, samples in (values.get("completables_progress") or {}).items():
            if selected and completable != selected:
                continue
            if only_changes and not _is_change_series(samples):
                continue
            for progress, timestamp in samples:
                number = _number(progress)
                if number is None:
                    continue
                yield {
                    "player": player, "completable": completable,
                    "progress": number, "time": timestamp,
                }


def completable_score_rows(info, target=None):
    """Yield final scores with ``player``, ``completable`` and ``score``."""
    selected = canonical_target(info, "completable", target)
    for player, values in sorted(info.items()):
        for completable, score in (values.get("completables_scores") or {}).items():
            if selected and completable != selected:
                continue
            number = _number(score)
            if number is not None:
                yield {"player": player, "completable": completable, "score": number}


def completable_time_rows(info, target=None):
    """Yield completion durations with ``player``, ``completable`` and ``minutes``."""
    selected = canonical_target(info, "completable", target)
    for player, values in sorted(info.items()):
        for completable, times in (values.get("completables_times") or {}).items():
            if selected and completable != selected:
                continue
            if not times or len(times) < 2:
                continue
            minutes = _duration_minutes(times[0], times[1])
            if minutes is not None:
                yield {
                    "player": player, "completable": completable,
                    "minutes": minutes,
                }


def alternative_answer_rows(info, target=None):
    """Yield ``player``, ``alternative``, ``response`` and ``success``."""
    selected = canonical_target(info, "alternative", target)
    for player, values in sorted(info.items()):
        for alternative, answers in (values.get("alternatives") or {}).items():
            if selected and alternative != selected:
                continue
            for response, success in answers:
                yield {
                    "player": player, "alternative": alternative,
                    "response": response, "success": is_success(success),
                }


def interaction_rows(info, target=None):
    """Yield ``player``, ``object_type``, ``item`` and ``time``."""
    selected = canonical_target(info, "item", target)
    for player, values in sorted(info.items()):
        for object_type, items in (values.get("interactions") or {}).items():
            for item, times in items.items():
                if selected and item != selected:
                    continue
                for timestamp in times:
                    yield {
                        "player": player, "object_type": object_type,
                        "item": item, "time": timestamp,
                    }


def action_type_rows(info, target=None):
    """Yield ``player``, ``object_type``, ``item``, ``action_type`` and ``time``."""
    selected = canonical_target(info, "action-type", target)
    for player, values in sorted(info.items()):
        for object_type, items in (values.get("action_type_interaction") or {}).items():
            for item, actions in items.items():
                for action_type, times in actions.items():
                    if selected and action_type != selected:
                        continue
                    for timestamp in times:
                        yield {
                            "player": player, "object_type": object_type,
                            "item": item, "action_type": action_type,
                            "time": timestamp,
                        }


def accessible_rows(info, target=None):
    """Yield ``player``, ``accessible`` and ``time``."""
    selected = canonical_target(info, "accessible", target)
    for player, values in sorted(info.items()):
        for accessible, times in (values.get("accessible") or {}).items():
            if selected and accessible != selected:
                continue
            for timestamp in times:
                yield {"player": player, "accessible": accessible, "time": timestamp}


def menu_rows(info, target=None):
    """Yield ``player``, ``menu``, ``selection`` and ``time``."""
    selected = canonical_target(info, "menu", target)
    for player, values in sorted(info.items()):
        for menu, selections in (values.get("selected_menus") or {}).items():
            if selected and menu != selected:
                continue
            for selection, times in selections.items():
                for timestamp in times:
                    yield {
                        "player": player, "menu": menu,
                        "selection": selection, "time": timestamp,
                    }
