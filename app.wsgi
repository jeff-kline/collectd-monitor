# -*- Python -*-
import json
import glob
import os
import stat
import time

CODE_OK = "200 OK"
CODE_ERROR = "500 Internal Server Error"


with open("/etc/ldr_monitor.json") as fh:
    config = json.load(fh)

BASE_URL = config["base-url"]

try: PAGE_TITLE = config["page-title"]
except KeyError: PAGE_TITLE = "LDR MOnitor Page"

try: IGNORE_AGE = config["ignore-age"]
except KeyError: 600

# this should be read from BaseDir in /etc/collectd/collectd.conf
BASE_DIR = "/var/lib/collectd/rrd"

SERVER_DIR_l = glob.glob(os.path.join(BASE_DIR, "*"))
SERVER_l = map(os.path.basename, SERVER_DIR_l)

def html_start():
    return """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
   "http://www.w3.org/TR/html4/strict.dtd">
<html>
  <head>
  <meta http-equiv="Content-Type" content="text/html;charset=utf-8" >
  <title>%s</title>
  </head>
<body>""" % PAGE_TITLE


def w3c_pride():
    return """
  <p>
    <a href="http://validator.w3.org/check?uri=referer"><img
      src="http://www.w3.org/Icons/valid-html401" alt="Valid HTML 4.01 Strict" height="31" width="88"></a>
  </p>"""


def html_end():
    return "</body></html>"


def ldrq(server_dir, server, ignore_age=IGNORE_AGE):
    """Attempt to return html node of ldrq if ldrq rrd file is younger
    than ignore_age"""
    try:
        img_src = "%s?hostname=%s;plugin=ldrq;type=ldrq;begin=-86400" % (BASE_URL, server)
        s = os.stat(os.path.join(server_dir, "ldrq/ldrq.rrd"))
        if ignore_age > time.time() - s[stat.ST_MTIME]:
            return """<img src="%s" alt="ldrq for %s">""" % (img_src, server)
        
            return str(time.time() - s[stat.ST_MTIME])
    except OSError: pass


def application(environ, start_response):
    """Derived from the simplest possible application object"""

    try:
        ret = [html_start()]
        for server_dir, server in zip(SERVER_DIR_l, SERVER_l):
            server_node_start = "<div><div>%s</div>" % server
            server_node_end = "</div>"
            server_node = []
            server_node.append(ldrq(server_dir, server))
            server_node.append(ldr_publish(server_dir, server))
            
            # only add nodes if server_node is not null
            if any(server_node):
                ret.append(server_node_start)
                ret.extend(server_node)
                ret.append(server_node_end)
            
        ret.append(w3c_pride())
        ret.append(html_end())
        response_headers = [('Content-type', 'text/html')]
        start_response(CODE_OK, response_headers)
        return ret
    except Exception as e:
        response_headers = [('Content-type', 'text/plain')]
        start_response(CODE_ERROR, response_headers)
        print e
        return ["Internal server error"]

if __name__=="__main__":
    def start_response(foo, bar):
        print foo, bar

    print application(os.environ, start_response)

