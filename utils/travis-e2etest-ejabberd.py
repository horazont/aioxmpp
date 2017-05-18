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

cwd = os.getcwd()

ejabberd = subprocess.Popen(
    [
        "docker",
        "run",
        "-p", "5222:5222",
        "--rm",
        "-v", "{}:/etc/ejabberd".format(
            os.path.join(cwd, "utils/ejabberd-cfg")
        ),
        "jprjr/ejabberd",
    ],
)

time.sleep(5)

if ejabberd.poll() is not None:
    print("ejabberd already terminated!", file=sys.stderr)
    sys.exit(10)

container_id = subprocess.check_output([
    "docker", "ps", "-ql",
]).decode().strip()
print("I think the ejabberd container ID is {}".format(container_id))

try:
    subprocess.check_call(
        ["python3",
         "-m", "aioxmpp.e2etest",
         "--e2etest-config=.travis-e2etest.ini",
         "tests"]
    )
finally:
    print("killing ejabberd")
    subprocess.check_call([
        "docker", "kill", container_id
    ])
    print("waiting for ejabberd to die...")
    ejabberd.wait()
