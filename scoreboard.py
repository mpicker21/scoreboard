import re, threading, subprocess, json, nflgame, smbus
from urllib2 import urlopen
from datetime import date, timedelta
from operator import itemgetter
from bottle import request, route, static_file, run

# This section declares strings, locks, etc.
i2c = smbus.SMBus(1)
disp_home = 0x52
disp_away = 0x50
disp_teambrt = 0x33
date = date.today()
dwell_time = 5
refresh_rate = 60
sport = "nhl"
dedicated_mode = False
currentgame = 0
scoredata = []
last_score = ""
nfl_season = ""
nfl_time = ""
nfl_weeks = ""
scoreslock = threading.Lock()
source_trigger = threading.Event()
display_trigger = threading.Event()
source_ready = threading.Event()
disp_ready = threading.Event()

# This section defines functions
#   Hardware functions
def init_board():
  try:
    for x in [disp_home, disp_away]:
      i2c.write_byte_data(x, 0x04, 0x05                                   # Turns MAX6953 on and sets fast blink
      i2c.write_i2c_block_data(x, 0x01, [disp_teambrt, disp_teambrt])     # Sets brightness for the team name
      i2c.write_byte_data(x, 0x03, 0x01)                                  # Sets SCANLIMIT to 4
  except:
    init_board()
    return
  disp_ready.set()
  return

def set_team(hoa, name):
  namechars = []
  for ch in enumerate(name):
    namechars.append(ord(ch))
  try:
    i2c.write_i2c_block_data(hoa, 0x20, [0x20, 0x20, 0x20])
    i2c.write_itc_block_data(hoa, 0x20, namechars)
  except:
    init_board()
    set_team(hoa, name)
    return
  return

#   Source functions
def build_nfl_times():                                                    # Build table of PRE/REG/POST and weeks in each to make it easier to reference with nfl_time
  a = []
  for x in range(0, 4 + 1):
    a.append([x, 'PRE'])
  for x in range(1, 17 + 1):
    a.append([x, 'REG'])
  for x in range(1, 4 + 1):
    a.append([x, 'POST'])
  return a

def set_nfl_current():                                                    # Sets the current nfl_season and returns the current nfl_time
  global nfl_season
  cyad = nflgame.live.current_year_and_week()
  nfl_season = cyad[0]
  return nfl_weeks.index([cyad[1], nflgame.live._cur_season_phase])

def get_nhl_scores(date):                                                 # Pulls json files from NHL, parses them, and fills scoredata with data
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
    elif game['gs'] == 2:
      time = ""
      period = "P"
    elif game['gs'] == 3:
      try:
        time = re.search(r'(\d*:\d\d)', game['bs']).group(1)
      except:
        time = "00:00"
      period = re.search(r'\s(\d)', game['bs']).group(1)
    elif game['gs'] == 5:
      time = ""
      period = "F"
    gameid = game['id']
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = scores
  return

def get_nba_scores(date):                                                 # Pulls json files fron NBA, parses them, and fills scoredata with data
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

def get_nfl_scores(nfl_time):                                             # Uses nflgame to fill scoredata with data
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

def update_scores():                                                      # Runs the appropriate score source to update scores
  global sport
  if sport == "nhl":
    get_nhl_scores(date)
  elif sport == "nba":
    get_nba_scores(date)
  elif sport == "nfl":
    get_nfl_scores(nfl_time)

#   Controller functions
def ir_monitor():                                                         # IR daemon, sets up listener for buttons and ties them to commands
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
  listener.register('2', change_sport)
  listener.activate()

def change_vol(event):                                                    # Changes volume up, down, or toggles mute... obviously
  if event == "vol+":
    subprocess.call(["amixer", "set", "PCM", "200+"])
  if event == "vol-":
    subprocess.call(["amixer", "set", "PCM", "200-"])
  if event == "mute":
    subprocess.call(["amixer", "set", "PCM", "toggle"])

def change_game(event):                                                   # Updates currentgame to the next or previous game and then triggers the display to change
  global currentgame, scoredata
  if event == "right":
    currentgame += 1
    if currentgame > (len(scoredata) - 1):
      currentgame = 0
  if event == "left":
    currentgame -= 1
    if currentgame < 0:
      currentgame = (len(scoredata) - 1)
  display_trigger.set()

def change_day(event):                                                    # Updates date to next or previous day, triggers source refresh, and triggers display change
  global date, nfl_time, currentgame
  if event == "up":
    if sport == "nfl":
      if nfl_time < 25:
        nfl_time += 1
    else:
      date = date + timedelta(days=1)
  elif event == "down":
    if sport == "nfl":
      if nfl_time > 0:
        nfl_time -= 1
    else:
      date = date - timedelta(days=1)
  currentgame = 0
  source_trigger.set()
  source_ready.wait()
  display_trigger.set()

def change_speed(event):                                                  # Change dwell_time to shorten or lenghten the amount of time the scoreboard sits on a game
  global dwell_time
  if event == "ffwd":
    dwell_time -= 1
  if event == "rew":
    dwell_time += 1

def change_mode():
  global dedicated_mode, last_score
  dedicated_mode = not dedicated_mode
  if dedicated_mode:
    last_score = scoredata[currentgame]
    source_trigger.set()
    source_ready.wait()
  display_trigger.set()

def shutdown():                                                           # Power button shuts the pi down completely
  subprocess.call("shutdown", "-h", "now")

def change_sport(event):                                                  # Sport buttons switch sports, date and triggers source refresh and display change
  global sport, date, currentgame
  if event == "1" or event == "nhl":
    sport = "nhl"
  elif event == "2" or event == "nba":
    sport = "nba"
  elif event == "3" or event == "nfl":
    sport = "nfl"
    nfl_time = set_nfl_current()
  currentgame = 0
  date = date.today()
  source_trigger.set()
  source_ready.wait()
  display_trigger.set()

@route('/controller.htm')
def control():
  return static_file('controller.htm', root='www')

@route('/command.php', method='POST')
def webcommand():
  dothis = request.forms.get('command')
  if dothis == "nhl" or dothis == "nba" or dothis == "nfl":
    change_sport(dothis)
  elif dothis == "volup":
    change_vol("vol+")
  elif dothis == "voldown":
    change_vol("vol-")
  elif dothis == "volmute":
    change_vol("mute")
  elif dothis == "nextgame":
    change_game("right")
  elif dothis == "prevgame":
    change_game("left")
  elif dothis == "nextday":
    change_day("up")
  elif dothis == "prevday":
    change_day("down")
  elif dothis == "dwelldown":
    change_speed("ffwd")
  elif dothis == "dwellup":
    change_speed("rew")
  elif dothis == "mode":
    change_mode()
  elif dothis == "shutdown":
    shutdown()

#   Other functions
def dedicated_compare(last):
  with scoreslock:
    if last['gameid'] != scoredata[currentgame]['gameid']:
      pass
    if last == scoredata[currentgame]:
      pass
    elif last['homescore'] != scoredata[currentgame]['homescore']:
      print "Home team scored!"
    elif last['awayscore'] != scoredata[currentgame]['awayscore']:
      print "Away team scored!"
    elif last['period'] == "":
      pass
    elif last['time'] != scoredata[currentgame]['time']:
      if scoredata[currentgame]['time'] == "00:00" or "":
        print "End of period!"
      elif last['period'] != scoredata[currentgame]['period']:
        if last['time'] != "00:00" or "":
          print "End of period!"
      else:
        pass

def test_display():                                                       # Simple terminal output for debugging
  global scoredata, currentgame, last_score
  from time import sleep
  source_ready.wait()
  while True:
    while not display_trigger.is_set():
      if not dedicated_mode:
        currentgame += 1
        if currentgame > (len(scoredata) - 1):
          currentgame = 0
      with scoreslock:
        set_team(disp_home, scoredata[currentgame]['hometeam']
        set_team(disp_away, scoredata[currentgame]['awayteam']
        print "Game: %s" % (scoredata[currentgame]['gameid'])
        print "Time: %s  Period: %s" % (scoredata[currentgame]['time'], scoredata[currentgame]['period'])
        print "Away: %s    %s" % (scoredata[currentgame]['awayteam'], scoredata[currentgame]['awayscore'])
        print "Home: %s    %s" % (scoredata[currentgame]['hometeam'], scoredata[currentgame]['homescore'])
        print ""
      if dedicated_mode:
        dedicated_compare(last_score)
        last_score = scoredata[currentgame]
        display_trigger.wait(10)
      else:
        display_trigger.wait(dwell_time)
    display_trigger.clear()

#   Daemon functions
def source_daemon():                                                      # A looping function that updates scores at refresh_rate interval unless source_trigger is set
  print "source_daemon is running"
  while True:
    while not source_trigger.is_set():
      print "updating scores"
      update_scores()
      source_ready.set()
      if dedicated_mode:
        source_trigger.wait(10)
      else:
        source_trigger.wait(refresh_rate)
    source_trigger.clear()

def remote_daemon():
  print "remote_daemon is running"
  run(host='0.0.0.0', port=8080)

def main():                                                               # The main function that gets everything running
  global nfl_time, nfl_weeks
  nfl_weeks = build_nfl_times()
  nfl_time = set_nfl_current()
  source = threading.Thread(target=source_daemon)
  source.daemon = True
  source.start()
  remote = threading.Thread(target=remote_daemon)
  remote.daemon = True
  remote.start()
  test_display()

main()

