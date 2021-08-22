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
import sys

import setuptools
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

version_mod = runpy.run_path("aioxmpp/_version.py")

lxml_constraint = "lxml~=4.0"
if sys.version_info < (3, 5):
    lxml_constraint += ",<4.4"

sortedcollections_constraint = "sortedcollections~=2.1"
if sys.version_info < (3, 6):
    sortedcollections_constraint = "sortedcollections~=1.0"

install_requires = [
    'aiosasl>=0.3',  # need 0.2+ for LGPLv3
    'aioopenssl>=0.1',
    'babel~=2.3',
    'dnspython>=1.0,<3.0',
    lxml_constraint,
    'multidict<6,>=2.0',
    sortedcollections_constraint,
    'pyOpenSSL',
    'pyasn1',
    'pyasn1_modules',
    'tzlocal>=1.2',
]

if tuple(map(int, setuptools.__version__.split(".")[:3])) < (6, 0, 0):
    for i, item in enumerate(install_requires):
        install_requires[i] = item.replace("~=", ">=")

if sys.version_info[:3] < (3, 5, 0):
    install_requires.append("typing")

setup(
    name="aioxmpp",
    version=version_mod["__version__"].replace("-", ""),
    description="Pure-python XMPP library for asyncio",
    long_description=long_description,
    url="https://github.com/horazont/aioxmpp",
    author="Jonas Schäfer",
    author_email="jonas@wielicki.name",
    license="LGPLv3+",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: POSIX",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Communications :: Chat",
        "Topic :: Internet :: XMPP",
    ],
    keywords="asyncio xmpp library",
    install_requires=install_requires,
    packages=find_packages(exclude=["tests*", "benchmarks*"])
)
