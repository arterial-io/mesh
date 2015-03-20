import logging
import re
from copy import deepcopy
from inspect import isclass
from textwrap import dedent

from scheme import INBOUND, OUTBOUND, Field, Structure
from scheme.exceptions import *
from scheme.util import format_structure

from mesh.constants import *
from mesh.exceptions import *
from mesh.util import LogHelper, pull_class_dict, string

__all__ = ('Endpoint', 'EndpointConstructor', 'EndpointResponse', 'Mediator', 'validator')

log = LogHelper(__name__)

class EndpointConstructor(object):
    """An endpoint constructor."""

    def __call__(self, resource, declaration=None):
        return self.construct(resource, declaration)

    def construct(self, resource, declaration=None):
        raise NotImplementedError()

    def get_endpoint(self, resource, declaration=None):
        return self.construct(resource, declaration)

class EndpointResponse(object):
    """A response definition for a resource endpoint.

    :param schema: Optional, default is ``None``; a schema describing the data returned in this
        response, specified as either a :class:`scheme.fields.Structure` instance or a ``dict``
        instance (which will be used to created a ``Structure`` instance). If ``None``, this
        response returns no data.

    :param str status: Optional, default is ``None``; ...
    """

    def __init__(self, schema=None, status=None):
        if isinstance(schema, dict):
            schema = Structure(schema)
        if schema and not schema.name:
            schema.name = 'response'

        self.schema = schema
        self.status = status

    def __repr__(self):
        if self.status is self:
            raise Exception('!!!')
        return 'EndpointResponse(status=%r)' % self.status

    def describe(self, verbose=False, omissions=None):
        if omissions:
            def omit(field):
                if isinstance(field, Structure):
                    candidate = field.replace(dict((k, Field(name=k)) for k in omissions))
                    if candidate is not field:
                        return candidate

        description = {'status': self.status, 'schema': None}
        if self.schema:
            schema = self.schema
            if omissions:
                schema = schema.transform(omit)
            description['schema'] = schema.describe(SCHEME_PARAMETERS, verbose)
        return description

class Endpoint(object):
    """An endpoint definition for a resource."""

    ATTRS = {
        'batch': False,
        'description': None,
        'method': None,
        'specific': False,
        'subject_required': True,
        'title': None,
        'verbose': False,
    }

    def __init__(self, resource=None, name=None, method=None, schema=None, responses=None,
            specific=False, description=None, title=None, auto_constructed=False, batch=False,
            subject_required=True, validators=None, metadata=None, verbose=False, **params):

        self.auto_constructed = auto_constructed
        self.batch = batch
        self.description = description
        self.metadata = metadata or {}
        self.method = method
        self.name = name
        self.resource = resource
        self.schema = schema
        self.specific = specific
        self.subject_required = subject_required
        self.title = title
        self.validators = validators or []
        self.verbose = verbose

        self.responses = {}
        if responses:
            for status, response in responses.items():
                if not isinstance(response, EndpointResponse):
                    response = EndpointResponse(response)
                if response.status is None:
                    response.status = status
                self.responses[status] = response

    def __repr__(self):
        return 'Endpoint(resource=%r, name=%r)' % (self.resource, self.name)

    def __str__(self):
        return '%s:%s' % (self.resource, self.name)

    def attach(self, address):
        address = address.clone(resource=self.resource.name, endpoint=self.name)
        if self.specific:
            address.subject = True
        return address

    @classmethod
    def construct(cls, resource, declaration):
        bases = declaration.__bases__
        if isclass(declaration) and bases:
            params = cls._pull_endpoint(resource, bases[0], declaration)
        else:
            params = {}

        params.update(pull_class_dict(declaration, cls.ATTRS.keys()))
        if 'responses' not in params:
            params['responses'] = {}

        schema = getattr(declaration, 'schema', None)
        if schema is not None:
            if isinstance(schema, dict):
                for name, field in schema.items():
                    if isinstance(field, string):
                        field = resource.schema.get(field)
                        if field:
                            schema[name] = field
                schema = Structure(schema)
            if not schema.name:
                schema.name = 'endpoint'
            params['schema'] = schema

        fields = getattr(declaration, 'fields', None)
        if fields:
            if 'schema' not in params:
                params['schema'] = Structure({}, name='endpoint')

            for name, field in fields.items():
                if isinstance(field, Field):
                    if not field.name:
                        field.name = name
                    params['schema'].insert(field, True)
                elif isinstance(field, string):
                    field = resource.schema.get(field)
                    if field:
                        if field.name != name:
                            field = field.clone(name=name)
                        params['schema'].insert(field, True)
                    else:
                        raise SpecificationError()
                elif field is None:
                    params['schema'].remove(name)
                else:
                    raise TypeError(field)

        responses = getattr(declaration, 'responses', {})
        for status, response in responses.items():
            if not isinstance(response, EndpointResponse):
                response = EndpointResponse(response)
            response.status = status
            params['responses'][status] = response

        description = params.get('description')
        if not description and declaration.__doc__:
            params['description'] = dedent(declaration.__doc__)

        metadata = getattr(declaration, 'metadata', None)
        if metadata:
            if 'metadata' in params:
                params['metadata'].update(metadata)
            else:
                params['metadata'] = metadata

        return cls(resource=resource, name=declaration.__name__, **params)

    def describe(self, address=None, verbose=False, omissions=None):
        if omissions:
            def omit(field):
                if isinstance(field, Structure):
                    return field.replace(dict((k, Field(name=k)) for k in omissions))

        description = {'name': self.name}
        for attr, default in self.ATTRS.items():
            value = getattr(self, attr, default)
            if verbose or value is not default:
                description[attr] = value
        
        if address:
            address = self.attach(address)
            description.update(address=address.signature, path=address.prefixed_path)

        description['schema'] = None
        if self.schema:
            schema = self.schema
            if omissions:
                schema = schema.transform(omit)
            description['schema'] = schema.describe(SCHEME_PARAMETERS, verbose)

        description['responses'] = {}
        for status, response in self.responses.items():
            description['responses'][status] = response.describe(verbose, omissions)

        return description

    def process(self, controller, request, response, mediators=None):
        #self._log_request(request)

        if mediators:
            for mediator in mediators:
                try:
                    mediator.before_validation(self, request, response)
                    if response.status:
                        return response
                except StructuralError as exception:
                    error = exception.serialize()
                    log('info', 'request to %s failed during mediator', str(self))
                    return response(INVALID, error)

        instance = controller()

        subject = None
        if self.specific:
            if request.address.subject is not None:
                subject = instance.acquire(request.address.subject)
                if not subject and self.subject_required:
                    log('info', 'request to %r specified unknown subject %r', str(self),
                        request.address.subject)
                    return response(GONE)
            else:
                return response(BAD_REQUEST)
        elif request.address.subject:
            log('info', 'request to %r improperly specified a subject', str(self))
            return response(BAD_REQUEST)

        data = None
        if self.schema:
            try:
                data = self.schema.process(request.data, INBOUND, request.serialized)
            except StructuralError as exception:
                error = exception.serialize()
                log('info', 'request to %r failed schema validation', str(self))
                response(INVALID, error)

            if not response.status and self.validators:
                try:
                    self.validate(data)
                except StructuralError as exception:
                    error = exception.serialize()
                    log('info', 'request to %r failed resource validation', str(self))
                    response(INVALID, error)
        elif request.data:
            log('info', 'request to %r improperly specified data', str(self))
            return response(BAD_REQUEST)

        if not response.status:
            try:
                instance.dispatch(self, request, response, subject, data)
                if not response.status:
                    response.status = OK
            except StructuralError as exception:
                error = exception.serialize()
                log('exception', 'request to %r failed controller invocation', str(self))
                response(INVALID, error)
            except RequestError as exception:
                return response(exception.status, exception.content)

        definition = self.responses.get(response.status)
        if not definition:
            if response.status in ERROR_STATUS_CODES and not response.data:
                return response
            else:
                log('error', 'response for %r has undeclared status code %s',
                    str(self), response.status)
                return response(SERVER_ERROR)

        if definition.schema:
            try:
                response.data = definition.schema.process(response.data,
                    OUTBOUND, request.serialized)
            except StructuralError as exception:
                log('error', 'response for %r failed schema validation\n%s\n%s',
                    str(self), exception.format_errors(), format_structure(response.data))
                response.data = None
                return response(SERVER_ERROR)
        elif response.data:
            log('error', 'response for %r improperly specified data', str(self))
            return response(SERVER_ERROR)

    @classmethod
    def reconstruct(cls, resource, description):
        description['schema'] = Field.reconstruct(description['schema'])
        for status, response in description['responses'].items():
            if 'schema' in response:
                response['schema'] = Field.reconstruct(response['schema'])
            description['responses'][status] = EndpointResponse(**response)

        return cls(resource, **description)

    def validate(self, data):
        if self.batch:
            errors = []
            for item in data:
                try:
                    self._validate_data(item)
                except StructuralError as exception:
                    errors.append(exception)
                else:
                    errors.append(None)

            if any(errors):
                raise ValidationError(structure=errors)
        else:
            self._validate_data(data)

    @classmethod
    def _pull_endpoint(cls, resource, endpoint, declaration=None):
        try:
            get_endpoint = endpoint.get_endpoint
        except AttributeError:
            pass
        else:
            endpoint = get_endpoint(resource, declaration)

        params = pull_class_dict(endpoint, cls.ATTRS.keys())

        schema = getattr(endpoint, 'schema', None)
        if schema:
            params['schema'] = deepcopy(schema)

        responses = getattr(endpoint, 'responses', None)
        if responses:
            params['responses'] = deepcopy(responses)

        metadata = getattr(endpoint, 'metadata', None)
        if metadata:
            params['metadata'] = deepcopy(metadata)

        return params

    def _validate_data(self, data):
        error = ValidationError(structure={})
        for validator in self.validators:
            try:
                validator(data)
            except StructuralError as exception:
                attr = validator.attr
                if attr:
                    if attr in error.structure:
                        error.structure[attr].merge(exception)
                    else:
                        error.structure[attr] = exception
                else:
                    error.merge(exception)

        if error.substantive:
            raise error

class Mediator(object):
    """A request mediator."""

    def before_validation(self, definition, request, response):
        pass

def validator(attr=None, endpoints=None):
    """Marks the decorated method as an endpoint validator.

    :param string attr: Optional, default is ``None``; if specified, the name of the field within
        the schema of the resource that will receive validation errors raised by this validator.
    :param endpoints: Optional.

    The decorated method must be implemented as a class method, taking a class as its first
    argument, but must not be decorated with ``@classmethod``; ``validator`` will convert the
    method to a classmethod itself, as otherwise the method can not be annotated. The decorated
    method will receive a single positional argument, the received data, which will already have
    passed standard validation, and should raise :exc:`ValidationError` is warranted.
    """

    if isinstance(endpoints, string):
        endpoints = endpoints.split(' ')
    elif isinstance(endpoints, (list, tuple)):
        endpoints = list(endpoints)
    elif endpoints is not None:
        endpoints = [endpoints]

    if endpoints:
        for i in range(len(endpoints)):
            if isclass(endpoints[i]):
                endpoints[i] = endpoints[i].__name__

    def decorator(method):
        method.__validates__ = True
        method.attr = attr
        method.endpoints = endpoints
        return classmethod(method)
    return decorator
