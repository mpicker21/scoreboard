import re, threading, subprocess
from bs4 import BeautifulSoup
from urllib2 import urlopen
from datetime import date, timedelta
from operator import itemgetter

date = date.today()
dwell_time = 5
refresh_rate = 60
sport = "nhl"
currentgame = 0
scoredata = []
nfl_season = ""
nfl_week = ""
scoreslock = threading.Lock()
source_trigger = threading.Event()
display_trigger = threading.Event()
source_ready = threading.Event()

def get_nhl_scores(date):
  global scoredata
  scores = []
  if date.month > 8:
    season = str(date.year) + str(date.year + 1)
  else:
    season = str(date.year - 1) + str(date.year)
  url = "http://www.nhl.com/ice/scores.htm?date=" + date.strftime('%m/%d/%Y') + "&season=" + season
  html = urlopen(url).read()
  soup = BeautifulSoup(html, "html")
  games = soup.find_all("div", "gamebox")
  for game in games:
    awayteam = game.find_all("a", {"rel" : True})[0]['rel'][0]
    hometeam = game.find_all("a", {"rel" : True})[3]['rel'][0]
    awayscore = game.find_all("td", "total")[0].string
    homescore = game.find_all("td", "total")[1].string
    if re.search(r'FINAL', game.th.contents[0]) is not None:
      time = ""
      period = "F"
    elif re.search(r'ET', game.th.contents[0]) is not None:
      time = re.search(r'(\d*:\d\d)', game.th.contents[0]).group(1)
      period = ""
    elif re.search(r'END', game.th.contents[0]) is not None:
      time = "00:00"
      period = re.search(r'\s(\d)', game.th.contents[0]).group(1)
    elif re.search(r'st|nd|rd', game.th.contents[0]) is not None:
      time = re.search(r'(\d\d:\d\d)', game.th.contents[0]).group()
      period = re.search(r'\s(\d)', game.th.contents[0]).group(1)
    else:
      time = re.search(r'(\d\d:\d\d)', game.th.contents[0]).group()
      period = "0"
    gameid = re.search('=(\d*)', game.find("div", "gcLinks").a['href']).group(1)
    time = re.sub(r':', '', time)
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = scores
  return

def get_nba_scores(date):
  global scoredata
  scores = []
  url = 'http://www.nba.com/gameline/' + date.strftime("%Y%m%d") + '/'
  html = urlopen(url).read()
  soup = BeautifulSoup(html, "html")
  games = soup.find_all(id=re.compile('nbaGL\d'))
  for game in games:
    teams = game.find_all("div", "nbaModTopTeamName")
    awayteam = teams[0].string.upper()
    hometeam = teams[1].string.upper()
    scores = game.find_all("div", "nbaModTopTeamNum")
    awayscore = scores[0].string
    homescore = scores[1].string
    if "Recap" in game['class']:
      period = "F"
      time = ""
    elif "Live" in game['class']:
      if game.find("div", "nbaLiveStatTxSm").string == "HALFTIME":
        period = "2"
        time = "00:00"
      else:
        period = re.search(r'(\d)', game.find("div", "nbaLiveStatTxSm").string).group()
        time = re.search(r'(\d*:\d\d)', game.find("div", "nbaLiveStatTxSm").string).group()
    elif "LiveOT" in game['class']:
      period = "0"
      time = re.search(r'(\d*:\d\d)', game.find("div", "nbaLiveStatTxSm").string).group()
    elif "Pre" in game['class']:
      period = ""
      time = game.find("h2", "nbaPreStatTx").string
    gameid = re.sub(r'nbaGL', '', game['id'])
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  with scoreslock:
    scoredata = scores
  return

def get_nfl_score(date):
  global scoredata, nfl_season, nfl_week
  scores = []
  if date == date.today():
    raw = urlopen("http://www.nfl.com/liveupdate/scorestrip/scorestrip.json").read()
    raw = re.sub(r',,', ',"",', raw)
    raw = re.sub(r',,', ',"",', raw)
    games = json.loads(raw)['ss']
    for game in games:
      awayteam = game[4]
      hometeam = game[6]
      awayscore = game[5]
      homescore = game[7]
      if game[2] == "Final":
        period = "F"
        time = ""
      elif game[2] == "Pregame":
        period = ""
        time = re.sub(":", "", game[1])
      elif re.search(r'\d', game[2]) is not None:
        period = re.search(r'(\d)', game[2]).group()
        time = re.search(r'(\d*:\d\d)', game[3]).group()
# Still need halftime, OT (end of qtrs go straight to next qtr)
      gameid = game[10]
      scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
    scores = sorted(scores, key=itemgetter('gameid'))
    nfl_season = games[0][13]
    nfl_week = games[0][12]
    with scoreslock:
      scoredata = scores
    return  
  else:
    url = "http://www.nfl.com/scores/" + nfl_season + "/" + nfl_week
    html = urlopen(url).read()
    soup = BeautifulSoup(html, "html")
    games = soup.find_all(id=re.compile('scorebox-\d'))
    for game in games:
      awayteam = re.sub(r'.*=', '', game.find("div", "away-team").a['href'])
      hometeam = re.sub(r'.*=', '', game.find("div", "home-team").a['href'])
      awayscore = game.find_all("p", "total-score")[0].string
      homescore = game.find_all("p", "total-score")[1].string
      if "ET" in game.find("span", "time-left").string:
        period = ""
        time = re.search(r'(\d*:\d\d)', game.find("span", "time-left").string).group()
      elif "FINAL" in game.find("span", "time-left").string:
        period = "F"
        time = ""
      gameid = re.sub("scorebox-", "", game['id'])
      scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
    scores = sorted(scores, key=itemgetter('gameid'))
    return

def update_scores():
  global sport
  if sport == "nhl":
    get_nhl_scores(date)
  elif sport == "nba":
    get_nba_scores(date)

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
    if currentgame > (len(scoredata) - 1)
      currentgame = 0
  elif currentgame == "left":
    currentgame -= 1
    if currentgame < 0:
      currentgame = (len(scoredata) -1)
  display_trigger.set()

def change_day(event):
  global date, nfl_week
  if event == "up":
    date = date + datetime.timedelta(days=1)
    if sport == "nfl":
      if nfl_week[:3] == "PRE":
        if int(nfl_week[3:]) > 0:
          nfl_week = "PRE" + str(int(nfl_week[3:]0 - 1)
      else:
        if int(nfl_week[3:]) < 1:
          nfl_week = "REG" + str(int(nfl_week[3:]0 - 1)
        elif int(nfl_week[3:]) == 1:
          nfl_week = "PRE4"
  elif event == "down":
    date = date - datetime.timedelta(days=1)
    if sport == "nfl":
      if nfl_week[:3] == "PRE":
        if int(nfl_week[3:]) < 4:
          nfl_week = "PRE" + str(int(nfl_week[3:]0 + 1)
        elif int(nfl_week[3:]) == 4:
          nfl_week = "REG1"
      else:
        if int(nfl_week[3:]) < 17:
          nfl_week = "REG" + str(int(nfl_week[3:]0 + 1)
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
  source = threading.Thread(target=source_daemon)
  source.daemon = True
  source.start()
  test_display()

main()

