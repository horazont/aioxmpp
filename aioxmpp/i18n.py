########################################################################
# File name: i18n.py
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
"""
:mod:`~aioxmpp.i18n` -- Helper functions for localizing text
############################################################

This module provides facilities to facilitate the internationalization of
applications using :mod:`aioxmpp`.

.. autoclass:: LocalizingFormatter

.. autoclass:: LocalizableString

Shorthand functions
===================

.. autofunction:: _

.. autofunction:: ngettext

"""

import numbers
import string

from datetime import datetime, timedelta, date, time

import babel
import babel.dates
import babel.numbers
import tzlocal


class LocalizingFormatter(string.Formatter):
    """
    This is an alternative implementation on top of
    :class:`string.Formatter`. It is designed to work well with :mod:`babel`,
    which also means that some things work differently when compared with the
    default :class:`string.Formatter`.

    Most notably, all objects from :mod:`datetime` are handled without using
    their :meth:`__format__` method. Depending on their type, they are
    forwarded to the respective formatting method in :mod:`babel.dates`.

    +----------------------------+------------------------------------+-----------------+
    |Type                        |Babel function                      |Timezone support |
    +============================+====================================+=================+
    |:class:`~datetime.datetime` |:func:`babel.dates.format_datetime` |yes              |
    +----------------------------+------------------------------------+-----------------+
    |:class:`~datetime.timedelta`|:func:`babel.dates.format_timedelta`|no               |
    +----------------------------+------------------------------------+-----------------+
    |:class:`~datetime.date`     |:func:`babel.dates.format_date`     |no               |
    +----------------------------+------------------------------------+-----------------+
    |:class:`~datetime.time`     |:func:`babel.dates.format_time`     |no               |
    +----------------------------+------------------------------------+-----------------+

    If the format specification is empty, the default format as babel defines
    it is used.

    In addition to date and time formatting, numbers which use the ``n`` format
    type are also formatted with babel. If the format specification is empty
    (except for the trailing ``n``), :func:`babel.numbers.format_number` is
    used. Otherwise, the remainder of the format specification is passed as
    format to :func:`babel.numbers.format_decimal`.

    Examples::

      >>> import pytz, babel, datetime, aioxmpp.i18n
      >>> tz = pytz.timezone("Europe/Berlin")
      >>> dt = datetime.datetime(year=2015, 5, 5, 15, 55, 55, tzinfo=tz)
      >>> fmt = aioxmpp.i18n.LocalizingFormatter(locale=babel.Locale("en_GB"))
      >>> fmt.format("{}", dt)
      '5 May 2015 15:55:55'
      >>> fmt.format("{:full}", dt)
      'Tuesday, 5 May 2015 15:55:55 GMT+00:00'
      >>> fmt.format("{:##.###n}, 120.3)
      >>> fmt.format("{:##.###n}", 12.3)
      '12.3'
      >>> fmt.format("{:##.###;-(#)n}", -1.234)
      '-(1.234)'
      >>> fmt.format("{:n}", -10000)
      '-10,000'

    """  # NOQA

    def __init__(self, locale=None, tzinfo=None):
        super().__init__()
        self.locale = locale if locale is not None else babel.default_locale()
        self.tzinfo = tzinfo if tzinfo is not None else tzlocal.get_localzone()

    def format_field(self, value, format_spec, locale=None, tzinfo=None):
        if tzinfo is None:
            tzinfo = self.tzinfo

        if locale is None:
            locale = self.locale

        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = tzinfo.normalize(value)
            if format_spec:
                return babel.dates.format_datetime(value,
                                                   locale=locale,
                                                   format=format_spec)
            else:
                return babel.dates.format_datetime(value,
                                                   locale=locale)
        elif isinstance(value, timedelta):
            if format_spec:
                return babel.dates.format_timedelta(value,
                                                    locale=locale,
                                                    format=format_spec)
            else:
                return babel.dates.format_timedelta(value,
                                                    locale=locale)
        elif isinstance(value, date):
            if format_spec:
                return babel.dates.format_date(value,
                                               locale=locale,
                                               format=format_spec)
            else:
                return babel.dates.format_date(value,
                                               locale=locale)
        elif isinstance(value, time):
            if format_spec:
                return babel.dates.format_time(value,
                                               locale=locale,
                                               format=format_spec)
            else:
                return babel.dates.format_time(value,
                                               locale=locale)
        elif isinstance(value, numbers.Real) and format_spec.endswith("n"):
            if len(format_spec) > 1:
                return babel.numbers.format_decimal(value,
                                                    format=format_spec[:-1],
                                                    locale=locale)
            else:
                return babel.numbers.format_number(value, locale=locale)
        else:
            return super().format_field(value, format_spec)

    def convert_field(self, value, conversion, locale=None, tzinfo=None):
        if conversion != "s":
            return super().convert_field(value, conversion)

        if locale is None:
            locale = self.locale

        if tzinfo is None:
            tzinfo = self.tzinfo

        if isinstance(value, datetime):
            return babel.dates.format_datetime(
                tzinfo.normalize(value),
                locale=locale)
        elif isinstance(value, timedelta):
            return babel.dates.format_timedelta(value, locale=locale)
        elif isinstance(value, date):
            return babel.dates.format_date(value, locale=locale)
        elif isinstance(value, time):
            return babel.dates.format_time(
                value,
                locale=locale)

        return super().convert_field(value, conversion)


class LocalizableString:
    """
    This class can be used for lazily translated localizable strings.

    `singular` must be a :class:`str`. If `plural` is not set, the string will
    be localized using `gettext`; otherwise, `ngettext` will be used. The
    detailed process on localizing a string is described in the documentation
    of :meth:`localize`.

    Localizable strings compare equal if their `singular`, `plural` and
    `number_index` values all match. The :func:`str` of a localizable string is
    its singular string. The :func:`repr` depends on whether `plural` is set
    and refers to the usage of :func:`_` and :func:`ngettext`.

    The arguments are stored in attributes named like the
    arguments. :class:`LocalizableString` instances are immutable and
    hashable.

    Examples::

      >>> import aioxmpp.i18n, pytz, babel, gettext
      >>> fmt = aioxmpp.i18n.LocalizingFormatter()
      >>> translator = gettext.NullTranslations()
      >>> s1 = aioxmpp.i18n.LocalizableString(
      ...     "{count} thing",
      ...     "{count} things", "count")
      >>> s1.localize(fmt, translator, count=1)
      '1 thing'
      >>> s1.localize(fmt, translator, count=10)
      '10 things'

    .. automethod:: localize

    """

    __slots__ = ("_singular", "_plural", "_number_index")

    def __init__(self, singular, plural=None, number_index=None):
        if plural is None and number_index is not None:
            raise ValueError("plural is required if number_index is given")
        self._singular = singular
        self._plural = plural
        if plural is not None:
            if number_index is None:
                number_index = "0"
            self._number_index = str(number_index)
        else:
            self._number_index = None

    @property
    def singular(self):
        return self._singular

    @property
    def plural(self):
        return self._plural

    @property
    def number_index(self):
        return self._number_index

    def __eq__(self, other):
        if not isinstance(other, LocalizableString):
            return NotImplemented
        return (self.singular == other.singular and
                self.plural == other.plural and
                self.number_index == other.number_index)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self._singular, self._plural, self._number_index))

    def localize(self, formatter, translator, *args, **kwargs):
        """
        Localize and format the string using the given `formatter` and
        `translator`. The remaining args are passed to the
        :meth:`~LocalizingFormatter.format` method of the `formatter`.

        The `translator` must be an object supporting the
        :class:`gettext.NullTranslations` interface.

        If :attr:`plural` is not :data:`None`, the number which will be passed
        to the `ngettext` method of `translator` is first extracted from the
        `args` or `kwargs`, depending on :attr:`number_index`. The whole
        semantics of all three are described in
        :meth:`string.Formatter.get_field`, which is used by this method
        (:attr:`number_index` is passed as `field_name`).

        The value returned by :meth:`~string.Formatter.get_field` is then used
        as third argument to `ngettext`, while the others are sourced from
        :attr:`singular` and :attr:`plural`.

        If :attr:`plural` is :data:`None`, the `gettext` method of `translator`
        is used with :attr:`singular` as its only argument.

        After the translation step, the `formatter` is used with the translated
        string and `args` and `kwargs` to obtain a formatted version of the
        string which is then returned.

        All of this works best when using a :class:`LocalizingFormatter`.
        """
        if self.plural is not None:
            n, _ = formatter.get_field(self.number_index, args, kwargs)
            translated = translator.ngettext(self.singular,
                                             self.plural,
                                             n)
        else:
            translated = translator.gettext(self.singular)
        return formatter.vformat(translated, args, kwargs)

    def __str__(self):
        return self.singular

    def __repr__(self):
        if self.plural is not None:
            return "ngettext({!r}, {!r}, {!r})".format(
                self.singular,
                self.plural,
                self.number_index
            )
        return "_({!r})".format(self.singular)


def _(s):
    """
    Return a new singular :class:`LocalizableString` using `s` as singular
    form.
    """
    return LocalizableString(s)


def ngettext(singular, plural, number_index):
    """
    Return a new plural :class:`LocalizableString` with the given arguments;
    these are passed to the constructor of :class:`LocalizableString`.
    """
    return LocalizableString(singular, plural, number_index)
