#!/bin/bash
ARGS="--python"
# this still misses IQ(from_=some_function(), type_=…), as regexes cannot count
ag $ARGS '\b(Presence|Message|IQ|Error)\((\s*|[^()]*?,\s*)(type_=)?("|None)' "$@"
# split these two, as None is a wildcard for register_message_callback
ag $ARGS '\b(un)?register_message_callback\(\s*(type_=)?"' "$@"
ag $ARGS '\b(un)?register_presence_callback\(\s*(type_=)?("|None)' "$@"
ag $ARGS '\b(un)?register_iq_request_coro\(\s*"' "$@"
ag $ARGS '\bmake_reply\([^()]*?(type_=)?("|None)' "$@"
# if you have unittests working with type_s:
ag $ARGS '\bassertEqual\(\s*(None|"(result|get|set|error|subscribed?|unsubscribed?|probe|unavailable|chat|groupchat|normal|headline)")\s*,\s*[^()]*?type_[^()]*?' "$@"
ag $ARGS '\bassertEqual\([^()]*?type_[^()]*?,\s*(None|"(result|get|set|error|subscribed?|unsubscribed?|probe|unavailable|chat|groupchat|normal|headline)")' "$@"
ag $ARGS '\.type_\s*=\s*(None|"(result|get|set|error|subscribed?|unsubscribed?|probe|unavailable|chat|groupchat|normal|headline))' "$@"
ag $ARGS '==\s*(None|"(result|get|set|error|subscribed?|unsubscribed?|probe|unavailable|chat|groupchat|normal|headline))' "$@"
