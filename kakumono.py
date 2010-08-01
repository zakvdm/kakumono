import logging
import os
from google.appengine.ext.webapp import template

import cgi
import urllib2
import urllib

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db

from django.utils import simplejson as json

class Writ(db.Model):
  author = db.UserProperty()
  content = db.TextProperty()
  ranked_content = db.TextProperty()
  date = db.DateTimeProperty(auto_now_add=True)

class MainPage(webapp.RequestHandler):
  def get(self):
    writs_query = Writ.all().order('-date')
    writs = writs_query.fetch(1)


    if len(writs) > 0:
      writ = writs[0]
    else:
      writ = None

    if users.get_current_user():
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Logout'
    else:
      url = users.create_login_url(self.request.uri)
      url_linktext = 'Login'

    pieces = []

    if writ is not None and writ.ranked_content is not None:
      pieces = json.loads(writ.ranked_content)

    template_values = {
	'pieces' : pieces,
	'user' : users.get_current_user(),
	'url': url,
	'url_linktext': url_linktext,
	}

    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))




class Analyzer(webapp.RequestHandler):
  minimumSearchStringLength = 2
  largeResultCount = 100000
  def post(self):
    writ = Writ()

    if users.get_current_user():
      writ.author = users.get_current_user()

    # Save the writ:
    content = self.request.get('content')
    writ.content = content

    checkedPieces = self.splitAndCheck(content)
    logging.warning(checkedPieces)
    rankedPieces = []
    for i in range(0, len(checkedPieces)):
      rank = self.getRankFromGoodness(checkedPieces[i][1])
      piece = checkedPieces[i][0]
      rankedPieces.append({'rank':rank, 'content':piece})

    #contentPieces = self.busticate(content)
    #rankedPieces = []
    #for i in range(0, len(contentPieces)):
      #count = self.getResultCountForSearch(contentPieces[i])
      #r = self.getRankFromResultCount(count)
      #rankedPieces.append({'rank':r, 'content':contentPieces[i]})

    writ.ranked_content = json.dumps(rankedPieces)
    writ.put()


    # Display results: (back to main page)
    self.redirect('/')

  def splitAndCheck(self, piece):
    maxLength = 10
    cutoff = 2

    if len(piece) > maxLength:
      left, right = self.splitWithSpaceChecking(piece)
      return self.splitAndCheck(left) + self.splitAndCheck(right)

    results = self.getResultCountForSearch(piece)
    if results > cutoff:
      goodness = self.getGoodness(piece, results)
      return [(piece, goodness)]
    left, right = self.splitWithSpaceChecking(piece)

    leftResults = self.getResultCountForSearch(left)
    rightResults = self.getResultCountForSearch(right)

    if leftResults > cutoff:
      if rightResults > cutoff:
        combinedGoodness = self.getGoodness(left, leftResults) + self.getGoodness(right, rightResults)
        return [(piece,combinedGoodness)]
      leftGoodness = self.getGoodness(left, leftResults)
      return [(left,leftGoodness)] + self.splitAndCheck(right)

    if rightResults > cutoff:
      rightGoodness = self.getGoodness(right, rightResults)
      return self.splitAndCheck(left) + [(right,rightGoodness)]

    return self.splitAndCheck(left) + self.splitAndCheck(right)

  def splitWithSpaceChecking(self, piece):
    halfway = int(len(piece) / 2)
    pieces = piece.split(' ')
    if len(pieces) == 1:
      # No spaces:
      return piece[:halfway], piece[halfway:]
    x = int(len(pieces) / 2)
    return ' '.join(pieces[:x]), ' '.join(pieces[x:])

  def getRandomRanking(self, piece):
    if len(piece) <= 3:
      return 20
    import random
    num = random.randint(1, 10)
    if num > 7:
      return 20
    return 1
    

  def getResultCountForSearch(self, searchQuery):
    cachedQuery = searchQuery
    searchQuery = searchQuery.encode('utf-8')

    if len(searchQuery) < self.minimumSearchStringLength:
      return self.largeResultCount

    quotedSearchQuery = urllib.quote_plus(searchQuery.center(len(searchQuery) + 2, '"'))
    url = 'http://ajax.googleapis.com/ajax/services/search/web?q='
    version = '&v=1.0'
    sizeLimit = '&rsz=1'
    key = '&key=ABQIAAAA-5GDQ5g6YGJmHeKGA3_qhBQ6TI5qcCcRxibBuiMD3gySP-Cj9xSswhK8YnmUhjdg16rR1gtbe-UUhA'
    userIP = '&userip=' + self.request.remote_addr

    requestUrl = url + quotedSearchQuery + version + sizeLimit + key + userIP
    logging.info(requestUrl)

    try:
      request = urllib2.Request(requestUrl, None, {'Referer':self.request.uri})
      response = urllib2.urlopen(request)
      results = json.load(response)
      #obj = json.loads( result )
      
    except urllib2.URLError, e:
      logging.error('YIKES!')
      logging.error(results)
      logging.error(e)

    if len(results['responseData']['results']) == 0:
      return 0

    
    ranking = int(results['responseData']['cursor']['estimatedResultCount'])
    logging.error('ZAK: Got ranking of: ' + str(ranking) + ' for: ' + cachedQuery)
    return ranking

  def getGoodness(self, piece, resultCount):
    return self.getScaledRankFromResultCount(resultCount) * len(piece) * len(piece)

  def getScaledRankFromResultCount(self, resultCount):
    scaledRank = 0
    if int(resultCount) >= 10:
      scaledRank = 1
    if int(resultCount) >= 100:
      scaledRank = 2
    if int(resultCount) > 1000:
      scaledRank = 3
    if int(resultCount) > 10000:
      scaledRank = 4
    return scaledRank


  def getRankFromGoodness(self, goodness):
    rank = "soso"
    if int(goodness) >= 0:
      rank = "bad"
    if int(goodness) >= 5:
      rank = "dodgy"
    if int(goodness) >= 10:
      rank = "soso"
    if int(goodness) > 50:
      rank = "okay"
    if int(goodness) > 100:
      rank = "good"
    return rank

  def busticate(self, content, maxLength=10):
    # split into pieces based on "words":
    pieces = content.split(' ')

    # split according to maxLength:
    for i in range(0, len(pieces)):
      while len(pieces[i]) > maxLength:
        halfway = int(len(pieces[i]) / 2)
        pieces.insert(i + 1, pieces[i][halfway:])
        pieces[i] = pieces[i][:halfway]

    return pieces

# START APPLICATION:
application = webapp.WSGIApplication(
                               [('/', MainPage),
				('/analyze', Analyzer)],
			       debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()

