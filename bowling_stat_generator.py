################################ SETTINGS #####################################
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
sys.path.append("C:/Users/thisi/Documents/Python Scripts")
import pretty_print
from statistics import mean
from math import floor

################################## GLOBALS ####################################
SCHEDULE = {
    "Week 1": [],
    "Week 2": ["The Greasy Pineapples", "We Don't Give a Split"],
    "Week 3": ["The Bowling Mambas", "We Don't Give a Split"],
    "Week 4": ["The Bowling Mambas", "The Greasy Pineapples"],
    "Week 5": ["The Greasy Pineapples", "We Don't Give a Split"],
    "Week 6": ["The Bowling Mambas", "We Don't Give a Split"],
    "Week 7": ["The Bowling Mambas", "The Greasy Pineapples"],
}

TEAMS = ["The Bowling Mambas", "The Greasy Pineapples", "We Don't Give a Split"]

MEN = {
    'Dan Gillet',
    'Michael Sanfilippo',
    'Randy Meyer',
    'Joseph Heinz',
    'Matthew Manuele',
    'Michael Rand',
    'Andrew Manuele',
    'Brian Levine',
    'Michael Contento',
}

WOMEN = {
    'Katie Wiederhold',
    'Olivia Kerr',
    'Kamila Mikos',
    'Danielle Docheff',
    'Alex Avila',
    'Rachel Rubin',
    'Elizabeth Manuele',
}

HEAD_2_HEAD_BONUS = 25
BEST_MALE_BOWLER_BONUS = 25
BEST_FEMALE_BOWLER_BONUS = 25
BEST_SCORE_BONUS = 25

BASIS_SCORE = 200
PERCENTAGE_FACTOR = .9

USE_HANDICAP = True

################################## MAIN #######################################
def main():
    """
    get data from google sheet
    calculate handicap
    for each team per week:
        -get best overall game
        -get 2nd best game
        -head to head bonus
        -best male bowler name and score
        -best female bowler name and score
        -total pins on season
    """
    season_data = {}
    data, sheet = get_data()
    handicaps = calculate_handicap(data)
    
    for game in data:
        player = game["Player"]
        if game["Frame 10"] == "-":
            game["adjusted_score"] = "-"
        else:
            game["adjusted_score"] = game["Frame 10"] + handicaps[player] if \
                USE_HANDICAP else game["Frame 10"]
    
    for week in SCHEDULE:
        season_data[week] = {}
        for team in TEAMS:
            ordered_scores = get_ordered_scores(data, week, team)
            best_bowler_data = get_best_bowler_data(data, week, team)
            
            season_data[week][team] = {
                "best_score": ordered_scores[0],
                "second_best": ordered_scores[1],
                "best_male_bowler": best_bowler_data["male_name"],
                "best_male_score": best_bowler_data["male_score"],
                "best_female_bowler": best_bowler_data["female_name"],
                "best_female_score": best_bowler_data["female_score"],
            }
        season_data[week]["h2h_bonus"] = get_h2h_bonus(
          season_data[week],
          SCHEDULE[week]
        )
    
    #calculate total pins on season
    for week_data in season_data.values():
      week_data = get_this_weeks_total_pins(week_data)
    
    #calc cumulative pins per week
    for team in TEAMS:
      cumulative_pins = 0
      for week_data in season_data.values():
        cumulative_pins += week_data[team]["current_total_pins"]
        week_data[team]["cumulative_pins"] = cumulative_pins
        
    pstop(season_data)
    update_google(season_data, sheet)
    
    
    
############################# FUNCTIONS IN MAIN ###############################
def get_data():
    """
    followed https://www.youtube.com/watch?v=vISRn5qFrkM
    """
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
            r'C:\Users\thisi\Documents\Python Scripts\bowling_tracker'
            '\\bowling_secret_info.json', scope)
    client = gspread.authorize(creds)
    
    sheet = client.open('Bowling Data').worksheet("Season 1 Data")
    
    bowling_data = sheet.get_all_records()
    return bowling_data, sheet
    

def calculate_handicap(data):
    """
    https://www.bowlingball.com/BowlVersity/how-to-calculate-bowling-handicap#:~:text=Subtract%20your%20average%20score%20from,Again%2C%20drop%20the%20fraction.
    -calculate the average score of each player last season
    -round down to whole number
    -(basis score - average) * percentage factor
    -round down to whole number
    """
    handicaps = {}
    
    players = MEN.union(WOMEN)
    for player in players:
        average = floor(
            mean(
                [i["Frame 10"] for i in data if i["Player"] == player \
                 and i["Frame 10"] != "-"]
            )
        )
        handicaps[player] = floor(
            (BASIS_SCORE - average) * PERCENTAGE_FACTOR
        )
    return handicaps
    

def get_ordered_scores(data, week, team):
    """
    takes in the data, current week and team name. returns the total scores
    for each game for that team for that week in a list
    """
    games = []
    
    num_of_games = len(set(x["Game"] for x in data if x["Date"] == week and \
        x["Team"] == team))
    
    for i in range(1, num_of_games+1):
      scores = []
      for game in data:
          if game["Date"] == week:
              if game["Team"] == team:
                if game["Game"] == i and game["adjusted_score"] != "-":
                    scores.append(game["adjusted_score"])
      games.append(sum(scores))
    return sorted(games, reverse=True)


def get_h2h_bonus(week_data, matchup):
  """
  takes in the high scores for the week and based on SCHEDULE determines which
  team won the head to head bonus for that week
  """
  if not matchup:
    return []
  
  if week_data[matchup[0]]["best_score"] > week_data[matchup[1]]["best_score"]:
    return [matchup[0]]
  elif week_data[matchup[0]]["best_score"] < week_data[matchup[1]]["best_score"]:
    return [matchup[1]]
  else:
    #if there is a tie for highest score, return both teams. we will split
    #the bonus later on
    return matchup


def get_best_bowler_data(data, week, team):
  """
  takes in the data universe, the week and team. Returns the best male and 
  female bowler names and scores for that week
  """
  best_bowler_stats = {
    "male_name": None,
    "male_score": 0,
    "female_name": None,
    "female_score": 0,
  }
    
  num_of_games = len(set(x["Game"] for x in data if x["Date"] == week and \
      x["Team"] == team))
  
  for i in range(1, num_of_games+1):
    scores = []
    for game in data:
      if game["Date"] == week:
        if game["Team"] == team:
          if game["Game"] == i and game["adjusted_score"] != "-":
            if game["Player"] in WOMEN:
              if game["adjusted_score"] > best_bowler_stats["female_score"]:
                best_bowler_stats["female_name"] = game["Player"]
                best_bowler_stats["female_score"] = game["adjusted_score"]
            else:
              if game["adjusted_score"] > best_bowler_stats["male_score"]:
                best_bowler_stats["male_name"] = game["Player"]
                best_bowler_stats["male_score"] = game["adjusted_score"]
  return best_bowler_stats


def get_this_weeks_total_pins(week_data):
  """
  takes in all data up to this point and calculates the total pins for the
  current week
  -get bonuses
    -best score bonus
    -h2h bonus
    -best male bowler bonus
    -best female bowler bonus
  """
  
  h2h_bonus = week_data.pop("h2h_bonus")
  best_scores = []
  best_male_bowlers = []
  best_female_bowlers = []
  
  #first get the best scores for the bonus categories
  for team_name, data in week_data.items():
    best_scores.append((team_name, data["best_score"]))
    best_male_bowlers.append((team_name, data["best_male_score"]))
    best_female_bowlers.append((team_name, data["best_female_score"]))

  best_score_team, best_score_value = max(best_scores, key = lambda x:x[1])
  best_male_team, best_male_value = max(best_male_bowlers, key = lambda x:x[1])
  best_female_team, best_female_value = max(best_female_bowlers, key = lambda x:x[1])

  #then calculate the total pins for the week
  for team_name, data in week_data.items():
    data["current_total_pins"] = calc_pins(
      team_name,
      data["best_score"],
      data["second_best"],
      best_score_team,
      best_male_team,
      best_female_team,
      h2h_bonus
    )
  
  return week_data


def calc_pins(
  team_name, 
  best_score, 
  second_best, 
  best_score_team, 
  best_male_team,
  best_female_team,
  h2h_bonus
):
  
  total_pins = (
    best_score + 
    second_best + 
    (BEST_SCORE_BONUS if best_score_team == team_name else 0) +
    (BEST_MALE_BOWLER_BONUS if best_male_team == team_name else 0) +
    (BEST_FEMALE_BOWLER_BONUS if best_female_team == team_name else 0) +
    (HEAD_2_HEAD_BONUS if team_name in h2h_bonus else 0)
  )
  return total_pins


def update_google(season_data, sheet):
  """
  updates the google sheet with the proper data
  """
  pass
################################# UTILITIES ###################################

def pstop(msg):
    raise Exception(pretty_print.pretty_print(msg))

if __name__ == "__main__":
    main()