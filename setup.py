#!/usr/bin/env python3
########################################################################
# File name: setup.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import os.path
import runpy

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

version_mod = runpy.run_path("aioxmpp/version.py")

setup(
    name="aioxmpp",
    version=version_mod["__version__"],
    description="Pure-python XMPP library for asyncio",
    long_description=long_description,
    url="https://github.com/horazont/aioxmpp",
    author="Jonas Wielicki",
    author_email="jonas@wielicki.name",
    license="LGPLv3+",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: POSIX",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Communications :: Chat",
    ],
    keywords="asyncio xmpp library",
    install_requires=['aiosasl>=0.2',  # need 0.2+ for LGPLv3
                      'aioopenssl>=0.1',
                      'babel~=2.3',
                      'dnspython3~=1.14',
                      'idna~=2.1',
                      'lxml~=3.6',
                      'multidict~=2.0',
                      'orderedset>=1.2',
                      'pyOpenSSL>=15.0',
                      'pyasn1',
                      'pyasn1_modules',
                      'tzlocal~=1.2'],
    packages=find_packages(exclude=["tests*"])
)
