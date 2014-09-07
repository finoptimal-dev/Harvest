import BaseHTTPServer
import requests
import json
import secrets
import harvest
import time
import datetime
from dateutil import parser

class OAuthHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  callback_url = "/harvest_callback"
  base_url = "http://localhost:3000"
  full_callback_url = "%s/harvest_callback" % base_url
  harvest_host = "https://company123456.harvestapp.com" #todo - to secrets?
  link = "%s/oauth2/authorize?client_id=%s&redirect_uri=%s&state=optional-csrf-token&response_type=code" % (harvest_host, secrets.client_id, full_callback_url) 
  refresh_url = "/refresh"
  my_info_url = "/my_info"
  test_url = "/test"
  last_refresh_time_key = "last_refresh_time"
  value_key = "value"

  def do_GET(self):
    if self.path == "/":
      self.generate_page("<a href='%s'>Connect / ReConnect</a>" % self.link)
    elif self.callback_url in self.path:
      json_data = self.get_new_access_token()
      TokensManager.write_tokens({
        "access_token": {
          self.value_key: json_data["access_token"],
          self.last_refresh_time_key: datetime.datetime.now().isoformat()
        },
        "refresh_token": {
          self.value_key: json_data["refresh_token"],
          self.last_refresh_time_key: datetime.datetime.now().isoformat()
        }
      })
      
      self.generate_page("Now you're connected to Harvest. Go to <a href='/my_info'>My info</a> or <a href='/test'>Test</a>")

    elif self.refresh_url in self.path:
      
      print "****** refreshing access token...." #todo

      json_data = TokensManager.refresh_access_token()
      old_json_file_data = TokensManager.get_tokens()
      TokensManager.write_tokens({
        "access_token": {
          self.value_key: json_data["access_token"],
          self.last_refresh_time_key: datetime.datetime.now().isoformat()
        },
        "refresh_token": {
          self.value_key: json_data["refresh_token"],
          self.last_refresh_time_key: old_json_file_data["refresh_token"][self.last_refresh_time_key]
        }
      })

      msg = "The access token has been refreshed."
      print msg
      self.generate_page(msg)      

    elif self.my_info_url in self.path:
      self.my_info()
    elif self.test_url in self.path:
      self._test()
    else:
      self.send_response(404)
      self.end_headers()
      self.wfile.write("<html><head><title>Harvest API OAuth2 client</title></head><body>404 <br /> %s</body></html>" % self.path)
  

    
  def get_new_access_token(self):
    code_param = "code="
    left_index = self.path.index(code_param)
    right_index = self.path.index("&")
    code = self.path[left_index + len(code_param):right_index]
    body = "code=%s&client_id=%s&client_secret=%s&redirect_uri=%s&grant_type=authorization_code" % (code, secrets.client_id, secrets.client_secret, self.full_callback_url)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    return json.loads(data.content)

  def my_info(self):
    headers = {"Accept": "application/json"}
    data_raw = requests.get("https://api.harvestapp.com/account/who_am_i?access_token=" + TokensManager.get_tokens()["access_token"]["value"], headers=headers).content
    data = json.loads(data_raw)
    res = "<p>Hello! Your Harvest company is called <strong>%s</strong></p> \
                      <p>You are <strong>%s %s</strong></p> \
                      <hr> \
                      <p><a href='/refresh'>Refresh the token</a></p>" \
                      % (data["company"]["name"], data["user"]["first_name"], data["user"]["last_name"])
    
    self.generate_page(res)

  def generate_page(self, html_code):
    self.send_response(200)
    self.end_headers()
    self.wfile.write("<html><head><title>Harvest API OAuth2 client</title></head><body>%s</body></html>" % html_code)

  def _test(self):
    h = harvest.Harvest("https://api.harvestapp.com", TokensManager.get_tokens()["access_token"]["value"])
    for p in h.projects():
      print p

    for u in h.users():
      print u
      date1 = datetime.datetime(2013, 01, 01)
      date2 = datetime.datetime(2014, 10, 10)
      for e in u.entries(date1, date2):
        print e

    self.generate_page("Test page")

class TokensManager():
  tokens_file_name = "tokens.json"
  access_token_refresh_time = 18    #in hours
  refresh_token_refresh_time = 720  #in hours, 30 days
  last_refresh_token_time_key = "last_refresh_time"
  seconds_per_hours = 3600

  @staticmethod
  def is_access_token_fresh():
    tokens = TokensManager.get_tokens()
    last_rd = parser.parse(tokens["access_token"][TokensManager.last_refresh_token_time_key])

    print "*** is_access_token_fresh:"
    last_rd_diff = datetime.datetime.now() - last_rd
    res = last_rd_diff.total_seconds() / TokensManager.seconds_per_hours
    print "diff hours %s " % res
    #todo refactor
    return res < TokensManager.access_token_refresh_time

  @staticmethod
  def refresh_access_token_by_demand():
    a = TokensManager.is_access_token_fresh()
    print "***** TokensManager -> TokensManager.is_access_token_fresh() -> " + str(a)
    if not (TokensManager.is_access_token_fresh()):
      print "**** refreshing access token..."
      TokensManager.refresh_access_token()  
  
  @staticmethod
  def refresh_access_token():
    #todo
    json_data = TokensManager.refresh_access_token2()
    old_json_file_data = TokensManager.get_tokens()
    TokensManager.write_tokens({
      "access_token": {
        "value": json_data["access_token"],
        "last_refresh_time": datetime.datetime.now().isoformat()
      },
      "refresh_token": {
        "value": json_data["refresh_token"],
        "last_refresh_time": old_json_file_data["refresh_token"]["last_refresh_time"]
      }
    })

    print "The access token has been refreshed."
  
  @staticmethod
  def refresh_access_token2():
    tokens = TokensManager.get_tokens()

    #todo "value"
    body = "refresh_token=%s&client_id=%s&client_secret=%s&grant_type=refresh_token" % (tokens["refresh_token"]["value"], secrets.client_id, secrets.client_secret)
    headers = {
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept": "application/json"
    }

    resp = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    return json.loads(resp.content)

  @staticmethod
  def is_refresh_token_fresh():
    tokens = TokensManager.get_tokens()
    last_rd = parser.parse(tokens["refresh_token"][TokensManager.last_refresh_token_time_key])
    last_rd_diff = datetime.datetime.now() - last_rd
    res = last_rd_diff.total_seconds() / TokensManager.seconds_per_hours
    return res < TokensManager.refresh_token_refresh_time

  @staticmethod
  def get_tokens():
    with open(TokensManager.tokens_file_name) as json_file:
      res = json.load(json_file)

    return res

  @staticmethod
  def write_tokens(data):
    with open(TokensManager.tokens_file_name, "w") as json_file:
      json.dump(data, json_file)


if __name__ == "__main__":
  from BaseHTTPServer import HTTPServer
  server = HTTPServer(("localhost", 3000), OAuthHandler)
  server.serve_forever()