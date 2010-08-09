
import wsgiref.handlers
#import os
#import urllib
#import re
#import time

#import datetime

#import lobby
#import gamemodel
#import chat
#import http

#import ajax

from django.utils import simplejson

#from google.appengine.api import users
#from google.appengine.ext import db
from google.appengine.ext import webapp



class KakumonsterHandler(webapp.RequestHandler):
  """Class implementing REST APIs for talking to kakuMonster
  """

  def get(self):
    """ Gets a suggestion from kakuMonster.

        The URL format is:
           GET /kakumonster/<opt_msgid>
           
        Fetches the highest ranked suggestion for the current Writ.

        Response is a Javascript object with 1 attribute:
        {
	  'mistakes': ["the text of the mistake"],
          'maybes': ["the possible fix"],  // string array
        }
    """
    self.response.headers['Content-Type'] = 'text/javascript'

    #Get the Writ - Find a suggestion...

      # Let the lobby know the user is here
      #lobby.in_lobby(user)

      # Build our response and write it out
    response = {}
    #response['mistake'] = self.get_player_list()
    response['mistakes'] = ["what you wrote"]
    response['maybes'] = ["what you shoulda wrote"]
    self.response.out.write(simplejson.dumps(response))


