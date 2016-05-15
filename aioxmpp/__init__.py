"""
Version information
###################

There are two ways to obtain the imported version of the :mod:`aioxmpp`
package:

.. autodata:: __version__

.. data:: version

   Is an alias to :data:`__version__`.

.. autodata:: version_info

"""

#: The imported :mod:`aioxmpp` version as a tuple.
#:
#: The components of the tuple are, in order: `major version`, `minor version`,
#: `patch level`, and `pre-release identifier`.
#:
#: .. seealso::
#:
#:    :ref:`api-stability`
version_info = (0, 5, 4, None)

#: The imported :mod:`aioxmpp` version as a string.
#:
#: The version number is dot-separated; in pre-release or development versions,
#: the version number is followed by a hypen-separated pre-release identifier.
#:
#: .. seealso::
#:
#:    :ref:`api-stability`
__version__ = ".".join(map(str, version_info[:3])) + ("-"+version_info[3] if
                                                      version_info[3] else "")

version = __version__
