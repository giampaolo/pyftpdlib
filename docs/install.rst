Install
=======

By using pip:

.. code-block:: sh

    $ pip3 install pyftpdlib

From sources:

.. code-block:: sh

    $ git clone git@github.com:giampaolo/pyftpdlib.git
    $ cd pyftpdlib
    $ python3 setup.py install

You might want to run tests to make sure pyftpdlib works:

.. code-block:: sh

    $ make test
    $ make test-contrib


Additional dependencies
-----------------------

`PyOpenSSL <https://pypi.python.org/pypi/pyOpenSSL>`__, to support
`FTPS <http://pyftpdlib.readthedocs.io/tutorial.html#ftps-ftp-over-tls-ssl-server>`__:

.. code-block:: sh

    $ pip3 install PyOpenSSL

`pywin32 <http://starship.python.net/crew/mhammond/win32/>`__ if you want to
use `WindowsAuthorizer <api.html#pyftpdlib.authorizers.UnixAuthorizer>`__ on
Windows:

.. code-block:: sh

    $ pip3 install pypiwin32
