Installation
############

There are currently two main ways of installing :mod:`aioxmpp`:

1. :ref:`ug-installation-pypi`: this is recommended if you simply want to use
   :mod:`aioxmpp` in a project or need it as an dependency for something. It is
   not recommended if you want to hack on :mod:`aioxmpp`.

2. :ref:`ug-installation-source`: this is recommended if you want to hack on
   :mod:`aioxmpp` or if you anticipate requiring bugfixes or new features while
   you use :mod:`aioxmpp`.

.. note::

   You can help adding a third (and then new first way, because that way is the
   one I prefer most) way: Become a package maintainer for :mod:`aioxmpp` for
   your favourite Linux distribution. `rku <https://github.com/rku/>`_ was so
   kind to create an `ArchLinux package in AUR
   <https://aur.archlinux.org/packages/python-aioxmpp/>`_, but other
   distributions are still lacking the awesomeness (``;-)``) of :mod:`aioxmpp`.
   *You* can change that.

.. _ug-installation-pypi:

Installing from PyPI
====================

In theory, simply running

.. code-block:: bash

   pip3 install aioxmpp

should install everything neccessary to run aioxmpp. You may need to install
dependencies for other packages manually. Most commonly you will need
python3-dev, libssl-dev (for Cryptography/PyOpenSSL) and libxml2-dev (for lxml)
(the package names will vary across platforms).

.. note::

   There is also an AUR package for aioxmpp for ArchLinux. You might want to use
   that instead of installing using pip.

.. note::

   On Debian Jessie (Debian 8), the pip from the packages is too old to install
   aioxmpp: it does not know the ``~=`` version comparison operator. This is
   unfortunate, but ``~=`` provides safety against accidental incompatible
   changes in dependencies.

   To install on Debian Jessie, you will need to upgrade pip using:

   .. code-block:: bash

      pip3 install --upgrade setuptools
      pip3 install --upgrade pip

   (You may add the ``--user`` flag or use a virtualenv if you don’t want to
   upgrade pip system-wide.)

.. _ug-installation-source:

Installing in editable mode from source
=======================================

Editable mode allows you to hack on aioxmpp while still being able to import it
from everywhere. You can read more about it in the relevant chapter from the
`Python Packaging User Guide
<https://packaging.python.org/en/latest/distributing/#working-in-development-mode>`_.

To install in editable mode, you first need a clone of the aioxmpp repository.
Then you tell pip to install the local directory in editable mode. It will
assume that you have all dependencies in place.

.. code-block:: bash

   git clone https://github.com/horazont/aioxmpp
   cd aioxmpp
   git checkout devel  # make sure to use the devel branch
   pip3 install -e .  # install in editable mode

If any dependencies are missing, you will notice rather quickly. Check the
README to see what dependencies aioxmpp needs.

Running the unittests
---------------------

To run the unittests, I personally recommend using the nosetests runner:

.. code-block:: bash

   cd path/to/source/of/aioxmpp
   nosetests3 tests

If any of the tests fail for you, this is worth a bug report.
