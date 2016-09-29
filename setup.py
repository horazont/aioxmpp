#!/usr/bin/env python3
import codecs
import os.path

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

import aioxmpp

setup(
    name="aioxmpp",
    version=aioxmpp.__version__,
    description="Pure-python XMPP library for asyncio",
    long_description=long_description,
    url="https://github.com/horazont/aioxmpp",
    author="Jonas Wielicki",
    author_email="jonas@wielicki.name",
    license="GPLv3",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: POSIX",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Communications :: Chat",
    ],
    keywords="asyncio xmpp library",
    install_requires=['aiosasl',
                      'aioopenssl',
                      'babel~=2.3',
                      'dnspython3~=1.14',
                      'lxml~=3.6',
                      'multidict~=2.0',
                      'orderedset>=1.2',
                      'pyOpenSSL>=15.0',
                      'pyasn1',
                      'pyasn1_modules',
                      'tzlocal~=1.2'],
    packages=find_packages(exclude=["tests*"])
)
