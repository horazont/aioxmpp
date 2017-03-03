#!/usr/bin/env python3
########################################################################
# File name: buildui.py
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

# pyuic is not installed on my system, so here we go with a workaround

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-5", "--qt5",
        dest="version",
        action="store_const",
        const=5,
        default=4)
    parser.add_argument("uifile")
    parser.add_argument("pyfile")

    args = parser.parse_args()

    if args.version == 4:
        import PyQt4.uic as uic
    elif args.version == 5:
        import PyQt5.uic as uic
    else:
        raise ValueError("Invalid version: {}".format(args.version))

    with open(args.pyfile, "w") as f:
        f.write("#pylint: skip-file\n")
        uic.compileUi(args.uifile, f)
