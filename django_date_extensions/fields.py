import time, re, datetime
from datetime import date
from django.conf import settings

from six import with_metaclass
from django.db import models
from django import forms
from django.forms import ValidationError
from django.utils import dateformat

from .widgets import PrettyDateInput

try:
    from south.modelsinspector import add_introspection_rules

    add_introspection_rules([], ["^django_date_extensions\.fields\.ApproximateDateField"])
except ImportError:
    pass


OUTPUT_FORMAT_DAY_MONTH_YEAR = getattr(settings, 'DATE_EXTENSIONS_OUTPUT_FORMAT_DAY_MONTH_YEAR', "jS F Y")
OUTPUT_FORMAT_MONTH_YEAR = getattr(settings, 'DATE_EXTENSIONS_OUTPUT_FORMAT_MONTH_YEAR', "F Y")
OUTPUT_FORMAT_YEAR = getattr(settings, 'DATE_EXTENSIONS_OUTPUT_FORMAT_YEAR', "Y")


class ApproximateDate(object):
    """A date object that accepts 0 for month or day to mean we don't
       know when it is within that month/year."""

    def __init__(self, year=0, month=0, day=0, future=False, past=False):
        if future and past:
            raise ValueError("Can't be both future and past")
        elif future or past:
            d = None
            if year or month or day:
                raise ValueError("Future or past dates can have no year, month or day")
        elif year and month and day:
            d = date(year, month, day)
        elif year and month:
            d = date(year, month, 1)
        elif year and day:
            raise ValueError("You cannot specify just a year and a day")
        elif year:
            d = date(year, 1, 1)
        else:
            raise ValueError("You must specify a year")

        self.future = future
        self.past = past
        self.year = year
        self.month = month
        self.day = day

    def __repr__(self):
        if self.future or self.past:
            return str(self)
        elif self.year and self.month and self.day:
            return "{year:d}-{month:d}-{day:d}".format(year=self.year, month=self.month, day=self.day)
        elif self.year and self.month:
            return "{year:d}-{month:d}-00".format(year=self.year, month=self.month)
        elif self.year:
            return "{year:d}-00-00".format(year=self.year)

    def __str__(self):
        if self.future:
            return 'future'
        if self.past:
            return 'past'
        elif self.year and self.month and self.day:
            return dateformat.format(self, OUTPUT_FORMAT_DAY_MONTH_YEAR)
        elif self.year and self.month:
            return dateformat.format(self, OUTPUT_FORMAT_MONTH_YEAR)
        elif self.year:
            return dateformat.format(self, OUTPUT_FORMAT_YEAR)

    def __eq__(self, other):
        if other is None:
            return False
        if not isinstance(other, ApproximateDate):
            return False
        elif (self.year, self.month, self.day, self.future, self.past) != (
                other.year, other.month, other.day, other.future, other.past):
            return False
        else:
            return True

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        if other is None:
            return False
        elif self.future or other.future:
            if self.future:
                return False  # regardless of other.future it won't be less
            else:
                return True  # we were not in future so they are
        elif self.past or other.past:
            if other.past:
                return False  # regardless of self.past it won't be more
            else:
                return True  # we were not in past so they are
        elif (self.year, self.month, self.day) < (other.year, other.month, other.day):
            return True
        else:
            return False

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return self > other or self == other

    def __len__(self):
        return len(self.__repr__())


ansi_date_re = re.compile(r'^\d{4}-\d{1,2}-\d{1,2}$')


class ApproximateDateField(with_metaclass(models.SubfieldBase, models.CharField)):
    """A model field to store ApproximateDate objects in the database
       (as a CharField because MySQLdb intercepts dates from the
       database and forces them to be datetime.date()s."""

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 10
        super(ApproximateDateField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, ApproximateDate):
            return value

        if value == 'future':
            return ApproximateDate(future=True)
        if value == 'past':
            return ApproximateDate(past=True)

        if not ansi_date_re.search(value):
            raise ValidationError('Enter a valid date in YYYY-MM-DD format.')

        year, month, day = map(int, value.split('-'))
        try:
            return ApproximateDate(year, month, day)
        except ValueError as e:
            msg = 'Invalid date: %s' % str(e)
            raise ValidationError(msg)

    # note - could rename to 'get_prep_value' but would break 1.1 compatability
    def get_db_prep_value(self, value, connection=None, prepared=False):
        if value in (None, ''):
            return ''
        if isinstance(value, ApproximateDate):
            return repr(value)
        if isinstance(value, date):
            return dateformat.format(value, "Y-m-d")
        if value == 'future':
            return 'future'
        if value == 'past':
            return 'past'
        if not ansi_date_re.search(value):
            raise ValidationError('Enter a valid date in YYYY-MM-DD format.')
        return value

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_db_prep_value(value)

    def formfield(self, **kwargs):
        defaults = {'form_class': ApproximateDateFormField}
        defaults.update(kwargs)
        return super(ApproximateDateField, self).formfield(**defaults)

# def get_db_prep_lookup(self, lookup_type, value):
# pass

# The same as the built-in Django one, but with the d/m/y ones the right way round ;)
DATE_INPUT_FORMATS = getattr(settings, 'DATE_EXTENSIONS_DATE_INPUT_FORMATS', (
    '%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y',  # '2006-10-25', '25/10/2006', '25/10/06'
    '%b %d %Y', '%b %d, %Y',  # 'Oct 25 2006', 'Oct 25, 2006'
    '%d %b %Y', '%d %b, %Y',  # '25 Oct 2006', '25 Oct, 2006'
    '%B %d %Y', '%B %d, %Y',  # 'October 25 2006', 'October 25, 2006'
    '%d %B %Y', '%d %B, %Y',  # '25 October 2006', '25 October, 2006'
))
MONTH_INPUT_FORMATS = getattr(settings, 'DATE_EXTENSIONS_MONTH_INPUT_FORMATS', (
    '%m/%Y', '%m-%Y',  # '10/2006', '10-2006'
    '%b %Y', '%Y %b',  # 'Oct 2006', '2006 Oct'
    '%B %Y', '%Y %B',  # 'October 2006', '2006 October'
))
YEAR_INPUT_FORMATS = getattr(settings, 'DATE_EXTENSIONS_YEAR_INPUT_FORMATS', (
    '%Y',  # '2006'
))


# TODO: Expand to work more like my PHP strtotime()-using function
class ApproximateDateFormField(forms.fields.Field):
    def __init__(self, max_length=10, *args, **kwargs):
        super(ApproximateDateFormField, self).__init__(*args, **kwargs)

    def clean(self, value):
        super(ApproximateDateFormField, self).clean(value)
        if value in (None, ''):
            return None
        if value == 'future':
            return ApproximateDate(future=True)
        if value == 'past':
            return ApproximateDate(past=True)
        if isinstance(value, ApproximateDate):
            return value
        value = re.sub('(?<=\d)(st|nd|rd|th)', '', value.strip())
        for format in DATE_INPUT_FORMATS:
            try:
                return ApproximateDate(*time.strptime(value, format)[:3])
            except ValueError:
                continue
        for format in MONTH_INPUT_FORMATS:
            try:
                match = time.strptime(value, format)
                return ApproximateDate(match[0], match[1], 0)
            except ValueError:
                continue
        for format in YEAR_INPUT_FORMATS:
            try:
                return ApproximateDate(time.strptime(value, format)[0], 0, 0)
            except ValueError:
                continue
        raise ValidationError('Please enter a valid date.')


DAY_MONTH_INPUT_FORMATS = getattr(settings, 'DATE_EXTENSIONS_DAY_MONTH_INPUT_FORMATS', (
    '%m-%d', '%d/%m',  # '10-25', '25/10'
    '%b %d', '%d %b',  # 'Oct 25', '25 Oct'
    '%B %d', '%d %B',  # 'October 25', '25 October'
))


# PrettyDateField - same as DateField but accepts slightly more input,
# like ApproximateDateFormField above. If initialised with future=True,
# it will assume a date without year means the current year (or the next
# year if the day is before the current date). If future=False, it does
# the same but in the past.
class PrettyDateField(forms.fields.Field):
    widget = PrettyDateInput

    def __init__(self, future=None, *args, **kwargs):
        self.future = future
        super(PrettyDateField, self).__init__(*args, **kwargs)

    def clean(self, value):
        """
        Validates that the input can be converted to a date. Returns a Python
        datetime.date object.
        """
        super(PrettyDateField, self).clean(value)
        if value in (None, ''):
            return None
        if value == 'future':
            return ApproximateDate(future=True)
        if value == 'past':
            return ApproximateDate(past=True)
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        value = re.sub('(?<=\d)(st|nd|rd|th)', '', value.strip())
        for date_input_format in DATE_INPUT_FORMATS:
            try:
                return datetime.date(*time.strptime(value, date_input_format)[:3])
            except ValueError:
                continue

        if self.future is None:
            raise ValidationError('Please enter a valid date.')

        # Allow year to be omitted. Do the sensible thing, either past or future.
        for day_month_input_format in DAY_MONTH_INPUT_FORMATS:
            try:
                t = time.strptime(value, day_month_input_format)
                month, day, yday = t[1], t[2], t[7]
                year = datetime.date.today().year
                if self.future and yday < int(datetime.date.today().strftime('%j')):
                    year += 1
                if not self.future and yday > int(datetime.date.today().strftime('%j')):
                    year -= 1
                return datetime.date(year, month, day)
            except ValueError:
                continue

        raise ValidationError('Please enter a valid date.')

