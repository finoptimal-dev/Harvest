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
      self.send_response(200)
      self.end_headers()
      self.wfile.write("<html><head><title>Test1</title></head><body><a href='%s'>Connect</a></body></html>" % self.link)
    elif CALLBACK_URL in self.path:
      self.get_new_token()

      #example
      # time.sleep(17)
      
      from datetime import datetime, timedelta
      import time
      
      h = harvest.Harvest("https://api.harvestapp.com", self.get_tokens()["access_token"])
      while True:
        total = 0
        dose = 0

        start = datetime.today().replace(hour=0, minute=0, second=0)
        end = start + timedelta(1)
        for user in h.users():
          for entry in user.entries(start, end):
            total += entry.hours

        text = '%0.02f' % total
        print text

    elif REFRESH_URL in self.path:
      self.refresh_token()
    elif MY_INFO_URL in self.path:
      self.my_info()
    else:
      self.send_response(404)
      self.end_headers()
      self.wfile.write("<html><head><title>Test1</title></head><body>404 THE PATH %s</body></html>" % self.path)
  
  def refresh_token(self):
    tokens = get_tokens()
    body = "refresh_token=%s&client_id=%s&client_secret=%s&grant_type=refresh_token" % (tokens["refresh_token"], secrets.CLIENT_ID, secrets.CLIENT_SECRET)
    headers = {
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept": "application/json"
    }

    self.data = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    json_data = json.loads(self.data.content)
    self.write_tokens({"access_token": json_data["access_token"], "refresh_token": json_data["refresh_token"]})
  
  def get_new_token(self):
    code_param = "code="
    left_index = self.path.index(code_param)
    right_index = self.path.index("&")
    code = self.path[left_index + len(code_param):right_index]
    self.send_response(200)
    self.end_headers()
    self.wfile.write("<html><head><title>Test1</title></head><body>THIS IS CALLBACK URL, code is: %s</body></html>" % code)

    body = "code=%s&client_id=%s&client_secret=%s&redirect_uri=%s&grant_type=authorization_code" % (code, secrets.CLIENT_ID, secrets.CLIENT_SECRET, FULL_CALLBACK_URL)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    self.data = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    json_data = json.loads(self.data.content)
    self.write_tokens({"access_token": json_data["access_token"], "refresh_token": json_data["refresh_token"]})

  def my_info(self):
    headers = {
      "Accept": "application/json"
    }

    data2 = requests.get("https://api.harvestapp.com/account/who_am_i?access_token=" + self.get_tokens()["access_token"], headers=headers).content
    data = json.loads(data2)
    self.send_response(200)
    self.end_headers()
    self.wfile.write("<html><head><title>Test1</title></head><body> \
                      <p>Hello! Your Harvest company is called <strong>%s</strong></p> \
                      <p>You are <strong>%s %s</strong></p> \
                      <p>This is your avatar: <br /><img src='%s' /></p> \
                      <hr> \
                      <p><a href='/refresh'>Refresh the token</a> or <a href='/'>go back to the main page</a></p> \
                      </body></html>" \
                      % (data["company"]["name"], data["user"]["first_name"], data["user"]["last_name"], data["user"]["avatar_url"]))

  def generate_page(self, html_code):
    pass

  def response_page(self):
    self.send_response(200)
    self.end_headers()
    if self.data["error"] is None:
      a = "<h2>Response data</h2>\
          <ul>\
            <li>Access token: %s</li>\
            <li>Refresh token: %s</li>\
          </ul>\
          <a href='/authenticated'>See an authenticated call</a>" % (self.data["access_token"], self.data["refresh_token"])
    else:
      a = "<h2>%s: %s</h2>" % (self.data["error"], self.data["error_description"])

    self.wfile.write("<html><head><title>Test1</title></head><body>%s</body></html>" % (a))

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