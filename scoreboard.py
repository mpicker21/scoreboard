import re
from bs4 import BeautifulSoup
from urllib2 import urlopen

def get_nhl_scores():
  html = urlopen("http://www.nhl.com/ice/m_scores.htm").read()    # pull HTML source code
  soup = BeautifulSoup(html, "html")                  # input that source code to Beautiful Soup for parsing
  games = soup.find_all("table", class_="gmDisplay")  # extracts individual games and outputs as a list
  scores = []                                         # create scores list that will be populated with a dictionary for each game
  for game in games:
    sections = game.find_all("td", colspan="1", rowspan="1")	# pulls the table of each game into sections, section 0 = awayteam, 1 = awayscore, 2 = time, 3 = hometeam, 4 = homescore	
    awayteam = sections[0]				# this section extracts the three letter team names, first away, then home, from the links for each team
    awayteam = awayteam.a.get('href')
    awayteam = re.sub(r'.*=', '', awayteam)
    hometeam = sections[3]
    hometeam = hometeam.a.get('href')
    hometeam = re.sub(r'.*=', '', hometeam)
    awayscore = sections[1].string			# simply outputs the text contained in the score cells
    homescore = sections[4].string
    time = sections[2].span.string			# this block assigns the time/period section and cleans it up
    period = ""
    if re.search(r'FINAL', time) is not None:
      period = "F"
      time = ""
    elif re.search(r'ET', time) is not None:
      time = re.search(r'(\d*:\d\d)', time).group()
    elif re.search(r'END', time) is not None:
      period = re.search(r'\s(\d)', time).group(1)
      time = "00:00"
    elif re.search(r'st|nd|rd', time) is not None:
      period = re.search(r'\s(\d)', time).group(1)
      time = re.search(r'(\d\d:\d\d)', time).group()
    else:
      period = "0"
      time = re.search(r'(\d\d:\d\d)', time).group()
    time = re.sub(r':', '', time)
    gameid = sections[2].a.get('href')		# this line pulls the gameid for sorting purposes
    gameid = re.sub(r'.*=', '', gameid)
    # this line populates the scores list with the appropriate groups/variables
    scores.append({"awayteam": awayteam, "awayscore": awayscore, "hometeam": hometeam, "homescore": homescore, "period": period, "time": time, "gameid": gameid})
  scores = sorted(scores, key=itemgetter('gameid'))
  return(scores)                                      # returns the score list as the function output

