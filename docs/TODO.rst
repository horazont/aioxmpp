TODO
####

XEPs to directly implement support for
======================================

* XEP-0050: Ad-Hoc Commands (serving and querying)
* XEP-0085: Chat State Notifications (with handling for legacy XEP-0022)
* XEP-0184: Message Delivery Reciepts (with handling for legacy XEP-0022)
* XEP-0280: Message Carbons (with support for special handling w.r.t. XEP-0085
  and XEP-0184)

Other stuff
===========

* test framework to automatedly run integration tests against specified server
  (will require ad-hoc commands...)
* polish pubsub and muc implementation

@stanza_model
=============

* Handle multiple children in Child / ChildText

@stanza_types
=============

* Validator arithmetic?


Presence stuff
==============

* we need a away to define the current presence
* idea: move that to the Presence service
* idea 2: use the Presence service to implement the features of PresenceManagedClient
* idea 3: remove PresenceManagedClient and rename AbstractClient -> Client
