import BaseHTTPServer
import requests
import json
import secrets
import harvest
import time

BASE_URL = "http://localhost:3000"
CALLBACK_URL = "/harvest_callback"
FULL_CALLBACK_URL = "%s/harvest_callback" % BASE_URL
HARVEST_HOST = "https://company123456.harvestapp.com"
REFRESH_URL = "/refresh"
MY_INFO_URL = "/my_info"

class OAuthHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  link = "%s/oauth2/authorize?client_id=%s&redirect_uri=%s&state=optional-csrf-token&response_type=code" % (HARVEST_HOST, secrets.CLIENT_ID, FULL_CALLBACK_URL) 

  def do_GET(self):
    if self.path == "/":
      self.generate_page("<a href='%s'>Connect / ReConnect</a>" % self.link)
    elif CALLBACK_URL in self.path:
      self.get_new_token()

      ######### test #################
      #########################################################################################################
      
      h = harvest.Harvest("https://api.harvestapp.com", self.get_tokens()["access_token"])
      for p in h.projects():
        print p

      import datetime

      for u in h.users():
        print u
        date1 = datetime.datetime(2013, 01, 01)
        date2 = datetime.datetime(2014, 10, 10)
        for e in u.entries(date1, date2):
          print e

      ########################################################################################################

    elif REFRESH_URL in self.path:
      self.refresh_token()
    elif MY_INFO_URL in self.path:
      self.my_info()
    else:
      self.send_response(404)
      self.end_headers()
      self.wfile.write("<html><head><title>Harvest API OAuth2 client</title></head><body>404 <br /> %s</body></html>" % self.path)
  
  def refresh_token(self):
    tokens = self.get_tokens()
    body = "refresh_token=%s&client_id=%s&client_secret=%s&grant_type=refresh_token" % (tokens["refresh_token"], secrets.CLIENT_ID, secrets.CLIENT_SECRET)
    headers = {
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept": "application/json"
    }

    data = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    json_data = json.loads(data.content)
    self.write_tokens({"access_token": json_data["access_token"], "refresh_token": json_data["refresh_token"]})
    
    self.generate_page("The token has been refreshed.")

  def get_new_token(self):
    code_param = "code="
    left_index = self.path.index(code_param)
    right_index = self.path.index("&")
    code = self.path[left_index + len(code_param):right_index]
    body = "code=%s&client_id=%s&client_secret=%s&redirect_uri=%s&grant_type=authorization_code" % (code, secrets.CLIENT_ID, secrets.CLIENT_SECRET, FULL_CALLBACK_URL)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    self.data = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    json_data = json.loads(self.data.content)
    self.write_tokens({"access_token": json_data["access_token"], "refresh_token": json_data["refresh_token"]})

    self.generate_page("Now you're connected to Harvest. Go to <a href='/my_info'>my info</a>")

  def my_info(self):
    headers = {
      "Accept": "application/json"
    }

    data2 = requests.get("https://api.harvestapp.com/account/who_am_i?access_token=" + self.get_tokens()["access_token"], headers=headers).content
    data = json.loads(data2)
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

  def write_tokens(self, data):
    with open("tokens.json", "w") as json_file:
      json.dump(data, json_file)

  def get_tokens(self):
    with open("tokens.json") as json_file:
      res = json.load(json_file)

    return res

if __name__ == "__main__":
  from BaseHTTPServer import HTTPServer
  server = HTTPServer(("localhost", 3000), OAuthHandler)
  server.serve_forever()