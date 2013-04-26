# -*- Python -*-
# vim: set syntax=python:
import base64
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
except KeyError: DEFAULT_START = -86400 * 2 - 1

try: DEFAULT_END = config["default-end"]
except KeyError: DEFAULT_END = -1

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
<body>
""" % PAGE_TITLE

def page_header():
    return """<div id="header">
  <p><a href="" id="back" title="back"> &larr; </a> | 
  <a href="" id="forward" title="forward"> &rarr; </a> | 
  <a href="" id="full_forward" title="full forward"> &raquo; </a> | 
  <a href="" id="zoom_out" title="zoom out"> &odash; </a> | 
  <a href="" id="zoom_in" title="zoom in"> &oplus; </a> | <a href="" id="reset">reset</a> <span id="t_range"></span>
</p>
<p><a href="http://www.ldas-cit.ligo.caltech.edu/lag.html">Dan's Lag page</a> | <a href="%s/index.cgi">The raw data</a>
</p>
</div>
""" % BASE_URL

def css_start():
    return """
    <style media="screen" type="text/css">
    a:visited {
      color: #0000aa;
    }
    a:hover {
      color: #0000ff;
      background: #eeeeff;
    }
    a {
      color: #0000aa;
      text-decoration: none;
    }
    #t_range {
      padding-left: 5em;
    } 
    #header {
    position: relative;
    width: 96%;
    border-width: 1px;
    border-color: #eeeeee;
    border-style: solid;
    background-color: #ffffff;
    padding:0.25em;
    }
    
    #header p:first-of-type {
    display: inline;
    }

    #header p:last-of-type {
    position: absolute;
    top: -0.75em;
    right: 2em;
    }

    </style>"""

def js_start(start, end):
    return """<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js" type="text/javascript"></script>
    <script type="text/javascript">

    // Simple function to calculate time difference between 2 Javascript date objects
    function get_time_difference(earlierDate,laterDate)
    {
           var nTotalDiff = laterDate.getTime() - earlierDate.getTime();
           var oDiff = new Object();
     
           oDiff.days = Math.floor(nTotalDiff/1000/60/60/24);
           nTotalDiff -= oDiff.days*1000*60*60*24;
     
           oDiff.hours = Math.floor(nTotalDiff/1000/60/60);
           nTotalDiff -= oDiff.hours*1000*60*60;
     
           oDiff.minutes = Math.floor(nTotalDiff/1000/60);
           nTotalDiff -= oDiff.minutes*1000*60;
     
           oDiff.seconds = Math.floor(nTotalDiff/1000);
     
           return oDiff;
    }

    $(document).ready(function() {
        // global variables
        var start=%d, end=%d, rrdtool_interval_handle;
        set_t_range_interval(start, end);

        function set_t_range_interval(_start_, _end_) {
          // refresh each rrdtool image every 100s
          if (rrdtool_interval_handle) {
            clearInterval(rrdtool_interval_handle);
          } 
          set_t_range(_start_, _end_);
          rrdtool_interval_handle = setInterval(function() {
                set_t_range(_start_, _end_);
            }, 100000);
        };

        // nav buttons operate on global variables start, end, 
        // rrdtool_interval_handle 
        $("#reset").click(function() {
            // these are set by the server-side script
            start = %d;
            end = %d;
            set_t_range_interval(start, end);
            return false;
        });

        $("#back").click(function() {
            var t_range = Math.floor((end - start)/2);
            start -= t_range;
            end -= t_range;
            set_t_range_interval(start, end);
            return false;
        });

        $("#full_forward").click(function() {
            // forward will move to the last sane value.
            start = - (end - start) - 1;
            end = -1;
            set_t_range_interval(start, end);
            return false;
        });

        $("#forward").click(function() {
            // forward will move to the last sane value.
            var t_range = (end - start)/2;
            start = end >= -t_range ? -2 * t_range - 1 : Math.floor(start + t_range);
            end = end >= -t_range ? -1: Math.floor(end + t_range);
            set_t_range_interval(start, end);
            return false;
        });

        $("#zoom_out").click(function() {
            // terminal (end - start) = 4 * t_range, so it is an integer
            // must ensure end and start are integers
            var t_range = (end - start)/2;
            start = end >= -t_range ? - 4 * t_range - 1 : Math.floor(start - t_range);
            end = end >= -t_range ? -1 : Math.floor(end + t_range);
            set_t_range_interval(start, end);
            return false;
        });

        $("#zoom_in").click(function() {
            var t_range = Math.floor((end - start)/2);
            start += Math.floor(t_range/2);
            end = start + t_range; 
            set_t_range_interval(start, end);
            return false;
        });

        function set_t_range(_start_, _end_) {
          var cur_d = new Date();
          // start and end are relative to now, negative numbers
          var start_d = new Date(cur_d - Math.abs(_start_ * 1000));
          var end_d = new Date(cur_d - Math.abs(_end_ * 1000));
          var td_obj = get_time_difference(start_d, end_d);
          var td_str = td_obj.days + "days " + td_obj.hours + "h " + td_obj.minutes + "m " + td_obj.seconds + "s ";
          $("#t_range").html(td_str + "&mdash; starting " + start_d.toString() );
          $(".rrdtool").each(function() {
            var new_src = $(this).attr("src") + ""
            new_src = new_src.replace(/start=-\d+/, "start=" + _start_);
            new_src = new_src.replace(/end=-\d+/, "end=" + _end_);
            new_src = new_src.replace(/;__cachebuster__=\d+/,"");
            $(this).attr("src", new_src + ";__cachebuster__=" + new Date().getTime());
          });
        };
    });
    </script>
    """ % (start, end, start, end)

def w3c_pride():
    return """
  <p>
    <a href="http://validator.w3.org/check?uri=referer"><img
      src="http://www.w3.org/Icons/valid-html401" alt="Valid HTML 4.01 Strict" height="31" width="88"></a>
  </p>"""

def html_end():
    return """</body></html>"""


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

def _get_recent_publish(server_dir, start=DEFAULT_START, ds_filter=""):
    return _get_recent(server_dir, 
                       [f for f in glob.glob(os.path.join(server_dir, "ldrq/*_publish*.rrd")) 
                       if re.search(re.compile(ds_filter), f)], start)

def _get_recent_rate(server_dir, start=DEFAULT_START, ds_filter=""):
    return _get_recent(server_dir, 
                       [f for f in glob.glob(os.path.join(server_dir, "ldrq/*_rate*.rrd")) 
                       if re.search(re.compile(ds_filter), f)], start)

def _get_recent_todo(server_dir, start=DEFAULT_START, ds_filter=""):
    return _get_recent(server_dir, 
                       [f for f in glob.glob(os.path.join(server_dir, "ldrq/*_transfer*.rrd")) 
                       if re.search(re.compile(ds_filter), f)], start)

def _get_recent_lagxfer(server_dir, start=DEFAULT_START, ds_filter=""):
    return _get_recent(server_dir, 
                       [f for f in glob.glob(os.path.join(server_dir, "ldrq/*_lagxfer*.rrd")) 
                       if re.search(re.compile(ds_filter), f)], start)

def _get_recent_lagpub(server_dir, start=DEFAULT_START, ds_filter=""):
    return _get_recent(server_dir, 
                       [f for f in glob.glob(os.path.join(server_dir, "ldrq/*_lagpub*.rrd")) 
                       if re.search(re.compile(ds_filter), f)], start)

def _get_recent_ldrq(server_dir, start=DEFAULT_START, ds_filter=""):
    return _get_recent(server_dir, 
	glob.glob(os.path.join(server_dir, "ldrq/ldrq.rrd")), start)

def img(img_src, alt):
    return """<td><img src="%s" alt="%s" class="rrdtool" style="width:400px;height:220px;"></td>""" % (img_src, alt)

def ldrq(server_dir, server, start=DEFAULT_START, end=DEFAULT_END):
    try:
        img_src = "ldrq_graph?hostname=%s;start=%d;end=%d" % (server, start, end)
        if _get_recent_ldrq(server_dir, abs(start)):
            return img(img_src, "ldr queue for %s" % server)
    except OSError: pass

def ldr_publish(server_dir, server, start=DEFAULT_START, end=DEFAULT_END, ds_filter=""):
    try:
        img_src = "publish_graph?hostname=%s;start=%d;end=%d;ds_filter=%s"  % (server, start, end, ds_filter)
        if _get_recent_publish(server_dir, abs(start), ds_filter):
            return img(img_src, "publish rate for %s" % server)
    except OSError: pass


def ldr_rate(server_dir, server, start=DEFAULT_START, end=DEFAULT_END, ds_filter=""):
    try:
       img_src = "rate_graph?hostname=%s;start=%d;end=%d;ds_filter=%s"  % (server, start, end, ds_filter)
       if _get_recent_rate(server_dir, abs(start), ds_filter):
            return img(img_src, "transfer rate for %s" % server)
    except OSError: pass

def ldr_todo(server_dir, server, start=DEFAULT_START, end=DEFAULT_END, ds_filter=""):
    try:
        img_src = "todo_graph?hostname=%s;start=%d;end=%d;ds_filter=%s"  % (server, start, end, ds_filter)
        if _get_recent_todo(server_dir, abs(start), ds_filter):
            return img(img_src, "transfer todo for %s" % server)
    except OSError: pass

def ldr_lagpub(server_dir, server, start=DEFAULT_START, end=DEFAULT_END, ds_filter=""):
    try:
        img_src = "lagpub_graph?hostname=%s;start=%d;end=%d;ds_filter=%s"  % (server, start, end, ds_filter)
        if _get_recent_lagpub(server_dir, abs(start), ds_filter):
            return img(img_src, "publish lag for %s" % server)
    except OSError: pass


def ldr_lagxfer(server_dir, server, start=DEFAULT_START, end=DEFAULT_END, ds_filter=""):
    try:
        img_src = "lagxfer_graph?hostname=%s;start=%d;end=%d;ds_filter=%s"  % (server, start, end, ds_filter)
        if _get_recent_lagxfer(server_dir, abs(start), ds_filter):
            return img(img_src, "transfer lag for %s" % server)
    except OSError: pass


def colorwheel(n):
    def hls_to_hex(hls):
        def rgb_to_hex(rgb):
            return format((rgb[0]<<16)|(rgb[1]<<8)|rgb[2], '06x')
        return rgb_to_hex([int(a*256) for a in colorsys.hls_to_rgb(*hls)])

    return [hls_to_hex((float(x)/n, 0.5, 0.625)) for x in range(n)]

def ldrq_graph(environ, start_response):
    hostname, start, end, ds_filter = _parse_qs(environ["QUERY_STRING"])
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

def _blank_png():
    # this is a blank 1x1 png
    return base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAAApJREFUCNdjYAAAAAIAAeIhvDMAAAAASUVORK5CYII=')

def _gen_graph(recent, name_l, start, end, vertical_label, title, ds, logarithmic=False, scale=1, op=""):
    rrdtool_args = [ '--imgformat', 'PNG', '--title', title,
                     '--start', start, '--end', end, '--vertical-label', vertical_label,]

    if logarithmic: rrdtool_args.append('--logarithmic')
    if not recent: 
        return _blank_png()
    
    color_file_name_l = zip(colorwheel(len(recent)), recent, name_l)
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
    except: start = "%d" % DEFAULT_START
    try: end=qs_d["end"][0]
    except: end = "%d" % DEFAULT_END
    try: ds_filter=qs_d["ds_filter"][0]
    except: ds_filter = ""
    return hostname, start, end, ds_filter

def _graph_(environ, start_response, fcn):
    hostname, start, end, ds_filter = _parse_qs(environ["QUERY_STRING"])
    _ds_filter = re.compile(ds_filter)
    recent = fcn(SERVER_d[hostname], start=abs(int(start)))
    name_l = [os.path.basename(f).split('-')[-1].split('.')[0] for f in recent if _ds_filter.search(f)]
    recent = [f for f in recent if _ds_filter.search(f)]
    return recent, name_l, start, end

def rate_graph(environ, start_response):
    recent, name_l, start, end = _graph_(environ, start_response, _get_recent_rate)
    img = _gen_graph(recent, name_l, start, end, "MB/s", "Transfer rate", "MBps")
    response_headers = [('Content-type', 'image/png')]
    start_response(CODE_OK, response_headers)
    return [img]


def todo_graph(environ, start_response):
    recent, name_l, start, end = _graph_(environ, start_response, _get_recent_todo)
    img = _gen_graph(recent, name_l, start, end, "count", "Transfer todo", "avail_m_moved", logarithmic=True)
    response_headers = [('Content-type', 'image/png')]
    start_response(CODE_OK, response_headers)
    return [img]


def lagpub_graph(environ, start_response):
    recent, name_l, start, end = _graph_(environ, start_response, _get_recent_lagpub)
    img = _gen_graph(recent, name_l, start, end, "Hours", "Publish Lag (modulo 7 days)", "lag", logarithmic=True, scale=1./3600., op=",168,%")
    response_headers = [('Content-type', 'image/png')]
    start_response(CODE_OK, response_headers)
    return [img]

def lagxfer_graph(environ, start_response):
    recent, name_l, start, end = _graph_(environ, start_response, _get_recent_lagxfer)
    img = _gen_graph(recent, name_l, start, end, "Hours", "Transfer Lag (modulo 7 days)", "lag", logarithmic=True, scale=1./3600., op=",168,%")
    response_headers = [('Content-type', 'image/png')]
    start_response(CODE_OK, response_headers)
    return [img]

def publish_graph(environ, start_response):
    recent, name_l, start, end = _graph_(environ, start_response, _get_recent_publish)
    img = _gen_graph(recent, name_l, start, end, "pub/min", "Publish rate", "pub_per_sec", scale=60)
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
        elif "lagpub_graph" in environ["REQUEST_URI"]:
	    return lagpub_graph(environ, start_response)


        qs_d = urlparse.parse_qs(environ["QUERY_STRING"])
        hostname, start, end, ds_filter = _parse_qs(environ["QUERY_STRING"])
        start, end =int(start), int(end)

        ret = [html_start(), css_start(), js_start(start, end), page_header()]

        # build a table, first store columns
        table_cells = []
        for server, server_dir in SERVER_d.iteritems():
            if hostname is not None and not re.search(hostname, server):
                continue
            server_node_start = """<th style="width:400px"><a href="?hostname=%s;ds_filter=%s">%s</a></th>""" % (server, ds_filter, server)
            server_node = []
            server_node.append(ldr_lagxfer(server_dir, server, start=start, end=end, ds_filter=ds_filter))
            server_node.append(ldr_lagpub(server_dir, server, start=start, end=end, ds_filter=ds_filter))
            server_node.append(ldrq(server_dir, server, start=start, end=end))
            server_node.append(ldr_publish(server_dir, server, start=start, end=end, ds_filter=ds_filter))
            server_node.append(ldr_rate(server_dir, server, start=start, end=end, ds_filter=ds_filter))
            server_node.append(ldr_todo(server_dir, server, start=start, end=end, ds_filter=ds_filter))

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
        return [str(r) for r in ret]
    except Exception as e:
        response_headers = [('Content-type', 'text/plain')]
        start_response(CODE_ERROR, response_headers)
        return ["Internal server error:\n  ", str(e)]

if __name__=="__main__":
    def start_response(foo, bar):
        print foo, bar

    print application(os.environ, start_response)

