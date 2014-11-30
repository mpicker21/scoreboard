import re, threading, subprocess, json, nflgame
from urllib2 import urlopen
from datetime import date, timedelta
from operator import itemgetter

date = date.today()
dwell_time = 5
refresh_rate = 60
sport = "nfl"
currentgame = 0
scoredata = []
nfl_season = ""
nfl_time = ""
nfl_weeks = ""
scoreslock = threading.Lock()
source_trigger = threading.Event()
display_trigger = threading.Event()
source_ready = threading.Event()

def build_nfl_times():
  a = []
  for x in range(0, 4 + 1):
    a.append([x, 'PRE'])
  for x in range(1, 17 + 1):
    a.append([x, 'REG'])
  for x in range(1, 4 + 1):
    a.append([x, 'POST'])
  return a

def set_nfl_current():
  global nfl_season
  cyad = nflgame.live.current_year_and_week()
  nfl_season = cyad[0]
  return nfl_weeks.index([cyad[1], nflgame.live._cur_season_phase])

def get_nhl_scores(date):
  global scoredata
  scores = []
  url = "http://live.nhle.com/GameData/GCScoreboard/" + date.strftime('%Y-%m-%d') + ".jsonp"
  raw = urlopen(url).read()
  raw = re.sub("loadScoreboard\(", "", raw)
  raw = re.sub("\)\\n", "", raw)
  games = json.loads(raw)['games']
  for game in games:
    awayteam = game['ata']
    hometeam = game['hta']
    awayscore = game['ats']
    homescore = game['hts']
    if game['gs'] == 1:
      time = re.search(r'(\d*:\d\d)', game['bs']).group(1)
      period = ""
    elif game['gs'] == 3:
      time = re.search(r'(\d*:\d\d)', game['bs']).group(1)
      period = period = re.search(r'\s(\d)', game['bs']).group(1)
    elif game['gs'] == 5:
      time = ""
      period = "F"
    gameid = game['id']
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = scores
  return

def get_nba_scores(date):
  global scoredata
  scores = []
  url = "http://data.nba.com/5s/json/cms/noseason/scoreboard/" + date.strftime('%Y%m%d') + "/games.json"
  raw = urlopen(url).read()
  games = json.loads(raw)['sports_content']['games']['game']
  for game in games:
    awayteam = game['visitor']['team_key']
    hometeam = game['home']['team_key']
    awayscore = game['visitor']['score']
    homescore = game['home']['score']
    if game['period_time']['game_status'] == "1":
      time = re.search(r'(\d*:\d\d)', game['period_time']['period_status']).group(1)
      period = ""
    elif game['period_time']['game_status'] == "2":
      time = game['period_time']['game_clock']
      period = game['period_time']['period_value']
    elif game['period_time']['game_status'] == "3":
      time = ""
      period = "F"
    gameid = game['id']
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = scores
  return

def get_nfl_scores(nfl_time):
  global scoredata
  scores = []
  this_week = []
  sched = nflgame.sched.games
##  populate this_week with a template for this week
  for key in sched:
    if sched[key]['year'] == nfl_season:
      if sched[key]['season_type'] == nfl_weeks[nfl_time][1]:
        if sched[key]['week'] == nfl_weeks[nfl_time][0]:
          awayteam = sched[key]['away']
          hometeam = sched[key]['home']
          awayscore = ""
          homescore = ""
          time = sched[key]['time']
          period = ""
          gameid = sched[key]['gamekey']
          this_week.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  games = nflgame.games(nfl_season, week=nfl_weeks[nfl_time][0], kind=nfl_weeks[nfl_time][1])
##  run through this_week and fill in scores for finished/ongoing games
  for game in this_week:
    for g in games:
      if g.gamekey == game['gameid']:
        if g.time.is_pregame():
          pass
        elif g.time.is_final():
          game['awayscore'] = g.score_away
          game['homescore'] = g.score_home
          game['time'] = ""
          game['period'] = "F"
        else:
          game['awayscore'] = g.score_away
          game['homescore'] = g.score_home
          game['time'] = g.time.clock
          game['period'] = g.time.qtr
  this_week = sorted(this_week, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = this_week
  return

def update_scores():
  global sport
  if sport == "nhl":
    get_nhl_scores(date)
  elif sport == "nba":
    get_nba_scores(date)
  elif sport == "nfl":
    get_nfl_scores(nfl_time)

def ir_monitor():
  listener = pifacecad.IREventListener(prog="scoreboard")
  listener.register('vol+', change_vol)
  listener.register('vol-', change_vol)
  listener.register('mute', change_vol)
  listener.register('right', change_game)
  listener.register('left', change_game)
  listener.register('up', change_day)
  listener.register('down', change_day)
  listener.register('ffwd', change_speed)
  listener.register('rew', change_speed)
  listener.register('pause', change_mode)
  listener.register('power', shutdown)
  listener.register('stop', toggle_display)  
  listener.register('1', change_sport)
  listener.register('2', change_sport)
  listener.activate()

def change_vol(event):
  if event == "vol+":
    subprocess.call("amixer", "set", "PCM", "200+")
  if event == "vol-":
    subprocess.call("amixer", "set", "PCM", "200-")
  if event == "mute":
    subprocess.call("amixer", "set", "PCM", "toggle")

def change_game(event):
  global currentgame, scoredata
  if event == "right":
    currentgame += 1
    if currentgame > (len(scoredata) - 1):
      currentgame = 0
  elif currentgame == "left":
    currentgame -= 1
    if currentgame < 0:
      currentgame = (len(scoredata) -1)
  display_trigger.set()

def change_day(event):
  global date, nfl_time
  if event == "up":
    if sport == "nfl":
      if nfl_time < 25:
        nfl_time += 1
    else:
      date = date + datetime.timedelta(days=1)
  elif event == "down":
    if sport == "nfl":
      if nfl_time > 0:
        nfl_time -= 1
    else:
      date = date - datetime.timedelta(days=1)
  source_trigger.set()

def change_speed(event):
  global dwell_time
  if event == "ffwd":
    dwell_time -= 1
  if event == "rew":
    dwell_time += 1

def shutdown():
  subprocess.call("shutdown", "-h", "now")

def change_sport(event):
  global sport, date
  if event == "1":
    sport = "nhl"
  if event == "2":
    sport = "nba"
  date = date.today()
  source_trigger.set()
  if event == "3":
    sport = "nfl"
    nfl_time = set_nfl_current()

def test_display():
  global scoredata, currentgame
  from time import sleep
  source_ready.wait()
  while True:
    with scoreslock:
      print "Game: %s" % (scoredata[currentgame]['gameid'])
      print "Time: %s  Period: %s" % (scoredata[currentgame]['time'], scoredata[currentgame]['period'])
      print "Away: %s    %s" % (scoredata[currentgame]['awayteam'], scoredata[currentgame]['awayscore'])
      print "Home: %s    %s" % (scoredata[currentgame]['hometeam'], scoredata[currentgame]['homescore'])
      print ""
    currentgame += 1
    if currentgame > (len(scoredata) - 1):
      currentgame = 0
    sleep(5)

def source_daemon():
  print "source_daemon is running"
  while True:
    while not source_trigger.is_set():
      print "updating scores"
      update_scores()
      source_ready.set()
      source_trigger.wait(refresh_rate)
    source_trigger.clear()

def main():
  global nfl_time, nfl_weeks
  nfl_weeks = build_nfl_times()
  nfl_time = set_nfl_current()
  source = threading.Thread(target=source_daemon)
  source.daemon = True
  source.start()
  test_display()

main()

