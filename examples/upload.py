########################################################################
# File name: upload.py
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
import argparse
import asyncio
import configparser
import os
import pathlib
import re
import subprocess
import sys

import aiohttp

import aioxmpp
import aioxmpp.httpupload

from aioxmpp.utils import namespaces

from framework import Example, exec_example


@aiohttp.streamer
def file_sender(writer, file_, size, show_progress):
    try:
        pos = file_.tell()
    except (OSError, AttributeError):
        pos = 0

    while True:
        data = file_.read(4096)
        if not data:
            return

        pos += len(data)

        if show_progress:
            print(
                "\r{:>3.0f}%".format((pos / size) * 100),
                flush=True,
                end="",
            )

        yield from writer.write(data)


class Upload(Example):
    VALID_MIME_RE = re.compile(r"^\w+/\w+$")
    DEFAULT_MIME_TYPE = "application/octet-stream"

    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        mutex = self.argparse.add_mutually_exclusive_group()

        mutex.add_argument(
            "-s", "--service",
            default=None,
            type=jid,
            help="The HTTP Upload service to use. Omit to auto-discover."
        )

        mutex.add_argument(
            "--service-discover",
            dest="service",
            action="store_const",
            const=False,
            help="Force auto-discovery, even if a service is configured."
        )

        self.argparse.add_argument(
            "-t", "--mime-type", "--content-type",
            default=None,
            help="Content / MIME type of the file "
            "(will attempt to auto-detect if omitted)"
        )

        mutex = self.argparse.add_mutually_exclusive_group()

        mutex.add_argument(
            "--quiet",
            dest="progress",
            action="store_false",
            default=os.isatty(sys.stdout.fileno()),
            help="Do not print progress",
        )

        mutex.add_argument(
            "--progress",
            dest="progress",
            action="store_true",
            help="Print progress",
        )

        self.argparse.add_argument(
            "file",
            default=None,
            type=argparse.FileType("rb"),
            help="File to upload"
        )

    def configure(self):
        super().configure()

        self.service_addr = self.args.service
        if self.service_addr is None:
            try:
                self.service_addr = aioxmpp.JID.fromstr(
                    self.config.get("upload", "service_address")
                )
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                pass

        self.file = self.args.file
        self.file_name = pathlib.Path(self.file.name).name
        self.file_size = os.fstat(self.file.fileno()).st_size
        self.file_type = self.args.mime_type
        self.show_progress = self.args.progress

        if not self.file_type:
            try:
                self.file_type = subprocess.check_output([
                    "xdg-mime", "query", "filetype",
                    self.file.name,
                ]).decode().strip()
            except subprocess.CalledProcessError:
                self.file_type = self.DEFAULT_MIME_TYPE
                print("warning: failed to determine mime type, using {}".format(
                    self.file_type,
                ))

    @asyncio.coroutine
    def _check_for_upload_service(self, disco, jid):
        info = yield from disco.query_info(jid)
        if namespaces.xep0363_http_upload in info.features:
            return jid

    async def upload(self, url, headers):
        headers["Content-Type"] = self.file_type
        headers["Content-Length"] = str(self.file_size)
        headers["User-Agent"] = "aioxmpp/{}".format(aioxmpp.__version__)

        async with aiohttp.ClientSession() as session:
            async with session.put(
                    url,
                    data=file_sender(file_=self.file,
                                     size=self.file_size,
                                     show_progress=self.show_progress),
                    headers=headers) as response:
                if self.show_progress:
                    print("\r", end="")
                if response.status not in (200, 201):
                    print(
                        "error: upload failed: {}".format(response.reason),
                        file=sys.stderr,
                    )
                    return False

        return True

    @asyncio.coroutine
    def run_simple_example(self):
        if not self.service_addr:
            disco = self.client.summon(aioxmpp.DiscoClient)
            items = yield from disco.query_items(
                self.client.local_jid.replace(localpart=None, resource=None),
                timeout=10
            )

            lookups = []

            for item in items.items:
                if item.node:
                    continue
                lookups.append(self._check_for_upload_service(disco, item.jid))

            jids = list(filter(
                None,
                (yield from asyncio.gather(*lookups))
            ))

            if not jids:
                print("error: failed to auto-discover upload service",
                      file=sys.stderr)
                return

            self.service_addr = jids[0]

        print("using {}".format(self.service_addr), file=sys.stderr)

        slot = yield from self.client.send(
            aioxmpp.IQ(
                to=self.service_addr,
                type_=aioxmpp.IQType.GET,
                payload=aioxmpp.httpupload.Request(
                    self.file_name,
                    self.file_size,
                    self.file_type,
                )
            )
        )

        if not (yield from self.upload(slot.put.url, slot.put.headers)):
            return

        print(slot.get.url)


if __name__ == "__main__":
    exec_example(Upload())
