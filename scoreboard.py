import re, threading
from bs4 import BeautifulSoup
from urllib2 import urlopen
from datetime import date, timedelta

scorestore = threading.Lock()

def get_nhl_scores(date):
  if date.month > 8:
    season = str(date.year) + str(date.year + 1)
  else:
    season = str(date.year - 1) + str(date.year)
  url = "http://www.nhl.com/ice/scores.htm?date=" + date.strftime('%m/%d/%Y') + "&season=" + season
  html = urlopen(url).read()
  soup = BeautifulSoup(html, "html")
  games = soup.find_all("div", "gamebox")
  for game in games:
    awayteam = game.find_all("a", {"rel" : True})[0]['rel']
    hometeam = game.find_all("a", {"rel" : True})[3]['rel']
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
  date = date.today()
  url = 'http://www.nba.com/gameline/' + date.strftime("%Y%m%d") + '/'
  html = urlopen(url).read()    # pull HTML source code
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
  global sport
  if sport == "nhl":
    with scorestore:
      scores = get_nhl_scores()
  elif sport == "nba":
    with scorestore:
      scores = get_nba_scores()
