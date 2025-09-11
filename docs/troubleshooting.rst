===============
Troubleshooting
===============

This sections enumerates potential connection problems with ``crash``,
and how to investigate and resolve them.


Debugging connection errors
===========================

If you are connecting to `CrateDB`_, for example like this::

    crash --hosts 'http://localhost:4200' -U 'admin' -W

and ``crash`` responds with a connection error message like this::

    CONNECT ERROR

you may want to add the ``--verbose`` command line option, in order to find out
about the reason why the connection fails. It could be a DNS / name resolution
error, or it could be a problem related to SSL termination.

Other than ``--verbose``, you can also use the shorthand version ``-v``::

    crash --hosts 'http://localhost:4200' -U 'admin' -W -v



SSL connection errors
=====================

`A recent problem`_ outlined SSL connectivity problems when connecting to
`CrateDB Cloud`_::

    crash --hosts 'https://MY-CLUSTER-NAME.eks1.eu-west-1.aws.cratedb.net:4200' -U 'admin' -W -v

The verbose output using ``crash -v`` signaled a certificate verification error
like that::

    Server not available, exception: HTTPSConnectionPool(host='MY-CLUSTER-NAME.eks1.eu-west-1.aws.cratedb.net', port=4200):
    Max retries exceeded with url: / (Caused by SSLError(SSLCertVerificationError(1, '
    [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1006)')))

If you are on macOS, the Python Installer offers an easy option to install the
required SSL root certificates. Because ``crash`` uses Python, this is the
right choice to resolve the problem durably.

.. figure:: https://github.com/crate/crash/assets/453543/c4e49d7e-86d8-40f6-b0d8-f64889f9d972

In order to install the SSL root certificates retroactively, you can use a
command like::

    /Applications/Python 3.11/Install Certificates.command


.. _a recent problem: https://community.cratedb.com/t/issue-connecting-to-cratedb-cloud-cluster-from-local-machine/1707
.. _CrateDB: https://github.com/crate/crate
.. _CrateDB Cloud: https://console.cratedb.cloud
