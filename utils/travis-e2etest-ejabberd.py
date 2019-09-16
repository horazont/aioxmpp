#!/usr/bin/env python
########################################################################
# File name: travis-e2etest-ejabberd.py
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

ejabberd_version = os.environ["EJABBERD_VERSION"]
if ejabberd_version == "latest":
    ejabberd_version_numeric = float("inf")
else:
    ejabberd_version_numeric = float(ejabberd_version)

cfg_files = None
if ejabberd_version_numeric >= 19.08:
    cfg_dir = "/home/ejabberd/conf/"
    cfg_files = ["ejabberd.yml", "server.pem"]
elif ejabberd_version_numeric >= 18.01:
    cfg_dir = "/home/ejabberd/conf/"
elif ejabberd_version_numeric >= 17.12:
    cfg_dir = "/home/ejabberd/config/"
else:
    cfg_dir = "/home/p1/cfg"

local_cfg_dir = os.path.join(cwd, "utils/ejabberd-cfg", ejabberd_version)
if cfg_files is None:
    volumes = ["{}:{}".format(local_cfg_dir, cfg_dir)]
else:
    volumes = ["{}/{file_}:{}/{file_}".format(local_cfg_dir, cfg_dir, file_=file_)
               for file_ in cfg_files]

print(
    "using cfg_dir={!r} for ejabberd {:.2f}".format(
        cfg_dir, ejabberd_version_numeric
    )
)

argv = [
    "docker",
    "run",
    "-p", "5222:5222",
    "--rm",
    "--name", "ejabberd",
]
for volume in volumes:
    argv.append("-v")
    argv.append(volume)
argv.append("ejabberd/ecs:{}".format(ejabberd_version))

ejabberd = subprocess.Popen(argv)

time.sleep(5)

if ejabberd.poll() is not None:
    print("ejabberd already terminated!", file=sys.stderr)
    sys.exit(10)

try:
    subprocess.check_call(
        ["python3",
         "-m", "aioxmpp.e2etest",
         "--e2etest-config=utils/ejabberd-cfg/e2etest.ini",
         "tests"]
    )
finally:
    print("killing ejabberd")
    subprocess.check_call([
        "docker", "kill", "ejabberd"
    ])
    print("waiting for ejabberd to die...")
    ejabberd.wait()
