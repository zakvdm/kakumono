import logging
import os
from google.appengine.ext.webapp import template

import cgi
import urllib2
import urllib

from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db

from django.utils import simplejson as json

class Writ(db.Model):
  author = db.UserProperty()
  content = db.TextProperty()
  ranked_content = db.TextProperty()
  date = db.DateTimeProperty(auto_now_add=True)

class Chunk(db.Model):
  chunk = db.StringProperty(required=True, multiline=True)
  result_count = db.IntegerProperty()
  date = db.DateTimeProperty(auto_now_add=True)

class MainPage(webapp.RequestHandler):
  def get(self):
    writs_query = Writ.all().order('-date')
    writ = writs_query.get()

    url, url_linktext = self.handleLogin()

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

  def handleLogin(self):
    if users.get_current_user():
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Logout'
    else:
      url = users.create_login_url(self.request.uri)
      url_linktext = 'Login'
    return url, url_linktext



# ANALYZER:
class Analyzer(webapp.RequestHandler):
  minimumSearchStringLength = 2
  largeResultCount = 100000
  fetchResults = {}

  def post(self):
    writ = Writ()

    if users.get_current_user():
      writ.author = users.get_current_user()

    # Save the writ:
    content = self.request.get('content')
    writ.content = content

    # SPLIT INTO MAXSIZE CHUNKS AND DO FIRST PASS FETCHING ASYNCHRONOUSLY
    content = content.encode('utf-8')
    initialPieces = self.maxSizeSplit(content)
    rpcs = []
    for piece in initialPieces:
      isCached, cacheValue = self.checkCache(piece)
      if not isCached:
        rpc = urlfetch.create_rpc()
        rpc.callback = self.createCallback(rpc)
        rpc.chunk = piece
        urlfetch.make_fetch_call(rpc, self.getApiQueryUrl(piece))
        rpcs.append(rpc)

    for rpc in rpcs:
      rpc.wait() # GET ALL THE FETCH RESULTS

    # DONE WITH FIRST PASS (ALL TOP-LEVEL CHUNKS SHOULD NOW BE CACHED...). NOW FOR RECURSIVE SEARCH:
    checkedPieces = self.splitAndCheck(content)
    rankedPieces = []
    for i in range(0, len(checkedPieces)):
      rank = self.getRankFromGoodness(checkedPieces[i][1])
      piece = checkedPieces[i][0]
      rankedPieces.append({'rank':rank, 'content':piece})

    writ.ranked_content = json.dumps(rankedPieces)
    writ.put()

    # Display results: (back to main page)
    self.redirect('/')

  def maxSizeSplit(self, content):
    maxLength = 20
    if len(content) < maxLength:
      return [content]

    left, right = self.splitWithSpaceChecking(content)
    return self.maxSizeSplit(left) + self.maxSizeSplit(right)
    
  def createCallback(self, rpc):
    return lambda: self.handleResult(rpc)

  def handleResult(self, rpc):
    try:
      result = rpc.get_result()
      if result.status_code == 200:
        text = json.loads(result.content)
        self.parseAndCacheApiQueryResult(rpc.chunk, text)
    except urlfetch.DownloadError, e:
      logging.error('YIKES! Asynchronous fetch FAILED!')
      logging.error(e)

  def splitAndCheck(self, piece):
    maxLength = 20
    cutoff = 2

    # SPLIT ON MAXIMUM LENGTH:
    if len(piece) > maxLength:
      left, right = self.splitWithSpaceChecking(piece)
      return self.splitAndCheck(left) + self.splitAndCheck(right)

    # RETURN IF CURRENT NODE IS GOOD ENOUGH:
    results = self.getResultCountForSearch(piece)
    if results > cutoff:
      goodness = self.getGoodness(piece, results)
      return [(piece, goodness)]

    # OKAY, WE NEED TO LOOK AT THE CHILDREN:
    left, right = self.splitWithSpaceChecking(piece)
    leftResults = self.getResultCountForSearch(left)
    rightResults = self.getResultCountForSearch(right)

    if leftResults > cutoff:
      if rightResults > cutoff:
        # BOTH CHILDREN GOOD ENOUGH, PARENT IS THE PROBLEM!
        combinedGoodness = min(self.getGoodness(left, leftResults), self.getGoodness(right, rightResults))
        return [(piece,combinedGoodness)]
      # LEFT GOOD, BUT NEED TO EXPLORE RIGHT:
      leftGoodness = self.getGoodness(left, leftResults)
      return [(left,leftGoodness)] + self.splitAndCheck(right)

    if rightResults > cutoff:
      # RIGHT GOOD, BUT NEED TO EXPLORE LEFT:
      rightGoodness = self.getGoodness(right, rightResults)
      return self.splitAndCheck(left) + [(right,rightGoodness)]

    # NEED TO EXPLORE BOTH CHILDREN:
    return self.splitAndCheck(left) + self.splitAndCheck(right)

  def splitWithSpaceChecking(self, piece):
    # We prefer to split on spaces if we can
    # TODO: Punctuation too?
    halfway = int(len(piece) / 2)
    pieces = piece.split(' ')
    if len(pieces) == 1:
      # No spaces:
      return piece[:halfway], piece[halfway:]
    numberOfPieces = int(len(pieces) / 2)
    return ' '.join(pieces[:numberOfPieces]), ' '.join(pieces[numberOfPieces:])

  def getResultCountForSearch(self, searchQuery):
    # CHECK IF ITS CACHED:
    isCached, cacheValue = self.checkCache(searchQuery.encode('utf-8'))
    if isCached:
      return cacheValue

    requestUrl = self.getApiQueryUrl(searchQuery)

    try:
      request = urllib2.Request(requestUrl, None, {'Referer':self.request.uri})
      response = urllib2.urlopen(request)
      results = json.load(response)
      
    except urllib2.URLError, e:
      logging.error('YIKES!')
      logging.error(results)
      logging.error(e)
      return 0

    return self.parseAndCacheApiQueryResult(searchQuery, results)

  def parseAndCacheApiQueryResult(self, chunk, responseText):
    if len(responseText['responseData']['results']) == 0:
      # No matches
      self.stickInCache(chunk, 0)
      return 0

    ranking = int(responseText['responseData']['cursor']['estimatedResultCount'])

    self.stickInCache(chunk, ranking)

    return ranking

  def getApiQueryUrl(self, searchQuery):
    # USES GOOGLE SEARCH API TO GET NUMBER OF MATCHES FOR THIS searchQuery (quoted)
    searchQuery = searchQuery.encode('utf-8')

    # OTHERWISE MAKE API CALL:
    quotedSearchQuery = urllib.quote_plus(searchQuery.center(len(searchQuery) + 2, '"'))
    url = 'http://ajax.googleapis.com/ajax/services/search/web?q='
    version = '&v=1.0'
    sizeLimit = '&rsz=1'
    key = '&key=ABQIAAAA-5GDQ5g6YGJmHeKGA3_qhBQ6TI5qcCcRxibBuiMD3gySP-Cj9xSswhK8YnmUhjdg16rR1gtbe-UUhA'
    userIP = '&userip=' + self.request.remote_addr

    return url + quotedSearchQuery + version + sizeLimit + key + userIP


  def getGoodness(self, piece, resultCount):
    # This is a heuristic measure of how "good" a piece is (currently based on length and number of search matches)
    return self.getScaledRankFromResultCount(resultCount) * (len(piece) * len(piece)) / 6

  def getScaledRankFromResultCount(self, resultCount):
    scaledRank = 0
    if int(resultCount) >= 20:
      scaledRank = 1
    if int(resultCount) >= 200:
      scaledRank = 2
    if int(resultCount) > 2000:
      scaledRank = 3
    if int(resultCount) > 20000:
      scaledRank = 4
    return scaledRank

  def getRankFromGoodness(self, goodness):
    # FINALLY: Convert "goodness" into something that can be used in the css
    rank = "bad"
    if int(goodness) >= 4:
      rank = "dodgy"
    if int(goodness) >= 8:
      rank = "soso"
    if int(goodness) > 16:
      rank = "okay"
    if int(goodness) > 32:
      rank = "good"
    return rank

  #CACHING:
  def checkCache(self, chunk):
    if len(chunk) < self.minimumSearchStringLength:
      # If the query is small enough, we can just assume it is going to be "correct" (think of a single kanji)
      return True, self.largeResultCount

    # CHECK DB CACHE:
    cachedChunks = db.GqlQuery("SELECT * FROM Chunk WHERE chunk = :1", chunk)
    cachedChunk = cachedChunks.get()
    if cachedChunk is None:
      return False, None
    return True, cachedChunk.result_count

  def stickInCache(self, chunk, resultCount):
    chunk = Chunk(chunk=chunk)
    chunk.result_count = resultCount
    chunk.put()



# APPLICATION BITS:
# Endpoint mappings
application = webapp.WSGIApplication(
                               [('/', MainPage),
				('/analyze', Analyzer)],
			       debug=True)

# Start application
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()

