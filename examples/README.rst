aioxmpp Examples
################

Most of these examples are built ontop of ``framework.py`` (also in this
directory). The only exceptions are those starting with ``quickstart_`` (they
are basically content of the quickstart guide and should be able to stand on
their own, serving as full examples) and ``xmpp_bridge.py``.

Those which use the examples framework share the following command line
options::

  optional arguments:
    -h, --help            show this help message and exit
    -c CONFIG, --config CONFIG
                          Configuration file to read
    -j LOCAL_JID, --local-jid LOCAL_JID
                          JID to authenticate with (only required if not in
                          config)
    -p                    Ask for password on stdio
    -v                    Increase verbosity

``--config`` can point to an INI-style config file, which supports most notably
the following options, all of which are optional::

  [global]
  local_jid=
  password=
  pin_store=
  pin_type=

* ``local_jid`` serves as fallback if the ``--local-jid`` command line argument
  is not given. If neither is given, the JID is prompted for on the terminal.

* ``password`` is the password used for authentication. If this is missing, the
  password is prompted for on the terminal.

* ``pin_store`` and ``pin_type`` can be used to configure certificate pinning,
  in case the server you want to test against does not have a certificate which
  passes the default OpenSSL PKIX tests.

  If set, ``pin_store`` must point to a JSON file, which consists of a single
  object mapping host names to arrays of strings containing the base64
  representation of what is being pinned. This is determined by ``pin_type``,
  which can be ``0`` for Public Key pinning and ``1`` for Certificate pinning.

In addition, some examples support additional configuration options, which are
listed below.

``muc_logger``
==============

::

   [muc_logger]
   muc_jid=
   nick=

* ``muc_jid`` serves as fallback for the ``--muc`` option of that example. If
  neither is given, the JID is prompted for on the terminal.

* ``nick`` serves as fallback for the ``--nick`` option of that example. If
  neither is given, the nickname to use is prompted for on the terminal.

``get_muc_config``
==================

::

   [muc_config]
   muc_jid=

* ``muc_jid`` serves as fallback for the ``--muc`` option of that example. If
  neither is given, the JID is prompted for on the terminal.

  Note that this option is shared with ``get_muc_config``.

``set_muc_config``
==================

::

   [muc_config]
   muc_jid=

* ``muc_jid`` serves as fallback for the ``--muc`` option of that example. If
  neither is given, the JID is prompted for on the terminal.

  Note that this option is shared with ``get_muc_config``.
