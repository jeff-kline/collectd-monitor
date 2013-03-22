Monitor app
===========

This is a collectd frontend for my personal use. This goal is to be
more useful than collection3 distributed with collectd. It meets that
goal.

Install
-------
Create ``/etc/ldr_monitor.json`` with a single object with key
``base-url``. This typicaly is a url that ends with
``graph.cgi``. Optional fields include ``page-title`` (LDR Monitor
Page), ``ignore-age`` (600).

Copy ``app.wsgi`` to ``/usr/lib/cgi-bin/collectd-monitor``.

Create two files,
``/etc/apache2/mods-available/collectd_monitor.{load,conf}``.  The file
``collectd_monitor.load`` may be empty, the other should look something
like this:

::

  WSGIDaemonProcess collectd_monitor threads=3 user=ldr group=ldr
  WSGIScriptAliasMatch /collectd-monitor.* /usr/lib/cgi-bin/collectd-monitor/app.wsgi
  
  <Directory /usr/lib/cgi-bin/collectd-monitor>
  </Directory>

Then do ``a2enmod collectd_monitor`` and ``sudo invoke-rc.d apache2 restart``

