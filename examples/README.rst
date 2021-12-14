aioxmpp Examples
################

Most of these examples are built on top of ``framework.py`` (also in this
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


Running ``adhoc_browser``
=========================

To run ``adhoc_browser``, you need PyQt5 and you need to compile the Qt Designer
UI file to python code. For the latter, run::

  make

in the examples directory. Now you can start the adhoc browser::

  python3 -m adhoc_browser

You may pass additional command line arguments like you can for other examples.

``retrieve_avatar.py``
======================

``retrieve_avatar.py`` retrieves the PNG avatar of another user and
stores it in a file.

positional arguments:
  ====================  ===================================================
  output_file           the file the retrieved avatar image will be written
                        to.
  ====================  ===================================================

Additional optional argument:

  --remote-jid REMOTE_JID
                        the jid of which to retrieve the avatar

The remote JID may also be supplied in the examples config file::

      [avatar]
      remote_jid=foo@example.com

If the remote JID is not given on the command line and also missing
from the config file ``retrieve_avatar.py`` will prompt for it.

``set_avatar.py``
=================

``set_avatar.py`` sets or unsets the avatar of the configured local
JID.

operations:
  --set-avatar AVATAR_FILE
                        set the avatar to content of the supplied PNG file.
  --wipe-avatar         set the avatar to no avatar.

`get_vcard.py`
==============

``get_vcard.py`` gets the vCard for a remote JID.

Additional optional argument:

  --remote-jid REMOTE_JID
                        the jid of which to retrieve the avatar

The remote JID may also be supplied in the examples config file::

      [vcard]
      remote_jid=foo@example.com

If the remote JID is not given on the command line and also missing
from the config file ``get_vcard.py`` will prompt for it.
