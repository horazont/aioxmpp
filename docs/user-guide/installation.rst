Installation
############

You have three options for installing :mod:`aioxmpp`:

1. :ref:`ug-installation-packages`: only on ArchLinux and only if you use AUR,
   but if you do, this is the preferred way for your platform if you want
   to use :mod:`aioxmpp` in your project. It is not recommended if you want to
   hack on :mod:`aioxmpp` (use the third way then).

2. :ref:`ug-installation-pypi`: this is recommended if you simply want to use
   :mod:`aioxmpp` in a project or need it as an dependency for something. It is
   not recommended if you want to hack on :mod:`aioxmpp`.

3. :ref:`ug-installation-source`: this is recommended if you want to hack on
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

.. _ug-installation-packages:

Installing using your system’s package manager
==============================================

Currently, aioxmpp is only packaged in AUR of ArchLinux. On ArchLinux, that
is the preferred way to install aioxmpp.

For other environments, you have to resort to the ways outlined below.

.. _ug-installation-pypi:

Installing from PyPI
====================

.. _ug-installation-pypi-deps-packages:

Installing dependencies using your system’s package manager (recommended)
-------------------------------------------------------------------------

For Debian 8 (Jessie):

.. code-block:: bash

   apt install --no-install-recommends python3-dnspython python3-openssl \
     python3-pyasn1 python3-pyasn1-modules build-essential libxml2-dev \
     libxslt1-dev python3-dev libz-dev python3-pip


For Debian 9 (Stretch):

.. code-block:: bash

   apt install --no-install-recommends python3-dnspython python3-openssl \
     python3-pyasn1 python3-pyasn1-modules python3-multidict \
     python3-tzlocal python3-lxml python3-babel python3-pip

.. _ug-installation-pypi-deps-pypi:

Installing dependencies from PyPI
---------------------------------

You will need some build dependencies for the dependencies, since some (such as
lxml and PyOpenSSL) include C code which will be built during installation.

In addition, we recommend installing PyOpenSSL using your system’s package
manager even if you install other dependencies using pip.

For Debian 8 (Jessie) and 9 (Stretch):

.. code-block:: bash

   apt install --no-install-recommends build-essential libssl-dev \
     libxml2-dev libxslt1-dev python3-dev python3-openssl libz-dev \
     python3-pip


You can now proceed to installing aioxmpp via pip, which will install the
dependencies from pip too.

Installing aioxmpp
------------------

Now, simply running

.. code-block:: bash

   pip3 install aioxmpp

should install everything neccessary to run aioxmpp.

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
Then you tell pip to install the local directory in editable mode. If you
prefer to install dependencies using your system’s package manager, be sure
to do so first (see :ref:`_ug-installation-pypi-deps-packages`), because
:program:`pip3` will install them for you if they are missing.

.. code-block:: bash

   git clone https://github.com/horazont/aioxmpp
   cd aioxmpp
   git checkout devel  # make sure to use the devel branch
   pip3 install -e .  # install in editable mode

Running the unittests
---------------------

To run the unittests, I personally recommend using the nosetests runner:

.. code-block:: bash

   cd path/to/source/of/aioxmpp
   nosetests3 tests

If any of the tests fail for you, this is worth a bug report.
