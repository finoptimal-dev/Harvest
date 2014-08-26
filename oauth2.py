import BaseHTTPServer
import requests
import json
import secrets

BASE_URL = "http://localhost:3000"
CALLBACK_URL = "/harvest_callback"
FULL_CALLBACK_URL = "%s/harvest_callback" % BASE_URL
HARVEST_HOST = "https://company123456.harvestapp.com"
REFRESH_URL = "/refresh"

class OAuthHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  link = "%s/oauth2/authorize?client_id=%s&redirect_uri=%s&state=optional-csrf-token&response_type=code" % (HARVEST_HOST, secrets.CLIENT_ID, FULL_CALLBACK_URL) 
  
  def do_GET(self):
    if self.path == "/":
      self.send_response(200)
      self.end_headers()
      self.wfile.write("<html><head><title>Test1</title></head><body><a href='%s'>Connect</a></body></html>" % self.link)
    elif CALLBACK_URL in self.path:
      self._get_new_token()
    elif REFRESH_URL in self.path:
      self._refresh_token()
    else:
      self.send_response(404)
      self.end_headers()
      self.wfile.write("<html><head><title>Test1</title></head><body>404 THE PATH %s</body></html>" % self.path)
  
  def _refresh_token(self):
    tokens = get_tokens()
    body = "refresh_token=%s&client_id=%s&client_secret=%s&grant_type=refresh_token" % (tokens["refresh_token"], secrets.CLIENT_ID, secrets.CLIENT_SECRET)
    headers = {
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept": "application/json"
    }

    resp = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    data = json.loads(resp.content)
    self.write_tokens({"access_token": data["access_token"], "refresh_token": data["refresh_token"]})
  
  def _get_new_token(self):
    self.send_response(200)
    self.end_headers()
    code_param = "code="
    left_index = self.path.index(code_param)
    right_index = self.path.index("&")
    code = self.path[left_index + len(code_param):right_index]
    self.wfile.write("<html><head><title>Test1</title></head><body>THIS IS CALLBACK URL, code is: %s</body></html>" % code)
    
    #post
    body = "code=%s&client_id=%s&client_secret=%s&redirect_uri=%s&grant_type=authorization_code" % (code, secrets.CLIENT_ID, secrets.CLIENT_SECRET, FULL_CALLBACK_URL)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    print "**** request is: %s" % resp.content
    data = json.loads(resp.content)
    self.write_tokens({"access_token": data["access_token"], "refresh_token": data["refresh_token"]})


  def write_tokens(self, data):
    with open("tokens.json", "w") as json_file:
      json.dump(data, json_file)

  def get_tokens(self):
    #todo
    return {"access_token": "access_token123", "refresh_token": "refresh_token123"}

if __name__ == "__main__":
  from BaseHTTPServer import HTTPServer
  server = HTTPServer(("localhost", 3000), OAuthHandler)
  server.serve_forever()