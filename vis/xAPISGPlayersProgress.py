import plotly.graph_objs as go
import pandas as pd
import plotly.express as px
initialized_verb_id="http://adlnet.gov/expapi/verbs/initialized"
progressed_verb_id="http://adlnet.gov/expapi/verbs/progressed"
completed_verb_id="http://adlnet.gov/expapi/verbs/completed"
seriousgame_object="https://w3id.org/xapi/seriousgames/activity-types/serious-game"
progress_verbs=[initialized_verb_id,progressed_verb_id,completed_verb_id]

# Define a function to update the progress for specific verbs
def update_progress(row):
    if row['verb.id'] == initialized_verb_id:
        return 0
    elif row['verb.id'] == completed_verb_id:
        return 1
    else:
        return row[result_progress_column]
    
def ProgressPlayerLineChart(df, game):
    result_progress_columns = [col for col in df.columns if 'result' in col and 'progress' in col]
    if len(result_progress_columns) > 0:
        global result_progress_column
        result_progress_column=result_progress_columns[0]
        progress_data=df.loc[df['verb.id'].isin(progress_verbs)].copy()
        progress_data=progress_data.loc[progress_data["object.definition.type"]==seriousgame_object]
        progress_data[result_progress_column] = progress_data.apply(update_progress, axis=1)
        bar_game_data=progress_data.loc[progress_data['object.id'] == game].copy()
        return bar_game_data

def displayPlayerProgressInitFig(bar_game_data, game):
    if isinstance(bar_game_data, pd.DataFrame) and len(bar_game_data) >0:
        data = []
        for actor in bar_game_data['actor.name'].unique():
               bar_data=bar_game_data.loc[bar_game_data['actor.name'] == actor].copy()
               first =bar_data.timestamp.min()
               bar_data["timestampinit"] = pd.to_timedelta(pd.to_datetime(bar_data['timestamp']) - pd.to_datetime(first)) + pd.to_datetime('1970/01/01')
               data.append(go.Scatter(x=bar_data['timestampinit'], y=bar_data[result_progress_column], name=actor, hovertext=f"<b>{actor}</b>", mode="lines+markers"))
        fig = go.Figure(data=data)
    else:
        from vis import xAPISGnoDataToFillVisualization
        fig=xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    fig.update_layout(
        title_text='Progress (same origin) during game level ' + str(game),
    )
    fig.update_xaxes(categoryorder="total descending")
    return fig

def displayPlayerProgressFig(bar_game_data, game):
    if isinstance(bar_game_data, pd.DataFrame) and len(bar_game_data) >0:
        data = []
        for actor in bar_game_data['actor.name'].unique():
            bar_data=bar_game_data.loc[bar_game_data['actor.name'] == actor].copy()
            data.append(go.Scatter(x=bar_data['timestamp'], y=bar_data[result_progress_column], name=actor, hovertext=f"<b>{actor}</b>", mode="lines+markers"))
        fig = go.Figure(data=data)
    else:
        from vis import xAPISGnoDataToFillVisualization
        fig=xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    fig.update_layout(
        title_text='Progress during game level ' + str(game),
    )
    fig.update_xaxes(categoryorder="total descending")
    return fig

# Define a function to update the progress for specific verbs
def update_started_completed_progress(row):
    if row['timestamp_started'] and row['timestamp_completed']:
        return f"Started And Completed"
    else:
        return f"Only Started"
    
def ProgressPlayerPie(df, game):
    progress_data=df.loc[df['verb.id'].isin(progress_verbs)].copy()
    progress_game=progress_data.loc[progress_data["object.definition.type"]==seriousgame_object]
    progress_game=progress_game.loc[progress_game["object.id"] == game]
    
    # Filter for "started" and "completed"
    progress_game_started = progress_game[progress_game['verb.id'] == initialized_verb_id]
    progress_game_completed = progress_game[progress_game['verb.id'] == completed_verb_id]

    # Merge to find actors who started and completed the same object
    progress_game_merged = pd.merge(progress_game_started, progress_game_completed, on=['actor.name'], suffixes=('_started', '_completed'))

    progress_game_merged["startedCompleted"] = progress_game_merged.apply(update_started_completed_progress, axis=1)
    #pie_chart_data=progress_game_merged.groupby(["startedCompleted"])["actor.name"].apply(list).reset_index(name='Actors')
    pie_chart_data=progress_game_merged.groupby(["startedCompleted"])["actor.name"].value_counts().reset_index(name='count')
    #if len(pie_chart_data["Actors"]) > 0:
    #    pie_chart_data["Actors"]= list(set(pie_chart_data["AllActors"][0]))
    #    pie_chart_data["count"]= len(pie_chart_data["Actors"][0])
    #else:
    #    pie_chart_data["Actors"]=[]
    #    pie_chart_data["count"]=0
    return pie_chart_data

def displayPlayerProgressPieFig(pie_chart_data):
    if isinstance(pie_chart_data, pd.DataFrame) and len(pie_chart_data)>0:
        fig = go.Figure(data=[go.Pie(
            labels=pie_chart_data['startedCompleted'],
            values=pie_chart_data['count'],
            hoverinfo='label+percent+value+text',
            text=pie_chart_data['startedCompleted']
        )])
    else:
        from vis import xAPISGnoDataToFillVisualization
        fig=xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    fig.update_layout(
            title_text='Game Status'
    )
    ## Show the plot
    return fig