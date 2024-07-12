def searchValueFromMultiSelector(df, object, search_value,value):
    filtered_df=df
    # Make sure that the set values are in the option list, else they will disappear
    # from the shown select list, but still part of the `value`.
    # Convert the dictionary keys to the appropriate format for dropdown options
    all_options = [{'label': k, 'value': k} for k in df[object].unique()]
    # Filter options based on the search value
    if search_value is not None:
        filtered_options = [o for o in all_options if search_value.lower() in o['label'].lower()]
    else:
        filtered_options = all_options
    # Ensure selected values remain in the options list
    if value:
        selected_options = [o for o in all_options if o['value'] in value]
        filtered_options = selected_options + filtered_options
        filtered_df = df.loc[df[object].isin(value)]
    # Remove duplicates while preserving order
    unique_options = list({v['value']:v for v in filtered_options}.values())
    return filtered_df, unique_options