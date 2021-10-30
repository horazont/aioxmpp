#!/bin/bash
cd /usr/lib/prosody/modules/
patch -p2 < /etc/prosody/0001-pubsub.patch
