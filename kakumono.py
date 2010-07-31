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
  def post(self):
    writ = Writ()

    if users.get_current_user():
      writ.author = users.get_current_user()

    # Save the writ:
    content = self.request.get('content')
    writ.content = content

    contentPieces = self.busticate(content)
    rankedPieces = []
    for i in range(0, len(contentPieces)):
      count = self.getResultCountForSearch(contentPieces[i])
      r = self.getRankFromResultCount(count)
      rankedPieces.append({'rank':r, 'content':contentPieces[i]})

    writ.ranked_content = json.dumps(rankedPieces)
    writ.put()


    # Display results: (back to main page)
    self.redirect('/')

  def getResultCountForSearch(self, searchQuery):
    searchQuery = searchQuery.encode('utf-8')
    quotedSearchQuery = urllib.quote_plus(searchQuery.center(len(searchQuery) + 2, '"'))
    url = 'http://ajax.googleapis.com/ajax/services/search/web?q='
    version = '&v=1.0'
    sizeLimit = '&rsz=1'
    key = '' # '&key=MY-KEY'
    userIP = '' # '&userip=192.168.0.1'

    requestUrl = url + quotedSearchQuery + version + sizeLimit + key + userIP
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
      return "0"

    return results['responseData']['cursor']['estimatedResultCount']

  def busticate(self, content):
    i = int(len(content) / 3)
    return [content[:i], content[i:2*i], content[2*i:]]

  def getRankFromResultCount(self, count):
    rank = "soso"
    if int(count) >= 0:
      rank = "bad"
    if int(count) >= 5:
      rank = "dodgy"
    if int(count) >= 10:
      rank = "soso"
    if int(count) > 100:
      rank = "okay"
    if int(count) > 1000:
      rank = "good"
    return rank



# START APPLICATION:
application = webapp.WSGIApplication(
                               [('/', MainPage),
				('/analyze', Analyzer)],
			       debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()

