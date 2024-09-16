=========
Adoptions
=========

.. contents:: Table of Contents

Here comes a (mostly outdated) list of softwares and systems using pyftpdlib.
In case you want to add your software to such list, make a PR or create a
ticket on the bug tracker.
Please help us in keeping such list updated.

Packages
========

Following lists the packages of pyftpdlib from various platforms.

Various Linux Distros
---------------------

pyftpdlib has been packaged for different Linux distros, see `repology.org <https://repology.org/project/python:pyftpdlib/versions>`__.

.. image:: https://repology.org/badge/vertical-allrepos/python:pyftpdlib.svg

FreeBSD
-------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/freebsd.gif?raw=true

A `freshport <http://www.freshports.org/ftp/py-pyftpdlib>`__
is available.

Softwares
=========

Following lists the softwares adopting pyftpdlib.

Google Chromium
---------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/chrome.jpg?raw=true

`Google Chromium <https://www.chromium.org/chromium-projects/>`__, the open
source project behind Google Chrome, uses pyftpdlib for unit tests of the
FTP client included in the browser.

Smartfile
---------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/smartfile.png?raw=true

`Smartfile <https://www.smartfile.com/>`__ is a market leader in FTP and online
file storage that has a robust and easy-to-use web interface. We utilize
pyftpdlib as the underpinnings of our FTP service. Pyftpdlib gives us the
flexibility we require to integrate FTP with the rest of our application.

Pyfilesystem
------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/images/pyfilesystem.svg?raw=true

`Pyfilesystem <https://www.pyfilesystem.org/>`__ is a Python module
that provides a common interface to many types of filesystem, and provides some
powerful features such as exposing filesystems over an internet connection, or
to the native filesystem. It uses pyftpdlib as a backend for testing its FTP
component.

Bazaar
------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/bazaar.jpg?raw=true

`Bazaar <https://code.launchpad.net/bzr>`__ is a distributed version control
system similar to GIT which supports different protocols among which FTP. Same
as Google Chromium, Bazaar uses pyftpdlib as the base FTP server to implement
internal FTP unit tests.

Python for OpenVMS
------------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/openvms.png?raw=true

`OpenVMS <https://vmssoftware.com/>`__ is an
operating system that runs on the `VAX <http://en.wikipedia.org/wiki/VAX>`__
and `Alpha <http://en.wikipedia.org/wiki/DEC*Alpha>`__ computer families,
now owned by Hewlett-Packard.
`vmspython <http://www.vmspython.org/>`__ is a porting of the original cPython
interpreter that runs on OpenVMS platforms.
pyftpdlib became a standard library module installed by default on
every new vmspython installation.

OpenERP
-------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/openerp.jpg?raw=true

`OpenERP <http://openerp.com>`__ is an Open Source enterprise management
software.  It covers and integrates most enterprise needs and processes:
accounting, hr, sales, crm, purchase, stock, production, services management,
project management, marketing campaign, management by affairs. OpenERP
included pyftpdlib as plug in to serve documents via FTP.

Plumi
-----

`Plumi <https://engagemedia.org/projects/plumi/>`__ is a video sharing Content Management System
based on `Plone <https://plone.org/>`__ that enables you to create your own
sophisticated video sharing site.
pyftpdlib has been included in Plumi to allow resumable large video file uploads
into `Zope <https://www.zope.dev/>`__.

put.io FTP connector
--------------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/putio.png?raw=true

`put.io <https://put.io/>`__ is a storage service that fetches media files
remotely and lets you stream them immediately. They wrote a PoC based on
pyftplidb that proxies FTP clients requests to put.io via HTTP. More info can
be found `here <http://mashable.com/2010/08/25/putio/>`__. See
https://github.com/ybrs/putio-ftp-connector.

Rackspace Cloud's FTP
---------------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/rackspace-cloud-hosting.jpg?raw=true

`ftp-cloudfs <http://github.com/chmouel/ftp-cloudfs>`__ is a FTP server acting
as a proxy to `Rackspace Cloud <https://www.rackspace.com/cloud>`__. It
allows you to connect via any FTP client to do upload/download or create
containers.

Far Manager
-----------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/farmanager.png?raw=true

`Far Manager <http://farmanager.com/>`__ is a program for managing files and
archives on Windows. Far Manager included pyftpdlib as a plug-in for making the
current directory accessible through FTP, which is convenient for exchanging
files with virtual machines.

Google Pages FTPd
-----------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/google-pages.gif?raw=true

`gpftpd <http://arkadiusz-wahlig.blogspot.com/2008/04/hosting-files-on-google.html>`__
is a pyftpdlib based FTP server you can connect to using your Google e-mail
account.
It redirects you to all files hosted on your
`Google Pages <http://pages.google.com>`__ account giving you access to
download them and upload new ones.

Peerscape
---------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/peerscape.gif?raw=true

`Peerscape <http://www.peerscape.org/>`__ is an experimental peer-to-peer social
network implemented as an extension to the Firefox web browser. It implements a
kind of serverless read-write web supporting third-party AJAX application
development. Under the hood, your computer stores copies of your data, the data
of your friends and the groups you have joined, and some data about, e.g.,
friends of friends. It also caches copies of other data that you navigate to.
Computers that store the same data establish connections among themselves to
keep it in sync.

feitp-server
------------

An `extra layer <http://code.google.com/p/feitp-server/>`__  on top of
pyftpdlib introducing multi processing capabilities and overall higher
performances.

Symbian Python FTP server
-------------------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/symbianftp.png?raw=true

An FTP server for Symbian OS: http://code.google.com/p/sypftp/

Sierramobilepos
---------------

The goal of this project is to extend Openbravo POS to use Windows Mobile
Professional or Standard devices. It will import the data from Ob POS
(originally in Postgres, later MySql). This data will reside in a database
using sqlite3. Later a program will allow to sync by FTP or using a USB cable
connected to the WinMob device.
`link <http://forge.openbravo.com/plugins/mwiki/index.php/MobilePOS>`__

Faetus
------

`Faetus <http://tomatohater.com/2010/07/15/faetus-v05-released/>`__ is a FTP
server that translates FTP commands into Amazon S3 API calls providing an FTP
interface on top of Amazon S3 storage.

Manent
------

`Manent <https://openhub.net/p/manent>`__ is an algorithmically strong
backup and archival program which can offer remote backup via a
pyftpdlib-based S/FTP server.

Aksy
----

`Aksy <http://walco.n--tree.net/projects/aksy/>`__ is a Python module to
control S5000/S6000, Z4/Z8 and MPC4000 Akai sampler models with System
Exclusive over USB.  Aksy introduced the possibility to mount samplers as web
folders and manage files on the sampler via FTP.

Imgserve
--------

`Imgserve <http://github.com/wuzhe/imgserve/tree/master>`__ is a python
image processing server designed to provide image processing service. It can
utilize modern multicore CPU to achieve higher throughput and possibly better
performance.
It uses pyftpdlib to permit image downloading/uploading through FTP/FTPS.

Shareme
-------

Ever needed to share a directory between two computers? Usually this is done
using NFS, FTP or Samba, which could be a pain to setup when you just want to
move some files around.
`Shareme <http://bbs.archlinux.org/viewtopic.php?id=56623>`__ is a small FTP
server that, without configuration files or manuals to learn, will publish your
directory, and users can download from it and upload files and directory.
Just open a shell and run ``shareme -d ~/incoming/`` ...and that's it!

Zenftp
------

A simple service that bridges an FTP client with zenfolio via SOAP. Start
zenftp.py, providing the name of the target photoset on Zenfolio, and then
connect to localhost with your FTP client.
`link <http://code.irondojo.com/>`__

ftpmaster
---------

A very simple FTP-based content management system (CMS) including an LDAP
authorizer. `link <https://github.com/MarkLIC/ftpmaster>`__

ShareFTP
--------

A program functionally equivalent to Shareme project.
`link <http://git.logfish.net/shareftp.git/>`__

EasyFTPd
--------

An end-user UNIX FTP server with focus on simplicity.  It basically provides a
configuration file interface over pyftpdlib to easily set up an FTP daemon.
`link <http://code.google.com/p/easyftpd/>`__.

Eframe
------

`Eframe <http://code.google.com/p/adqmisc/wiki/eframe>`__ offers Python
support for the BT EFrame 1000 digital photo frame.

Fastersync
----------

A tool to synchronize data between desktop PCs, laptops, USB drives, remote
FTP/SFTP servers, and different online data storages.
`link <http://code.google.com/p/fastersync/>`__

bftpd
-----

A small easy to configure FTP server.
`link <http://bftpd.sourceforge.net/>`__

Web sites using pyftpdlib
=========================

www.bitsontherun.com
--------------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/bitsontherun.png?raw=true

http://www.bitsontherun.com

www.adcast.tv
-------------

.. image:: https://github.com/giampaolo/pyftpdlib/blob/master/docs/images/adcast.png?raw=true

http://www.adcast.tv http://www.adcast.tv

www.netplay.it
--------------

.. image:: http://pyftpdlib.googlecode.com/svn/wiki/images/netplay.jpg

http://netplay.it/
