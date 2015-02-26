import base64
import binascii
import re

import pytz

from datetime import datetime, timedelta


class String:
    def parse(self, v):
        return v

    def format(self, v):
        return v


class Integer:
    def parse(self, v):
        return int(v)

    def format(self, v):
        return str(v)


class Float:
    def parse(self, v):
        return float(v)

    def format(self, v):
        return str(v)


class Bool:
    def parse(self, v):
        v = v.strip()
        if v in ["true", "1"]:
            return True
        elif v in ["false", "0"]:
            return False
        else:
            raise ValueError("not a boolean value")

    def format(self, v):
        if v:
            return "true"
        else:
            return "false"


class DateTime:
    tzextract = re.compile("((Z)|([+-][0-9]{2}):([0-9]{2}))$")

    def parse(self, v):
        v = v.strip()
        m = self.tzextract.search(v)
        if m:
            _, utc, hour_offset, minute_offset = m.groups()
            if utc:
                hour_offset = 0
                minute_offset = 0
            else:
                hour_offset = int(hour_offset)
                minute_offset = int(minute_offset)
            tzinfo = pytz.utc
            offset = timedelta(minutes=minute_offset+60*hour_offset)
            v = v[:m.start()]
        else:
            tzinfo = None
            offset = timedelta(0)

        try:
            dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")

        return dt.replace(tzinfo=tzinfo) - offset

    def format(self, v):
        if v.tzinfo:
            v = pytz.utc.normalize(v)
        result = v.strftime("%Y-%m-%dT%H:%M:%S")
        if v.microsecond:
            result += ".{:06d}".format(v.microsecond).rstrip("0")
        if v.tzinfo:
            result += "Z"
        return result


class Base64Binary:
    def parse(self, v):
        return base64.b64decode(v)

    def format(self, v):
        return base64.b64encode(v).decode("ascii")


class HexBinary:
    def parse(self, v):
        return binascii.a2b_hex(v)

    def format(self, v):
        return binascii.b2a_hex(v).decode("ascii")
