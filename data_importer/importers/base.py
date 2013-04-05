#!/usr/bin/python
# encoding: utf-8
import csv
from django.db import transaction


def objclass2dict(objclass):
    """
    Meta is a objclass on python 2.7 and no have __dict__ attribute.

    This method convert one objclass to one lazy dict without AttributeError
    """
    class Dict(dict):
        def __init__(self, data={}):
            super(Dict, self).__init__(data)
            self.__dict__ = dict(self.items())

        def __getattr__(self, key):
            try:
                return self.__getattribute__(key)
            except AttributeError:
                return False

    obj_list = [i for i in dir(objclass) if not str(i).startswith("__")]
    obj_values = []
    for objitem in obj_list:
        obj_values.append(getattr(objclass, objitem))
    return Dict(zip(obj_list, obj_values))


class BaseImporter(object):
    """
    Base Importer method to create simples importes CSV files.

    set_reader: can be override to create new importers files
    """
    _error = []
    _cache = ()
    _cleaned_data = ()
    _fields = []
    _reader = None
    _excluded = False
    _readed = False

    def __new__(cls, **kargs):
        """
        Provide custom methods in subclass Meta
        """
        if hasattr(cls, "Meta"):
            cls.Meta = objclass2dict(cls.Meta)
        return super(BaseImporter, cls).__new__(cls)

    def __init__(self, source=None):
        self.start_fields()
        if source:
            self.source = source
            self.set_reader()

    class Meta:
        """
        Importer configurations
        """

    @property
    def source(self):
        """
        Return source opened
        """
        return self._source

    @source.setter
    def source(self, source):
        """
        Open source to reader
        """
        if isinstance(source, file):
            self._source = source
        elif isinstance(source, list):
            self._source = source
        elif hasattr(source, 'file'):
            self._source = open(source.file.name, 'rb')
        elif hasattr(source, 'name'):
            self._source = open(source.name, 'rb')
        else:
            self._source = source
            # raise ValueError('Invalid Source')

    @property
    def meta(self):
        """
        Is same to use .Meta
        """
        if hasattr(self, 'Meta'):
            return self.Meta
        return {}

    def start_fields(self):
        """
        Initial function to find fields or headers values.
        This values will be used on process to clean_ and save method

        If this method not have fields and have Meta.model this method
        will use model fields to populate content without id
        """
        if self.Meta.model and not hasattr(self, 'fields'):
            all_models_fields = [i.name for i in self.Meta.model._meta.fields if i.name != 'id']
            self.fields = all_models_fields
        if self.Meta.exclude and not self._excluded:
            self._excluded = True
            for exclude in self.Meta.exclude:
                if exclude in self.fields:
                    self.fields.remove(exclude)

    @property
    def errors(self):
        """
        Show errors catch by clean_ methods
        """
        return self._error

    def is_valid(self):
        """
        Clear content and return False if not have errors
        """
        if not self.cleaned_data:
            self.cleaned_data
        return not any(self._error)

    def set_reader(self):
        """
        Method responsable to convert file content into a list with same values that
        have fields

            fields: ['myfield1', 'myfield2']

            response: [['value_myfield1', 'value_myfield2'],
                        ['value2_myfield1', 'value2_myfield2']]
        """
        self._reader = csv.reader(self.source, delimiter=self.meta.get('delimiter', ';'))

    def _clean_content(self, row, values):
        """
        Read clean_ functions from importer and return tupla with row number, field and value
        """
        values = dict(zip(self.fields, values))
        for k, v in values.items():
            if hasattr(self, 'clean_%s' % k):
                clean_function = getattr(self, 'clean_%s' % k)
                if self.Meta.raise_errors:
                    values[k] = clean_function(v)
                else:
                    try:
                        values[k] = clean_function(v)
                    except Exception, e:
                        self._error.append((row, repr(e)))

        return (row, values)

    @property
    def cleaned_data(self):
        """
        Return tupla with data cleaned
        """
        if self._readed:
            return self._cleaned_data

        try:
            self.pre_clean()
        except Exception, e:
            self._error.append(('__pre_clean__', repr(e)))

        for data in self._lines():
            self._cleaned_data += (data, )

        try:
            self.clean()
        except Exception, e:
            self._error.append(('__clean_all__', repr(e)))

        try:
            self.post_clean()
        except Exception, e:
            self._error.append(('__post_clean__', repr(e)))

        self._readed = True
        return self._cleaned_data

    def pre_clean(self):
        """
        Executed before all clean methods
        Important: pre_clean dont have cleaned_data content
        """

    def post_clean(self):
        """
        Excuted after all clean method
        """

    def clean(self):
        """
        Custom clean method
        """

    def _lines(self):
        """
        Create cleaned_data content
        """
        for row, values in enumerate(self._reader):
            if self.Meta.ignore_first_line:
                row -= 1
            if row == -1:
                pass
            else:
                yield self._clean_content(row, values)

    def cache(self, value, obj=None):
        """
        TODO: not implemented
        """
        cache = [i[1] for i in self._cache if value == i[0]]
        if cache:
            return cache
        else:
            self._cache += (value, obj)
        return value

    def save(self, instance=None):
        if not instance:
            instance = self.Meta.model

        if not instance:
            raise AttributeError("Invalid instance model")

        if self.Meta.transaction:
            with transaction.atomic():
                for row, data in self.cleaned_data:
                    print data
                    record = instance(**data)
                    record.save()
                try:
                    transaction.commit()
                except Exception, e:
                    self._error.append(('__trasaction__', repr(e)))
                    transaction.rollback()
        else:
            for row, data in self.cleaned_data:
                print data
                record = instance(**data)
                record.save()