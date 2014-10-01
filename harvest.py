import BaseHTTPServer
import requests
import urllib2
from base64 import b64encode
from dateutil.parser import parse as parseDate
from xml.dom.minidom import parseString
import json
import datetime
from dateutil import parser
import os, sys
from optparse import OptionParser

client_secret = None
client_id = None
harvest_host = None
tokens_file_name = None

def get_authorized(c_id, c_secret, tokens_path, h_host):
  """
  Refresh the oauth tokens if necessary, I think....
  """
 
  global client_id
  client_id        = c_id

  global client_secret
  client_secret    = c_secret

  global tokens_file_name
  tokens_file_name = tokens_path

  global harvest_host
  harvest_host     = h_host

  print "Please navigate to localhost:3000 to authorize access to:"
  print h_host
  
  server = BaseHTTPServer.HTTPServer(("localhost", 3000), OAuthHandler)
  server.serve_forever()

def main():
  """
  The command line arguments:
    -s, --client_secret (client "S"ecret)
    -i, --client_id (client "I"d)
    -t, --tokens_file_name ("T"okens file)
    -d, --harvest_host ("D"omain)
    --help

  All the arguments are mandatory except the "help"
  """
  from BaseHTTPServer import HTTPServer

  parse_arguments()
  server = HTTPServer(("localhost", 3000), OAuthHandler)
  server.serve_forever()

def parse_arguments():
  parser = OptionParser()
  parser.add_option("-s", "--client_secret", dest="client_secret", help="client_secret")
  parser.add_option("-i", "--client_id", dest="client_id", help="client_id")
  parser.add_option("-t", "--tokens_file_name", dest="tokens_file_name", help="tokens_file_name")
  parser.add_option("-d", "--harvest_host", dest="harvest_host", help="harvest_host")
  options, args = parser.parse_args()

  global client_secret
  client_secret = options.client_secret
  
  global client_id
  client_id = options.client_id

  global tokens_file_name
  tokens_file_name = options.tokens_file_name

  global harvest_host
  harvest_host = options.harvest_host

class HarvestError(Exception):
  pass

class HarvestConnectionError(HarvestError):
  pass

instance_classes = []
class HarvestItemGetterable(type):
  def __init__(klass, name, bases, attrs):
    super(HarvestItemGetterable,klass).__init__(name, bases, attrs)
    instance_classes.append( klass )


class HarvestItemBase(object):
  def __init__(self, harvest, data):
    self.harvest = harvest
    for key,value in data.items():
      key = key.replace("-","_").replace(" ","_")
      try:
        setattr(self, key, value)
      except AttributeError:
        pass


class User(HarvestItemBase):
  __metaclass__ = HarvestItemGetterable

  base_url = "/people"
  element_name = "user"
  plural_name = "users"

  def __str__(self):
    return u"User: %s %s" % (self.first_name, self.last_name)

  def entries(self,start,end):
    return self.harvest._time_entries( "%s/%d/" % (self.base_url, self.id), start, end )


class Project(HarvestItemBase):
  __metaclass__ = HarvestItemGetterable

  base_url = "/projects"
  element_name = "project"
  plural_name = "projects"

  def __str__(self):
    return "Project: " + self.name

  def entries(self,start,end):
    return self.harvest._time_entries( "%s/%d/" % (self.base_url, self.id), start, end )

  @property
  def client(self):
    return self.harvest.client( self.client_id )

  @property
  def task_assignments(self):
    url = "%s/%d/task_assignments" % (self.base_url, self.id)
    for element in self.harvest._get_element_values( url, "task-assignment" ):
        yield TaskAssignment( self.harvest, element )

  @property
  def user_assignments(self):
    url = "%s/%d/user_assignments" % (self.base_url, self.id)
    for element in self.harvest._get_element_values( url, "user-assignment" ):
      yield UserAssignment( self.harvest, element )


class Client(HarvestItemBase):
  __metaclass__ = HarvestItemGetterable

  base_url = "/clients"
  element_name = "client"
  plural_name = "clients"

  @property
  def contacts(self):
    url = "%s/%d/contacts" % (self.base_url, self.id)
    for element in self.harvest._get_element_values( url, "contact" ):
      yield Contact( self.harvest, element )

  def invoices(self):
    url = "%s?client=%s" % (Invoice.base_url, self.id)
    for element in self.harvest._get_element_values( url, Invoice.element_name ):
      yield Invoice( self.harvest, element )

  def __str__(self):
    return "Client: " + self.name

class Contact(HarvestItemBase):
  __metaclass__ = HarvestItemGetterable

  base_url = "/contacts"
  element_name = "contact"
  plural_name = "contacts"

  def __str__(self):
    return "Contact: %s %s" % (self.first_name, self.last_name)


class Task(HarvestItemBase):
  __metaclass__ = HarvestItemGetterable

  base_url = "/tasks"
  element_name = "task"
  plural_name = "tasks"

  def __str__(self):
    return "Task: " + self.name


class UserAssignment(HarvestItemBase):
  def __str__(self):
    return "user %d for project %d" % (self.user_id, self.project_id)

  @property
  def project(self):
    return self.harvest.project( self.project_id )

  @property
  def user(self):
    return self.harvest.user( self.user_id )

class TaskAssignment(HarvestItemBase):
  def __str__(self):
    return "task %d for project %d" % (self.task_id, self.project_id)

  @property
  def project(self):
    return self.harvest.project( self.project_id )

  @property
  def task(self):
    return self.harvest.task( self.task_id )


class Entry(HarvestItemBase):
  def __str__(self):
    return "%0.02f hours for project %d" % (self.hours, self.project_id)

  @property
  def project(self):
    return self.harvest.project(self.project_id)

  @property
  def task(self):
    return self.harvest.task(self.task_id)


class Invoice(HarvestItemBase):
  __metaclass__ = HarvestItemGetterable

  base_url = "/invoices"
  element_name = "invoice"
  plural_name = "invoices"

  def __str__(self):
    return "invoice %d for client %d" % (self.id, self.client_id)

  @property
  def csv_line_items(self):
    """
    Invoices from lists omit csv-line-items

    """
    if not hasattr(self, "_csv_line_items"):
      url = "%s/%s" % (self.base_url, self.id)
      self._csv_line_items = self.harvest._get_element_values(url, self.element_name).next().get("csv-line-items", "")
    return self._csv_line_items

  @csv_line_items.setter
  def csv_line_items(self, val):
    self._csv_line_items = val

  def line_items(self):
    import csv
    return csv.DictReader(self.csv_line_items.split("\n"))


class Harvest(object):
  def __init__(self, uri, access_token):
    self.access_token = access_token
    self.uri = uri
    self.headers = {
      "Accept": "application/xml",
      "Content-Type":"application/xml"
    }

    # create getters
    for klass in instance_classes:
      self._create_getters( klass )

  def _create_getters(self, klass):
    """
    This method creates both the singular and plural getters for various
    Harvest object classes.

    """
    flag_name = "_got_" + klass.element_name
    cache_name = "_" + klass.element_name

    setattr(self, cache_name, {})
    setattr(self, flag_name, False)
    cache = getattr(self, cache_name)
    def _get_item(id):
      if id in cache:
        return cache[id]
      else:
        url = "%s/%d" % (klass.base_url, id)
        item = self._get_element_values(url, klass.element_name).next()
        item = klass(self, item)
        cache[id] = item
        return item

    setattr(self, klass.element_name, _get_item)

    def _get_items():
      if getattr(self, flag_name):
        for item in cache.values():
          yield item
      else:
        for element in self._get_element_values(klass.base_url, klass.element_name):
          item = klass( self, element )
          cache[ item.id ] = item
          yield item

        setattr(self, flag_name, True)

    setattr(self, klass.plural_name, _get_items)

  def find_user(self, first_name, last_name):
    for person in self.users():
      if first_name.lower() in person.first_name.lower() and last_name.lower() in person.last_name.lower():
        return person

    return None

  def _time_entries(self, root, start, end):
    url = root + "entries?from=%s&to=%s" % (start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
    for element in self._get_element_values(url, "day-entry"):
      yield Entry(self, element)

  def _request(self, url):
    if "?" in url:
      separator = "&"
    else:
      separator = "?"
    
    full_url = self.uri + url + separator + "access_token=" + self.access_token
    request = urllib2.Request(url=full_url, headers=self.headers)
    try:
      # if refresh_token is fresh then the access token can be refreshed 
      # by sending a GET request to a specific url according to the spec of OAuth2
      # but if isn"t fresh then an user must re-authenticate to obtain the new access and refresh tokens
      if TokensManager.is_refresh_token_fresh():
        TokensManager.refresh_access_token_by_demand()
      else:
        raise HarvestError("You must re-authenticate first by going to http://localhost:3000")
              
      r = urllib2.urlopen(request)
      xml = r.read()
      return parseString(xml)
    except urllib2.URLError as e:
      raise HarvestConnectionError(e)

  def _get_element_values(self,url,tagname):
    def get_element(element):
      text = "".join(n.data for n in element.childNodes if n.nodeType == n.TEXT_NODE)
      
      try:
        entry_type = element.getAttribute("type")
        
        if entry_type == "integer":
          try:
            return int(text)
          except ValueError:
            return 0
        
        elif entry_type in ("date", "datetime"):
          return parseDate( text )
        
        elif entry_type == "boolean":
          try:
            return text.strip().lower() in ("true", "1")
          except ValueError:
            return False
        
        elif entry_type == "decimal":
          try:
            return float(text)
          except ValueError:
            return 0.0
        
        else:
          return text
      
      except:
        return text

    xml = self._request(url)
    for entry in xml.getElementsByTagName(tagname):
      value = {}
      for attr in entry.childNodes:
        if attr.nodeType == attr.ELEMENT_NODE:
          tag = attr.tagName
          value[tag] = get_element(attr)

      if value:
        yield value


class OAuthHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  callback_url = "/harvest_callback"
  base_url = "http://localhost:3000"
  full_callback_url = "%s/harvest_callback" % base_url
  link_template = "{harvest_host}/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&state=optional-csrf-token&response_type=code"
  refresh_url = "/refresh"
  my_info_url = "/my_info"
  test_url = "/test"

  def do_GET(self):
    if self.path == "/":
      self.generate_page("<a href='{}'>Connect / ReConnect</a>".format(self.link_template.format(
                          harvest_host=harvest_host, client_id=client_id, redirect_uri=self.full_callback_url
                        )))

    elif self.callback_url in self.path:
      TokensManager.get_new_access_token(self.path, self.full_callback_url)
      self.generate_page("Now you're connected to Harvest. Go to <a href='/my_info'>My info</a> or <a href='/test'>Test</a>")

    elif self.refresh_url in self.path:
      TokensManager.refresh_access_token()
      self.generate_page("The access token has been refreshed.")      

    elif self.my_info_url in self.path:
      self.my_info()

    elif self.test_url in self.path:
      self._test()

    else:
      self.send_response(404)
      self.end_headers()
      self.wfile.write("<html><head><title>Harvest API OAuth2 client</title></head><body>404 <br /> %s</body></html>" % self.path)
  
  def my_info(self):
    data = TokensManager.get_my_info_request()
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
    h = Harvest("https://api.harvestapp.com", TokensManager.get_tokens()["access_token"]["value"])
    for p in h.projects():
      print p

    for u in h.users():
      print u
      date1 = datetime.datetime(2013, 01, 01)
      date2 = datetime.datetime(2014, 10, 10)
      for e in u.entries(date1, date2):
        print e

    self.generate_page("Test page")

class TokensManager(object):
  access_token_refresh_time = 18    #in hours
  refresh_token_refresh_time = 720  #in hours, 30 days
  last_refresh_token_time_key = "last_refresh_time"
  value_key = "value"
  seconds_per_hours = 3600

  @staticmethod
  def is_access_token_fresh():
    tokens = TokensManager.get_tokens()
    last_rd = parser.parse(tokens["access_token"][TokensManager.last_refresh_token_time_key])
    last_rd_diff = datetime.datetime.now() - last_rd
    res = last_rd_diff.total_seconds() / TokensManager.seconds_per_hours
    return res < TokensManager.access_token_refresh_time

  @staticmethod
  def refresh_access_token_by_demand():
    if not (TokensManager.is_access_token_fresh()):
      TokensManager.refresh_access_token()  
  
  @staticmethod
  def refresh_access_token():
    json_data = TokensManager._refresh_access_token_request()
    old_json_file_data = TokensManager.get_tokens()
    TokensManager.write_tokens({
      "access_token": {
        TokensManager.value_key: json_data["access_token"],
        TokensManager.last_refresh_token_time_key: datetime.datetime.now().isoformat()
      },
      "refresh_token": {
        TokensManager.value_key: json_data["refresh_token"],
        TokensManager.last_refresh_token_time_key: old_json_file_data["refresh_token"][TokensManager.last_refresh_token_time_key]
      }
    })

    print "The access token has been refreshed."
  
  @staticmethod
  def _refresh_access_token_request():
    tokens = TokensManager.get_tokens()
    body = "refresh_token=%s&client_id=%s&client_secret=%s&grant_type=refresh_token" % (tokens["refresh_token"][TokensManager.value_key], client_id, client_secret)
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
  def get_my_info_request():
    headers = {"Accept": "application/json"}
    data_raw = requests.get("https://api.harvestapp.com/account/who_am_i?access_token=" + TokensManager.get_tokens()["access_token"]["value"], headers=headers).content
    return json.loads(data_raw)

  @staticmethod
  def get_new_access_token(path, full_callback_url):
    json_data = TokensManager._get_new_access_token_request(path, full_callback_url)
    TokensManager.write_tokens({
      "access_token": {
        TokensManager.value_key: json_data["access_token"],
        TokensManager.last_refresh_token_time_key: datetime.datetime.now().isoformat()
      },
      "refresh_token": {
        TokensManager.value_key: json_data["refresh_token"],
        TokensManager.last_refresh_token_time_key: datetime.datetime.now().isoformat()
      }
    })
  
  @staticmethod
  def _get_new_access_token_request(path, full_callback_url):
    code_param = "code="
    left_index = path.index(code_param)
    right_index = path.index("&")
    code = path[left_index + len(code_param):right_index]
    body = "code=%s&client_id=%s&client_secret=%s&redirect_uri=%s&grant_type=authorization_code" % (code, client_id, client_secret, full_callback_url)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = requests.post("https://api.harvestapp.com/oauth2/token", headers=headers, data=body, verify=False)
    return json.loads(data.content)

  @staticmethod
  def get_tokens():
    with open(tokens_file_name) as json_file:
      res = json.load(json_file)

    return res

  @staticmethod
  def write_tokens(data):
    with open(tokens_file_name, "w") as json_file:
      json.dump(data, json_file)

def get_session(api_creds, token_path, harvest_host_prefix):
  """
  If the token_path exists, (get or) refresh the token (from) there. If not,
   go through the authorization workflow.
  """
  
  global tokens_file_name
  tokens_file_name = token_path

  h_host  = "https://%s.harvestapp.com" % harvest_host_prefix

  if not os.path.exists(token_path):
    # This should give the client_token_path a fresh access token from
    #  scratch, rather than refreshing an existing token.
    get_authorized(api_creds['client_id'],
                   api_creds['client_secret'],
                   token_path,
                   h_host)

  # Refresh the access token if necessary
  TokensManager.refresh_access_token_by_demand()

  # Then...
  access_token = TokensManager.get_tokens()["access_token"]["value"]

  # And finally, the moment we've all been waiting for...
  return Harvest(h_host, access_token)


if __name__ == "__main__":
  main()

#todo - refactor - replace % with "".format()
