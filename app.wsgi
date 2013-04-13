# -*- Python -*-
# vim: set syntax=python:
import colorsys
import json
import glob
import os
import re
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

try: DEFAULT_START = config["default-start"]
except KeyError: DEFAULT_START = -86400

try: DEFAULT_END = config["default-end"]
except KeyError: DEFAULT_END = -1

# this should be read from BaseDir in /etc/collectd/collectd.conf
BASE_DIR = "/var/lib/collectd/rrd"

SERVER_DIR_l = glob.glob(os.path.join(BASE_DIR, "*"))
SERVER_l = map(os.path.basename, SERVER_DIR_l)
SERVER_d = dict(zip(SERVER_l, SERVER_DIR_l))

def html_start():
    return str("""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
   "http://www.w3.org/TR/html4/strict.dtd">
<html>
  <head>
  <meta http-equiv="Content-Type" content="text/html;charset=utf-8" >
  <title>%s</title>
  </head>
<body>
<p>
<a href="http://www.ldas-cit.ligo.caltech.edu/lag.html">Dan's Lag page</a>, <a href="%s/index.cgi">The raw data</a>, 
Valid query params: hostname (regexp), start (negative int), end (negative int)</p>
    """ % (PAGE_TITLE, BASE_URL))

def js_start():
    return """<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js" type="text/javascript"></script>
    <script type="text/javascript">
    // refresh each rrdtool image every 100s
    // append ts=${timestamp} to each image url
    $(document).ready(function() {
      setInterval(function() {
        $(".rrdtool").each(function() {
          $(this).attr("src",$(this).attr("src").replace(/ts=.*/, "ts="+new Date().getTime()));
          });
      }, 100000);
    });
    </script>
    """

def w3c_pride():
    return """
  <p>
    <a href="http://validator.w3.org/check?uri=referer"><img
      src="http://www.w3.org/Icons/valid-html401" alt="Valid HTML 4.01 Strict" height="31" width="88"></a>
  </p>"""

def html_end():
    return str("""</body></html>""")


def _get_recent(server_dir, file_l, start):
    all_files_stat = [os.stat(f) for f in file_l]
    ret = []
    for f, s in zip(file_l, all_files_stat):
        if start > time.time() - s[stat.ST_MTIME]:
            ret.append(f)
    ret.sort()
    return ret

def _get_recent_ldrq(server_dir, start=DEFAULT_START):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/ldrq.rrd")), start)

def _get_recent_publish(server_dir, start=DEFAULT_START):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/*_publish*.rrd")), start)

def _get_recent_rate(server_dir, start=DEFAULT_START):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/*_rate*.rrd")), start)

def _get_recent_todo(server_dir, start=DEFAULT_START):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/*_transfer*.rrd")), start)

def _get_recent_lagxfer(server_dir, start=DEFAULT_START):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/*_lagxfer*.rrd")), start)

def _get_recent_ldrq(server_dir, start=DEFAULT_START):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/ldrq.rrd")), start)

def img(img_src, alt):
    return """<td><img src="%s;ts=0" alt="%s" class="rrdtool" style="width:100%%" ></td>""" % (img_src, alt)

def ldrq(server_dir, server, start=DEFAULT_START, end=DEFAULT_END):
    try:
        img_src = "ldrq_graph?hostname=%s;start=%d;end=%d" % (server, start, end)
        if _get_recent_ldrq(server_dir, abs(start)):
            return img(img_src, "ldr queue for %s" % server)
    except OSError: pass

def ldr_publish(server_dir, server, start=DEFAULT_START, end=DEFAULT_END):
    try:
        img_src = "publish_graph?hostname=%s;start=%d;end=%d"  % (server, start, end)
        if _get_recent_publish(server_dir, abs(start)):
            return img(img_src, "publish rate for %s" % server)
    except OSError: pass


def ldr_rate(server_dir, server, start=DEFAULT_START, end=DEFAULT_END):
    try:
       img_src = "rate_graph?hostname=%s;start=%d;end=%d"  % (server, start, end)
       if _get_recent_rate(server_dir, abs(start)):
            return img(img_src, "transfer rate for %s" % server)
    except OSError: pass

def ldr_todo(server_dir, server, start=DEFAULT_START, end=DEFAULT_END):
    try:
        img_src = "todo_graph?hostname=%s;start=%d;end=%d"  % (server, start, end)
        if _get_recent_todo(server_dir, abs(start)):
            return img(img_src, "transfer todo for %s" % server)
    except OSError: pass

def ldr_lagxfer(server_dir, server, start=DEFAULT_START, end=DEFAULT_END):
    try:
        img_src = "lagxfer_graph?hostname=%s;start=%d;end=%d"  % (server, start, end)
        if _get_recent_lagxfer(server_dir, abs(start)):
            return img(img_src, "transfer lag for %s" % server)
    except OSError: pass


def colorwheel(n):
    def hls_to_hex(hls):
        def rgb_to_hex(rgb):
            return format((rgb[0]<<16)|(rgb[1]<<8)|rgb[2], '06x')
        return rgb_to_hex([int(a*256) for a in colorsys.hls_to_rgb(*hls)])

    return [hls_to_hex((float(x)/n, 0.5, 0.625)) for x in range(n)]

def ldrq_graph(environ, start_response):
    hostname, start, end = _parse_qs(environ["QUERY_STRING"])
    recent = _get_recent_ldrq(SERVER_d[hostname], start=abs(int(start))).pop()
    name = os.path.basename(recent).split('-')[-1].split('.')[0]

    # [ds, color, label]
    kcl = [["transfer", "00FF00",      "transfer "],
           ["publish", "0000FF",       "publish  "],
           ["error", "FF0000",         "error    "],
           ["transfer_fail", "EEDD00", "xfer fail"],
           ["publish_fail", "00DDCC",  "pub fail "],
       ]

    with tempfile.NamedTemporaryFile() as fh:
        rrdtool_args = [ '--imgformat', 'PNG', '--title', 'queue', 
                         '--start', start, '--end', end, '--vertical-label', "count",
                         '--logarithmic']
        for key, color, label in kcl:
            rrdtool_args.append('DEF:%s=%s:%s:AVERAGE' % (key, recent, key) )
            rrdtool_args.append('LINE:%s#%s:%s' % (key, color, label) )
            rrdtool_args.append('GPRINT:%s:AVERAGE:  avg\: %%7.2lf' % (key) )
            rrdtool_args.append('GPRINT:%s:MAX:  max\: %%4.0lf' % (key) )
            rrdtool_args.append('GPRINT:%s:LAST: last\: %%4.0lf\\n' % (key) )

        rrdtool.graph(fh.name, *rrdtool_args)
        response_headers = [('Content-type', 'image/png')]
        start_response(CODE_OK, response_headers)
        return [fh.read()]

def _gen_graph(color_file_name_l, start, end, vertical_label, title, ds, logarithmic=False, scale=1, op=""):
    rrdtool_args = [ '--imgformat', 'PNG', '--title', title,
                     '--start', start, '--end', end, '--vertical-label', vertical_label,]
    if logarithmic:
        rrdtool_args.append('--logarithmic')

    with tempfile.NamedTemporaryFile() as fh:
        for c, f, n in color_file_name_l:
            rrdtool_args.append('DEF:%s0=%s:%s:AVERAGE' % (n, f, ds))
            rrdtool_args.append('CDEF:%s=%s0,%f,*%s' % (n, n, scale, op))
            rrdtool_args.append('LINE:%s#%s:%25s' % (n,''.join(c), n[-25:]))
            rrdtool_args.append('GPRINT:%s:AVERAGE:avg\: %%8.2lf' % (n))
            rrdtool_args.append('GPRINT:%s:MAX:max\: %%5.0lf' % (n))
            rrdtool_args.append('GPRINT:%s:LAST:last\: %%5.0lf\\n' % (n))
        rrdtool.graph(fh.name, *rrdtool_args)
        return fh.read()

def _parse_qs(qs):
    qs_d = urlparse.parse_qs(qs)
    try: hostname=qs_d["hostname"][0]
    except: hostname = None
    try: start=qs_d["start"][0]
    except: start = '-86400'
    try: end=qs_d["end"][0]
    except: end = '-1'
    return hostname, start, end

def rate_graph(environ, start_response):
    hostname, start, end = _parse_qs(environ["QUERY_STRING"])
    recent = _get_recent_rate(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]
    img = _gen_graph(zip(colorwheel(len(recent)), recent, name_l), start, end, "MB/s", "Transfer rate", "MBps")
    response_headers = [('Content-type', 'image/png')]
    start_response(CODE_OK, response_headers)
    return [img]


def todo_graph(environ, start_response):
    hostname, start, end = _parse_qs(environ["QUERY_STRING"])
    recent = _get_recent_todo(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]
    img = _gen_graph(zip(colorwheel(len(recent)), recent, name_l), start, end, "count", "TODO", "avail_m_moved", logarithmic=True)
    response_headers = [('Content-type', 'image/png')]
    start_response(CODE_OK, response_headers)
    return [img]


def lagxfer_graph(environ, start_response):
    hostname, start, end = _parse_qs(environ["QUERY_STRING"])
    recent = _get_recent_lagxfer(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]
    img = _gen_graph(zip(colorwheel(len(recent)), recent, name_l), start, end, "Hours", "Lag (modulo 7 days)", "lag", logarithmic=True, scale=1./3600., op=",168,%")
    response_headers = [('Content-type', 'image/png')]

    start_response(CODE_OK, response_headers)
    return [img]

def publish_graph(environ, start_response):
    hostname, start, end = _parse_qs(environ["QUERY_STRING"])
    recent = _get_recent_publish(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]
    img = _gen_graph(zip(colorwheel(len(recent)), recent, name_l), start, end, "pub/min", "Publish rate", "pub_per_sec", scale=60)
    response_headers = [('Content-type', 'image/png')]

    start_response(CODE_OK, response_headers)
    return [img]


def application(environ, start_response):
    """Derived from the simplest possible application object"""

    try:
	# dispatch the special cases
        if "publish_graph" in environ["REQUEST_URI"]:
	    return publish_graph(environ, start_response)
        elif "rate_graph" in environ["REQUEST_URI"]:
	    return rate_graph(environ, start_response)
        elif "todo_graph" in environ["REQUEST_URI"]:
	    return todo_graph(environ, start_response)
        elif "ldrq_graph" in environ["REQUEST_URI"]:
	    return ldrq_graph(environ, start_response)
        elif "lagxfer_graph" in environ["REQUEST_URI"]:
	    return lagxfer_graph(environ, start_response)

        qs_d = urlparse.parse_qs(environ["QUERY_STRING"])
        hostname, start, end = _parse_qs(environ["QUERY_STRING"])
        start, end =int(start), int(end)

        ret = [html_start(), js_start()]

        # build a table, first store columns
        table_cells = []
        for server, server_dir in SERVER_d.iteritems():
            if hostname is not None and not re.search(hostname, server):
                continue
            server_node_start = """<th style="width:400px"><a href="?hostname=%s">%s</a></th>""" % (server, server)
            server_node = []
            server_node.append(ldr_lagxfer(server_dir, server, start=start, end=end))
            server_node.append(ldrq(server_dir, server, start=start, end=end))
            server_node.append(ldr_publish(server_dir, server, start=start, end=end))
            server_node.append(ldr_rate(server_dir, server, start=start, end=end))
            server_node.append(ldr_todo(server_dir, server, start=start, end=end))

            # only add nodes if server_node is not null
            if any(server_node):
                cells = [server_node_start]
                # convert None to empty cells
                cells.extend([s or "<td></td>" for s in server_node])
                table_cells.append(cells)

        # now transpose the columns
        table_html=['<table>']
        for j in range(len(table_cells[0])):
                table_html.append("<tr>")
                for col in table_cells:
                    table_html.append(col[j])
                table_html.append("</tr>")
        table_html.append("</table>")

        ret.extend(table_html)
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

