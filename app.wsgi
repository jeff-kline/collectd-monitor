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

try: DEFAULT_START = config["ignore-age"]
except KeyError: DEFAULT_START = 600

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

def js_start():
    return """<script src="//ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js"></script>"""

def w3c_pride():
    return """
  <p>
    <a href="http://validator.w3.org/check?uri=referer"><img
      src="http://www.w3.org/Icons/valid-html401" alt="Valid HTML 4.01 Strict" height="31" width="88"></a>
  </p>"""

def html_end():
    return str("""<p>
<a href="%s/index.cgi">The raw data</a>
Append "?start=-S" for integer number of seconds S to the URL to adjust the start time of the plots.</p>
</body></html>""" % BASE_URL)


def _get_recent(server_dir, file_l, start):
    all_files_stat = [os.stat(f) for f in file_l]
    ret = []
    for f, s in zip(file_l, all_files_stat):
        if start > time.time() - s[stat.ST_MTIME]:
            ret.append(f)
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

def _get_recent_ldrq(server_dir, start=DEFAULT_START):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/ldrq.rrd")), start)

def img(img_src, alt):
    return """<td><img src="%s" alt="%s" style="width:100%%" ></td>""" % (img_src, alt)

def ldrq(server_dir, server, start=DEFAULT_START):
    try:
        img_src = "ldrq_graph?hostname=%s;start=-%d" % (server, start)
        if _get_recent_ldrq(server_dir, start):
            return img(img_src, "ldr queue for %s" % server)
    except OSError: pass

def ldr_publish(server_dir, server, start=DEFAULT_START):
    try:
        img_src = "publish_graph?hostname=%s;start=-%d"  % (server, start)
        if _get_recent_publish(server_dir, start):
            return img(img_src, "publish rate for %s" % server)
    except OSError: pass


def ldr_rate(server_dir, server, start=DEFAULT_START):
    try:
        img_src = "rate_graph?hostname=%s;start=-%d"  % (server, start)
        if _get_recent_rate(server_dir, start):
            return img(img_src, "transfer rate for %s" % server)
    except OSError: pass

def ldr_todo(server_dir, server, start=DEFAULT_START):
    try:
        img_src = "todo_graph?hostname=%s;start=-%d"  % (server, start)
        if _get_recent_todo(server_dir, start):
            return img(img_src, "transfer todo for %s" % server)
    except OSError: pass


def colorwheel(n):
    def hls_to_hex(hls):
        def rgb_to_hex(rgb):
            return format((rgb[0]<<16)|(rgb[1]<<8)|rgb[2], '06x')
        return rgb_to_hex([int(a*256) for a in colorsys.hls_to_rgb(*hls)])

    return [hls_to_hex((float(x)/n, 0.5, 0.625)) for x in range(n)]

def ldrq_graph(environ, start_response):
    qs_d = urlparse.parse_qs(environ["QUERY_STRING"])
    hostname=qs_d["hostname"][0]
    try: start=qs_d["start"][0]
    except: start = '-86400'

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
                         '--start', start, '--end', '-1', '--vertical-label', "count",
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

def rate_graph(environ, start_response):
    publish_graph_d = urlparse.parse_qs(environ["QUERY_STRING"])
    hostname=publish_graph_d["hostname"][0]
    try: start=publish_graph_d["start"][0]
    except: start = '-86400'

    recent = _get_recent_rate(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]

    with tempfile.NamedTemporaryFile() as fh:
        rrdtool_args = [ '--imgformat', 'PNG', '--title', 'Transfer rate', 
                         '--start', start, '--end', '-1', '--vertical-label', "MB/s"]
        for c, f, n in zip(colorwheel(len(recent)), recent, name_l):
            rrdtool_args.append('DEF:%s0=%s:MBps:AVERAGE' % (n, f))
            rrdtool_args.append('CDEF:%s=%s0,1,*' % (n, n)) # FIXME
            rrdtool_args.append('LINE:%s#%s:%s' % (n,''.join(c), n))
        rrdtool.graph(fh.name, *rrdtool_args)
        response_headers = [('Content-type', 'image/png')]
        start_response(CODE_OK, response_headers)
        return [fh.read()]


def todo_graph(environ, start_response):
    publish_graph_d = urlparse.parse_qs(environ["QUERY_STRING"])
    hostname=publish_graph_d["hostname"][0]
    try: start=publish_graph_d["start"][0]
    except: start = '-86400'

    recent = _get_recent_todo(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]

    with tempfile.NamedTemporaryFile() as fh:
        rrdtool_args = [ '--imgformat', 'PNG', '--title', 'TODO', 
                         '--start', start, '--end', '-1', '--vertical-label', "count",
                         '--logarithmic']
        for c, f, n in zip(colorwheel(len(recent)), recent, name_l):
            rrdtool_args.append('DEF:%s0=%s:avail_m_moved:AVERAGE' % (n, f))
            rrdtool_args.append('CDEF:%s=%s0,1,*' % (n, n)) # FIXME
            rrdtool_args.append('LINE:%s#%s:%s' % (n,''.join(c), n))
        rrdtool.graph(fh.name, *rrdtool_args)
        response_headers = [('Content-type', 'image/png')]
        start_response(CODE_OK, response_headers)
        return [fh.read()]

def publish_graph(environ, start_response):
    publish_graph_d = urlparse.parse_qs(environ["QUERY_STRING"])
    hostname=publish_graph_d["hostname"][0]
    try: start=publish_graph_d["start"][0]
    except: start = '-86400'

    recent = _get_recent_publish(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent]

    with tempfile.NamedTemporaryFile() as fh:
        rrdtool_args = [ '--imgformat', 'PNG', '--title', 'Publish rate', 
                         '--start', start, '--end', '-1', '--vertical-label', "pub/min",

                        ]
        for c, f, n in zip(colorwheel(len(recent)), recent, name_l):
            rrdtool_args.append('DEF:%s0=%s:pub_per_sec:AVERAGE' % (n, f))
            rrdtool_args.append('CDEF:%s=%s0,60,*' % (n, n))
            rrdtool_args.append('LINE:%s#%s:%27s' % (n,''.join(c), n[-27:]))
            rrdtool_args.append('GPRINT:%s:AVERAGE:avg\: %%6.2lf' % (n))
            rrdtool_args.append('GPRINT:%s:MAX:max\: %%4.0lf' % (n))
            rrdtool_args.append('GPRINT:%s:LAST:last\: %%6.2lf\\n' % (n))


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
        elif "rate_graph" in environ["REQUEST_URI"]:
	    return rate_graph(environ, start_response)
        elif "todo_graph" in environ["REQUEST_URI"]:
	    return todo_graph(environ, start_response)
        elif "ldrq_graph" in environ["REQUEST_URI"]:
	    return ldrq_graph(environ, start_response)

        qs_d = urlparse.parse_qs(environ["QUERY_STRING"])
        try: start=abs(int(qs_d["start"][0]))
        except: start = 86400

        ret = [html_start()]
        table_cells = []
        for server, server_dir in SERVER_d.iteritems():
            server_node_start = """<th style="width:25%%">%s</td>""" % server
            server_node_end = ""
            server_node = []
            server_node.append(ldrq(server_dir, server, start=start))
            server_node.append(ldr_publish(server_dir, server, start=start))
            server_node.append(ldr_rate(server_dir, server, start=start))
            server_node.append(ldr_todo(server_dir, server, start=start))
            server_node = map(str, [s or '' for s in server_node])
            
            # only add nodes if server_node is not null
            if any(server_node):
                cells = [server_node_start]
                cells.extend([s or "<td></td>" for s in server_node])
                cells.append(server_node_end)
                table_cells.append(cells)

        table_html=["<table>"]
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

