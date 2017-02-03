#!/usr/bin/env python
from __future__ import unicode_literals, print_function

import subprocess
import os
import time
import sys

prosody = subprocess.Popen(
    [
        "./prosody",
    ],
    cwd=os.path.join(os.getcwd(), "prosody"),
)

time.sleep(2)

if prosody.poll() is not None:
    print("Prosody already terminated!", file=sys.stderr)
    sys.exit(10)

try:
    subprocess.check_call(
        ["python3",
         "-m", "aioxmpp.e2etest",
         "--e2etest-config=.travis-e2etest.ini",
         "tests"]
    )
finally:
    prosody.kill()
    prosody.wait()
