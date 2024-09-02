import pandas as pd
import plotly.express as px

def VideoSeenSkippedBarChart(df):
    only_cutscenes = df[df['object.definition.type'].str.contains('cutscene', case=False)]
    df_skipped = only_cutscenes[only_cutscenes['verb.id'].str.contains('skipped')]
    df_accessed = only_cutscenes[only_cutscenes['verb.id'].str.contains('accessed')]
    print("Skipped " + str(len(df_skipped)))
    print("Access " + str(len(df_accessed)))
    # Merge to find actors who start and skipped the same object
    df_access_skipped = pd.merge(df_skipped, df_accessed, on=['object.id','actor.name'], how= 'outer', suffixes=('_skipped', '_accessed'))
    df_access_skipped

    # Group by 'object' and 'actor' to get the count
    df_grouped = df_access_skipped[['object.id',  'actor.name', 'verb.id_skipped', 'verb.id_accessed']].groupby(['object.id', 'actor.name']).count().reset_index()
    df_grouped['count_seen_but_skipped']=df_grouped['verb.id_skipped']
    df_grouped['count_seen']=df_grouped['verb.id_accessed']-df_grouped['verb.id_skipped']
    if len(df_grouped) > 0:
        # Create a stacked bar chart with Plotly
        fig = px.bar(df_grouped, x='object.id', y=['count_seen', 'count_seen_but_skipped'], 
                color_discrete_sequence=['#1f77b4', '#ff7f0e'],
                hover_name='actor.name', 
                labels={'count_seen_but_skipped': 'Access Count', 'count_seen': 'Seen Count', 'actor.name':'Actor'})
        ### Show the plot
        return fig
    else: 
        from vis import xAPISGnoDataToFillVisualization
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)