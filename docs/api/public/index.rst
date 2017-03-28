Main classes
############

This section of the API covers the classes which are directly instantiated or
used to communicate with an XMPP server.

.. toctree::
   :maxdepth: 2

   node
   stream
   stanza
   security_layer


.. _api-xep-modules:


Protocol part and XEP implementations
#####################################

This section contains services (cf. :mod:`aioxmpp.service`) which can be
summoned (cf. :meth:`aioxmpp.Client.summon`) into a client, to extend its
functionality or provide backwards compatibility.

.. toctree::
   :maxdepth: 2

   adhoc
   avatar
   disco
   entitycaps
   forms
   muc
   presence
   pubsub
   roster
   rfc6120
   rfc3921
   rsm
   shim


Less common and helper classes
##############################

The modules in this section implement some of the tools which are used to
provide the functionality of the main classes (such as
:mod:`aioxmpp.callbacks`). In addition, classes and modules which are rarely
used directly by basic clients (such as the :mod:`aioxmpp.sasl` module) are
sorted into this section.

.. toctree::
   :maxdepth: 2

   structs
   tracking
   nonza
   sasl
   errors
   i18n
   callbacks
   connector
   dispatcher


APIs mainly relevant for extension developers
#############################################

These APIs are used by many of the other modules, but detailed knowledge is
usually required (for users of :mod:`aioxmpp`) only if extensions are to be
developed.

.. toctree::
   :maxdepth: 2

   service
   xso
