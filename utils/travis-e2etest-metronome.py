#!/usr/bin/env python
########################################################################
# File name: travis-e2etest-prosody.py
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

metronome_version = os.environ["METRONOME_VERSION"]

metronome = subprocess.Popen(
    [
        "./metronome",
    ],
    cwd=os.path.join(os.getcwd(), "metronome"),
)

time.sleep(2)

if metronome.poll() is not None:
    print("Metronome already terminated!", file=sys.stderr)
    sys.exit(10)

try:
    subprocess.check_call(
        [
            "python3",
            "-m", "aioxmpp.e2etest",
            "--e2etest-config=utils/metronome-cfg/{}/e2etest.ini".format(
                metronome_version,
            ),
            "tests"
        ]
    )
finally:
    metronome.kill()
    metronome.wait()
