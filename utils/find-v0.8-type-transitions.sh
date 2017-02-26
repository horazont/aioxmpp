#!/bin/bash
ARGS="--python"
# this still misses Presence(from_=some_function(), show=…), as regexes cannot count
ag $ARGS '\b(Presence(State)?)\((\s*|[^()]*?,\s*)(show=)?("|None)' "$@"
# if you have unittests working with shows:
ag $ARGS '\bassertEqual\(\s*(None|"(xa|away|dnd|chat)")\s*,\s*[^()]*?show[^()]*?' "$@"
ag $ARGS '\bassertEqual\([^()]*?show[^()]*?,\s*(None|"(xa|away|dnd|chat)")' "$@"
ag $ARGS '\.show\s*=\s*(None|"(xa|away|dnd|chat))' "$@"
ag $ARGS '==\s*(None|"(xa|away|dnd|chat))' "$@"
