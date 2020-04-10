Documentation
#############

Online documentation
--------------------

If you want to read documentation without building it yourself, please check the
online documentation available on `our website
<https://docs.zombofant.net/aioxmpp/devel/>`_. It is automatically updated when
a commit is pushed to devel. Documentation for specific aioxmpp versions is
available at `<https://docs.zombofant.net/aioxmpp/>`_.

Building the documentation
--------------------------

To build the documentation, ``aioxmpp`` and all of its components need to be
importable. This means that you need to have all ``aioxmpp`` dependencies
installed. In addition, `sphinx <http://www.sphinx-doc.org/en/stable/>`_ as well
as the alabaster theme for sphinx are required. Make sure to install sphinx for
python3!

If the executable of sphinx for python3 is not called ``sphinx-build-3`` on your
system, export the ``SPHINXBUILD`` environment variable with the name of the
executable for the makefile to use. For example, if the executable is called
``sphinx-build`` on your system, either add ``SPHINXBUILD=sphinx-build`` to the
make commandline or export it using::

  export SPHINXBUILD=sphinx-build

Once that is done, you can navigate **to the root of the repository** and build
the documentation using::

  make docs-html

The resulting documentation is available in
``docs/sphinx-data/build/html/index.html``. To build the documentation and view
it in your favourite browser immediately, use::

  make docs-view-html
