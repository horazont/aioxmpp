#!/usr/bin/env python
########################################################################
# File name: travis-e2etest.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
########################################################################
from __future__ import unicode_literals, print_function

import subprocess
import os
import time
import sys

argv = ["python3",
        "-m", "aioxmpp.e2etest",
        "--e2etest-config=.travis-e2etest.ini",
        "tests"]

if sys.argv[1:] == ["--cover"]:
    print("running e2etests with covergae")
    argv.insert(-1, "--with-cover")
    argv.insert(-1, "--cover-package")
    argv.insert(-1, "aioxmpp")

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
    subprocess.check_call(argv)
finally:
    prosody.kill()
    prosody.wait()
