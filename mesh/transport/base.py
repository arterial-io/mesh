import re

from scheme.fields import Field
from scheme import Format, formats

from mesh.address import *
from mesh.bundle import *
from mesh.constants import *
from mesh.exceptions import *
from mesh.util import subclass_registry

__all__ = ('Client', 'Request', 'Response', 'Server')

INTROSPECTION_PATH_EXPR = r"""(?x)^%s
    /(?P<bundle>[\w.]+)
    /_(?P<request>[\w.]+)
    (?:[!](?P<format>\w+))?
    /?$"""

class Request(object):
    """A mesh request."""

    token = 'mesh'

    def __init__(self, address=None, data=None, context=None, mimetype=None,
            identity=None, serialized=False):

        self.address = address
        self.context = context
        self.data = data
        self.identity = identity
        self.mimetype = mimetype
        self.serialized = serialized

    def __repr__(self):
        aspects = []
        if self.address:
            aspects.append(repr(self.address.address))
        if self.mimetype:
            aspects.append(repr(self.mimetype))
        if self.identity:
            aspects.append(repr(self.identity))

        return '%s(%s)' % (type(self).__name__, ', '.join(aspects))

    def __str__(self):
        address = self.address
        return '[%s: %s %s]' % (self.token, self.identity or '-',
            str(address) if address else '-')

class Response(object):
    """A mesh response."""

    def __init__(self, status=None, data=None, context=None, mimetype=None):
        self.context = context
        self.data = data
        self.mimetype = mimetype
        self.status = status

    def __call__(self, status=None, data=None):
        return self.construct(status, data)

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.status)

    @property
    def ok(self):
        return (self.status in VALID_STATUS_CODES)

    def construct(self, status=None, data=None):
        if status in STATUS_CODES:
            self.status = status
        else:
            data = status

        if data is not None:
            self.data = data
        return self

    def unserialize(self):
        if self.data and self.mimetype:
            return Format.unserialize(self.data, self.mimetype)
        else:
            return self.data

class Server(object):
    """A mesh server."""

    AvailableFormats = (formats.Json,)
    DefaultFormat = None

    def __init__(self, bundles, default_format=None, available_formats=None, mediators=None):
        self.bundles = {}
        for bundle in bundles:
            if isinstance(bundle, Bundle):
                if bundle.name not in self.bundles:
                    self.bundles[bundle.name] = bundle
                else:
                    raise ValueError(bundles)
            else:
                raise TypeError(bundle)

        self.default_format = default_format or self.DefaultFormat
        self.mediators = mediators

        self.formats = {}
        for format in (available_formats or self.AvailableFormats):
            self.formats[format.name] = self.formats[format.mimetype] = format

    def dispatch(self):
        raise NotImplementedError()

class Client(object):
    """An API client."""

    DefaultFormat = None
    StandardFormats = (formats.Json, formats.UrlEncoded)

    clients = {}

    def __init__(self, specification=None, context=None, format=None, formats=None):
        if isinstance(specification, Bundle):
            specification = specification.specify()
        elif isinstance(specification, dict):
            specification = Specification(specification)

        self.context = context or {}
        self.format = format or self.DefaultFormat
        self.formats = {}
        self.name = None
        self.specification = specification

        if specification:
            self.name = specification.name

        for format in (formats or self.StandardFormats):
            for key in (format, format.name, format.mimetype):
                self.formats[key] = format

    def execute(self, resource, endpoint, subject=None, data=None, format=None, context=None):
        raise NotImplementedError()

    def extract(self, resource, endpoint, subject, sparse=True):
        endpoint = self.get_endpoint(resource, endpoint)
        return endpoint['schema'].extract(subject, sparse=sparse)

    @classmethod
    def get_client(cls, name):
        if isinstance(name, Specification):
            name = name.name
        return cls.clients.get(name)

    def get_endpoint(self, address):
        return self.specification.find(address)

    def register(self):
        self.clients[self.name] = self
        return self

    def unregister(self):
        if self.clients.get(self.name) is self:
            del self.clients[self.name]
        return self

    def _construct_context(self, additional=None):
        context = self.context
        if callable(context):
            context = context()
        if context is None:
            context = {}

        if additional:
            context = context.copy()
            context.update(additional)

        return context
