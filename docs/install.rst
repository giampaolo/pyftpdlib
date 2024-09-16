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

`PyOpenSSL`_, to support `FTPS`_:

.. code-block:: sh

    $ pip3 install PyOpenSSL

`pywin32`_ if you want to use `WindowsAuthorizer`_ on Windows:

.. code-block:: sh

    $ pip3 install pypiwin32

.. _`FTPS`: https://pyftpdlib.readthedocs.io/en/latest/tutorial.html#ftps-ftp-over-tls-ssl-server
.. _`PyOpenSSL`: https://pypi.org/project/pyOpenSSL
.. _`WindowsAuthorizer`: api.html#pyftpdlib.authorizers.UnixAuthorizer
.. _`pywin32`: https://pypi.org/project/pywin32/
