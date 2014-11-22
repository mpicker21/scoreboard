import re, threading
from bs4 import BeautifulSoup
from urllib2 import urlopen
from datetime import date, timedelta
from operator import itemgetter

global date, dwell_time, sport
date = date.today()
dwell_time = 5
refresh_rate = 60
sport = "nhl"
scoredata = []
scorestore = threading.Lock()
source_trigger = threading.Event()
source_ready = threading.Event()

def get_nhl_scores(date):
  scores = []
  if date.month > 8:
    season = str(date.year) + str(date.year + 1)
  else:
    season = str(date.year - 1) + str(date.year)
  url = "http://www.nhl.com/ice/scores.htm?date=" + date.strftime('%m/%d/%Y') + "&season=" + season
  print url
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
  return(scores)

def get_nba_scores():
  scores = []
  date = date.today()
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
  scores = soreted(scores, key=itemgetter('gameid'))
  return(scores)

def update_scores():
  global sport, scoredata
  if sport == "nhl":
    with scorestore:
      scoredata = get_nhl_scores(date)
  elif sport == "nba":
    with scorestore:
      scoredata = get_nba_scores(date)

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

def change_day(event):
  global date
  if event == "up":
    date = date + datetime.timedelta(days=1)
  elif event == "down":
    date = date - datetime.timedelta(days=1)

def change_speed(event):
  global dwell_time
  if event == "ffwd":
    dwell_time -= 1
  if event == "rew":
    dwell_time += 1

def change_sport(event):
  global sport
  if event == "1":
    sport = "nhl"
  if event == "2":
    sport = "nba"

def test_display():
  global scoredata
  from time import sleep
  source_ready.wait()
  while True:
    print scoredata
    for game in scoredata:
      print "Game: %s" % (game['gameid'])
      print "Time: %s  Period: %s" % (game['time'], game['period'])
      print "Away: %s    %s" % (game['awayteam'], game['awayscore'])
      print "Home: %s    %s" % (game['hometeam'], game['homescore'])
      print ""
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

