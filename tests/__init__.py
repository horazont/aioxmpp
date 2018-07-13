########################################################################
# File name: __init__.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
from aioxmpp.e2etest import (  # NOQA
    setup_package as e2etest_setup_package,
    teardown_package,
)

import warnings


def setup_package():
    e2etest_setup_package()
    warnings.filterwarnings(
        "error",
        message=".+(Stream)?ErrorCondition",
        category=DeprecationWarning,
    )
