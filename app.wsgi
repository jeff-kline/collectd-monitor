# -*- Python -*-
# vim: set syntax=python:
import colorsys
import json
import glob
import os
import rrdtool
import stat
import tempfile
import time
import urlparse

CODE_OK = "200 OK"
CODE_ERROR = "500 Internal Server Error"


with open("/etc/ldr_monitor.json") as fh:
    config = json.load(fh)

BASE_URL = config["base-url"]

try: PAGE_TITLE = config["page-title"]
except KeyError: PAGE_TITLE = "LDR Monitor Page"

try: IGNORE_AGE = config["ignore-age"]
except KeyError: IGNORE_AGE = 600

# this should be read from BaseDir in /etc/collectd/collectd.conf
BASE_DIR = "/var/lib/collectd/rrd"

SERVER_DIR_l = glob.glob(os.path.join(BASE_DIR, "*"))
SERVER_l = map(os.path.basename, SERVER_DIR_l)
SERVER_d = dict(zip(SERVER_l, SERVER_DIR_l))

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
    return str("""
<a href="%s/index.cgi">The raw data</a>
</body></html>""" % BASE_URL)


def ldrq(server_dir, server, ignore_age=IGNORE_AGE):
    """Attempt to return html node of ldrq if ldrq rrd file is younger
    than ignore_age"""
    try:
        img_src = "%s/graph.cgi?hostname=%s;plugin=ldrq;type=ldrq;begin=-%d" % (BASE_URL, server, ignore_age)
        s = os.stat(os.path.join(server_dir, "ldrq/ldrq.rrd"))
        if ignore_age > time.time() - s[stat.ST_MTIME]:
            return """<img src="%s" alt="ldrq for %s">""" % (img_src, server)
    except OSError: pass

def _get_recent_publish(server_dir, ignore_age=IGNORE_AGE):
    all_files = glob.glob(os.path.join(server_dir, "ldrq/*_publish*.rrd"))
    all_files_stat = [os.stat(f) for f in all_files]
    ret = []
    for f, s in zip(all_files, all_files_stat):
        if ignore_age > time.time() - s[stat.ST_MTIME]:
            ret.append(f)
    return ret

def ldr_publish(server_dir, server, ignore_age=IGNORE_AGE):
    try:
        img_src = "publish_graph?hostname=%s;start=-%d"  % (server, ignore_age)
        if _get_recent_publish(server_dir, ignore_age):
            return """<img src="%s" alt="ldrpublish for %s">""" % (img_src, server)
    except OSError: pass

def publish_graph(environ, start_response):
    publish_graph_d = urlparse.parse_qs(environ["QUERY_STRING"])
    hostname=publish_graph_d["hostname"][0]
    try: start=publish_graph_d["start"][0]
    except: start = '-86400'

    recent = _get_recent_publish(SERVER_d[hostname], ignore_age=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]

    # build the rrd command
    #i for fpath, name in zip(recent, name_l):
    n = len(recent)
    HEX = '0123456789abcdef'
    HEX_d = dict((a+b, HEX.index(a)*16 + HEX.index(b)) for a in HEX for b in HEX)

    def rgb(triplet):
        triplet = triplet.lower()
        return (HEX2[triplet[0:2]], HEX2[triplet[2:4]], HEX2[triplet[4:6]])

    def triplet(rgb):
        return format((rgb[0]<<16)|(rgb[1]<<8)|rgb[2], '06x')

    def triplet_01(rgb):
        return triplet([int(a*256) for a in rgb])

    cw = [triplet_01(colorsys.hls_to_rgb(float(x)/n, 0.5, 0.625)) for x in range(n)]
    
    with tempfile.NamedTemporaryFile() as fh:
        rrdtool_args = [ '--imgformat', 'PNG', '--title', 'Publish rate', 
                         '--start', start, '--end', '-1', '--vertical-label', "pub/min"]
        for c, f, n in zip(cw, recent, name_l):
            rrdtool_args.append('DEF:%s0=%s:pub_per_sec:AVERAGE' % (n, f))
            rrdtool_args.append('CDEF:%s=%s0,60,*' % (n, n))
            rrdtool_args.append('LINE:%s#%s:%s' % (n,''.join(c), n))
        rrdtool.graph(fh.name, *rrdtool_args)
        response_headers = [('Content-type', 'image/png')]
        start_response(CODE_OK, response_headers)
        return [fh.read()]

def application(environ, start_response):
    """Derived from the simplest possible application object"""

    try:
	# dispatch the special cases if necessary
        if "publish_graph" in environ["REQUEST_URI"]:
	    return publish_graph(environ, start_response)

        publish_graph_d = urlparse.parse_qs(environ["QUERY_STRING"])
        try: start=abs(int(publish_graph_d["start"][0]))
        except: start = 86400
        ret = [html_start()]
        for server, server_dir in SERVER_d.iteritems():
            server_node_start = "<div><div>%s</div>" % server
            server_node_end = "</div>"
            server_node = []
            server_node.append(ldrq(server_dir, server, ignore_age=start))
            server_node.append(ldr_publish(server_dir, server, ignore_age=start))
            server_node = map(str, [s or '' for s in server_node])
            
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
        return ["Internal server error:\n  ", str(e)]

if __name__=="__main__":
    def start_response(foo, bar):
        print foo, bar

    print application(os.environ, start_response)

