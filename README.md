# xapi-sg-processor

## Introduction

xAPI-SG processor is a set of Jupyter Notebooks to process xAPI-SG statements (traces), and display a default set of visualizations with information about the data in xAPI-SG.

## Configuration

The main Jupyter Notebook is **xAPISGProcessor.ipynb**. 
By executing this Notebook, you will need to select the file with the widget file selector to point to your JSON file containing a list of xAPI-SG statements.
 
After selected, all xAPI-SG statements in your JSON file will be processed (the Jupyter Notebook ProcessxAPISGStatement.ipynb process each xAPI-SG statement). 
With the information extracted from the statements, the default set of visualizations will be displayed in tabs in the notebook.

### xAPI-SG

The **Experience API Profile for Serious Games (xAPI-SG)** is a validated xAPI Profile to collect information from serious games. 
Each xAPI-SG statement (trace) represents an activity in the context of a serious game.

For more information about the xAPI-SG Profile, check [our wiki page](https://github.com/e-ucm/rage-analytics/wiki/xAPI-SG-Profile) and the [official vocabulary website](http://xapi.e-ucm.es/vocab/seriousgames).

### Default visualizations

The Jupyter Notebooks with the default set of visualizations are included in the folder */vis*. These visualizations are:

* **xAPISG-GamesStartedCompleted**: displays a pie chart of games started and completed.
* **xAPISG-PlayersProgress**: displays a line chart showing progress over time for each player.
* **xAPISG-VideosSeenSkipped**: displays a bar chart showing for each video the total number of times it has been seen and skipped.
* **xAPISG-CompletablesProgress**: displays a bar chart showing for each player the progress achieved in the different completables of the game as well as in the total game.
* **xAPISG-CompletablesScores**: displays a bar chart showing the score achieved by players in the different completables.
* **xAPISG-CompletablesTimes**: displays a bar chart showing for each completable the maximum, minimum and mean time of completion by players.
* **xAPISG-CorrectIncorrectPlayer**: displays a bar chart showing for each user the number of correct and incorrect alternatives selected in multiple-choice questions.
* **xAPISG-CorrectIncorrectQuestion**: displays a bar chart showing the total number of correct and incorrect alternatives selected by players in each multiple-choice question.
* **xAPISG-AlternativesSelectedQuestion**: displays multiple bar charts showing the alternatives selcted in each multiple-choice question.
* **xAPISG-ItemsInteracted**: 
   * display a multibar chart and a heatmap showing the number of times the player has interacted with the item.
   * display a bubble chart showing a bubble in function of the average of players has interacted with the item in a certain period of time.
* **xAPISG-ItemsActionTypeInteracted**: display a multibar chart and a heatmap showing for each action type (like talk_to, etc) the total number of time the player has been interacted with.
* **xAPISG-AccessedAccessible**:
    * display a multibar chart and a heatmap showing for each accessible the total number of time the player has accessed to this zone.
    * display a bubble chart showing a bubble in function of the average of players has accessed this accessible in a certain period of time.
* **xAPISG-MenusSelected**: display multiples bar chart showing for each menus the number of time each player select an option.