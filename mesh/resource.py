import re
from inspect import isclass
from textwrap import dedent

from scheme import *

from mesh.address import *
from mesh.constants import *
from mesh.endpoint import *
from mesh.exceptions import *
from mesh.util import *

class Configuration(object):
    """A resource configuration scheme.

    :param dict standard_endpoints: Optional, default is ``None``; a ``dict`` mapping endpoint
        names to callables which will generate a standard endpoint definition for a given
        resource and its schema. The callable should take a single :class:`Resource` argument.

    :param list default_endpoints: Optional, default is ``None``; a ``list`` indicating which
        standard endpoints provided by this configuration should be included by default on a
        resource which doesn't explicitly specify ``endpoints`` at class level.

    :param list validated_endpoints: Optional, default is ``None``; a ``list`` indicating which
        standard endpoints provided by this configuration should be subject to validation by
        validators which don't explicitly specify endpoints.

    :param Field id_field: Optional, default is ``None``; a :class:`scheme.Field` which will
        serve as the unique identifier field for resources associated with this configuration
        which do not themselves declare an identifier field. If not specified, a Integer field
        with the name "id" will be constructed for this configuration.

    :param default_controller: Optional, default is ``None``; a subclass of :class:`Controller`
        which will be used as the base class for automatically generated mock controllers under
        this configuration.
    """

    def __init__(self, standard_endpoints=None, default_endpoints=None, validated_endpoints=None,
            id_field=None, default_controller=None):

        self.default_controller = default_controller or Controller
        self.default_endpoints = default_endpoints or []
        self.id_field = id_field or Integer(name='id', nonnull=True)
        self.standard_endpoints = standard_endpoints or {}
        self.validated_endpoints = validated_endpoints or []

    def create_controller(self, resource):
        if self.default_controller:
            return type('%sController' % resource.__name__, (self.default_controller,), {
                'configuration': self,
                'resource': resource,
                'version': (resource.version, 0),
            })

def associate_resource_version(resource):
    version = resource.version
    if version is None:
        return
    
    try:
        versions = resource.versions
    except AttributeError:
        resource.versions = {version: resource}
        return

    if version not in versions:
        versions[version] = resource
    else:
        raise SpecificationError('cannot declare duplicate version of %r' % resource)

class ResourceMeta(type):
    ATTRS = ('abstract', 'composite_key', 'configuration', 'name', 'version')

    def __new__(metatype, name, bases, namespace):
        asis = namespace.pop('__asis__', False)
        if asis:
            resource = type.__new__(metatype, name, bases, namespace)
            associate_resource_version(resource)
            return resource

        base_class = None
        if namespace.get('abstract', False):
            base_class = bases[0]
            if len(bases) > 1 or base_class.name is not None:
                raise SpecificationError('abstract resource %r may only inherit from a single'
                    ' abstract base resource' % name)
        else:
            for candidate in bases:
                if getattr(candidate, 'abstract', False):
                    continue
                elif base_class is None:
                    base_class = candidate
                else:
                    raise SpecificationError('concrete resource %r must inherit from only one'
                        ' concrete resource' % name)

        if not base_class:
            raise SpecificationError('resource %r must inherit from exactly one non-abstract'
                ' base resource' % name)

        configuration = getattr(base_class, 'configuration', None)
        if not configuration:
            configuration = namespace.get('configuration', None)
        if not configuration:
            return type.__new__(metatype, name, (base_class,), namespace)
        elif not isinstance(configuration, Configuration):
            raise SpecificationError('invalid configuration')

        schema = namespace.pop('schema', {})
        if isclass(schema):
            schema = pull_class_dict(schema)
        if not isinstance(schema, dict):
            raise SpecificationError('resource %r has an invalid schema' % name)

        removed_fields = set()
        for attr in list(schema):
            if isinstance(schema[attr], Field):
                schema[attr].name = attr
            else:
                if schema[attr] is None:
                    removed_fields.add(attr)
                del schema[attr]

        requested_endpoints = namespace.pop('endpoints', None)
        if isinstance(requested_endpoints, string):
            requested_endpoints = requested_endpoints.split(' ')
        if requested_endpoints is None:
            requested_endpoints = configuration.default_endpoints

        declared_endpoints = {}
        removed_attrs = set()

        for attr in list(namespace):
            if attr not in metatype.ATTRS and not attr.startswith('_'):
                if isclass(namespace[attr]):
                    declared_endpoints[attr] = namespace.pop(attr)
                elif namespace[attr] is None:
                    removed_attrs.add(attr)
                    namespace.pop(attr)

        resource = type.__new__(metatype, name, (base_class,), namespace)
        if resource.version is not None:
            if not (isinstance(resource.version, int) and resource.version >= 1):
                raise SpecificationError('resource %r declares an invalid version' % name)

        resource.endpoints = {}
        resource.schema = {}
        resource.validators = {}

        inherited_endpoints = set()
        for base in reversed(bases):
            if hasattr(base, 'schema'):
                resource.schema.update(base.schema)
                resource.validators.update(base.validators)
                for name, endpoint in base.endpoints.items():
                    inherited_endpoints.add(endpoint)
                    resource.endpoints[name] = endpoint

        resource.schema.update(schema)
        for name in removed_fields:
            if name in resource.schema:
                del resource.schema[name]

        id_field = configuration.id_field
        if id_field.name in resource.schema:
            resource.schema[id_field.name].is_identifier = True
        elif id_field.name not in removed_fields:
            resource.schema[id_field.name] = id_field.clone(is_identifier=True)
        resource.id_field = resource.schema.get(id_field.name)

        if isinstance(resource.composite_key, string):
            resource.composite_key = resource.composite_key.split(' ')

        if resource.composite_key:
            for key in resource.composite_key:
                if key not in resource.schema:
                    raise SpecificationError('resource %r declares an invalid composite key' % name)

        for name, endpoint in declared_endpoints.items():
            resource.endpoints[name] = Endpoint.construct(resource, endpoint)

        for attr, value in namespace.items():
            if isinstance(value, classmethod):
                value = getattr(resource, attr)
                if getattr(value, '__validates__', False):
                    resource.validators[value.__name__] = value
                    delattr(resource, value.__name__)

        resource.description = dedent(resource.__doc__ or '')
        if resource.name is None:
            associate_resource_version(resource)
            return resource

        if requested_endpoints:
            for name in requested_endpoints:
                constructor = configuration.standard_endpoints.get(name)
                if constructor:
                    endpoint = resource.endpoints.get(name)
                    if endpoint and endpoint in inherited_endpoints and endpoint.auto_constructed:
                        endpoint = None
                    if not endpoint:
                        endpoint = constructor(resource)
                        if endpoint:
                            resource.endpoints[name] = endpoint
                else:
                    raise SpecificationError('resource %r requests unknown standard request %r'
                        % (resource.name, name))

        for collection in (resource.endpoints, resource.validators):
            for name in list(collection):
                if name in removed_attrs:
                    del collection[name]

        for validator in resource.validators.values():
            if validator.endpoints is None:
                set_function_attr(validator, 'endpoints', configuration.validated_endpoints)
            for endpoint_name in validator.endpoints:
                if endpoint_name in resource.endpoints:
                    resource.endpoints[endpoint_name].validators.append(validator)

        associate_resource_version(resource)
        return resource

    def __getattr__(resource, name):
        endpoints = type.__getattribute__(resource, 'endpoints')
        target = endpoints.get(name)

        if target:
            get_endpoint = lambda *args: target
        else:
            candidate = resource.configuration.standard_endpoints.get(name)
            if not candidate:
                raise AttributeError(name)
            elif isinstance(candidate, EndpointConstructor):
                get_endpoint = lambda *args: candidate(*args)
            else:
                get_endpoint = candidate

        return type(name, (object,), {
            'get_endpoint': staticmethod(get_endpoint),
        })

    def __getitem__(resource, version):
        return resource.versions[version]

    def __repr__(resource):
        if resource.name:
            return '%s(name=%r, version=%r)' % (resource.__name__, resource.name,
                resource.version)
        else:
            return resource.__name__

    def __str__(resource):
        if resource.name:
            return '%s:%d' % (resource.name, resource.version)
        else:
            return resource.__name__

    @property
    def maximum_version(resource):
        return max(resource.versions.keys())

    @property
    def minimum_version(resource):
        return min(resource.versions.keys())

    @property
    def title(resource):
        chars = []
        for char in resource.__name__:
            if char.isupper():
                chars.append(' ')
            chars.append(char)
        return ''.join(chars).strip()

    def describe(resource, controller=None, address=None, verbose=False, omissions=None):
        if address:
            address = address.clone(resource=resource.name)
        else:
            address = Address(resource=resource.name)

        description = {
            '__subject__': 'resource',
            'abstract': resource.abstract,
            'classname': resource.__name__,
            'composite_key': resource.composite_key,
            'controller': None,
            'description': resource.description,
            'id': None,
            'name': resource.name,
            'resource': identify_class(resource),
            'title': resource.title,
        }

        if address.bundle:
            description['id'] = str(address)

        if controller:
            description['controller'] = identify_class(controller)
            description['version'] = controller.version
        else:
            description['version'] = (resource.version, 0)

        description['schema'] = {}
        for name, field in resource.schema.items():
            if omissions and name in omissions:
                field = Field(name=name)
            description['schema'][name] = field.describe(verbose=verbose)

        description['endpoints'] = {}
        for name, endpoint in resource.endpoints.items():
            description['endpoints'][name] = endpoint.describe(address, verbose, omissions)

        return description

    def enumerate_endpoints(resource, address=None):
        if not address:
            address = Address()

        for name, endpoint in resource.endpoints.items():
            yield endpoint.attach(address), endpoint

    def filter_schema(resource, all=False, **params):
        schema = {}
        for name, field in resource.schema.items():
            candidate = field.filter(all, **params)
            if candidate:
                schema[name] = candidate

        return schema

    def mirror_schema(resource, exclude=None):
        if isinstance(exclude, string):
            exclude = exclude.split(' ')

        schema = {}
        for name, field in resource.schema.items():
            if not exclude or name not in exclude:
                schema[name] = field.clone()

        return schema

    def reconstruct(resource, description, configuration=None):
        if not (resource.configuration or configuration):
            raise TypeError('cannot reconstruct resource without configuration')

        namespace = {
            '__asis__': True,
            'composite_key': description.get('composite_key'),
            'name': description['name'],
            'endpoints': {},
            'schema': {},
            'validators': {},
            'version': description['version'][0]}

        if configuration:
            namespace['configuration'] = configuration

        schema = description.get('schema')
        if isinstance(schema, dict):
            for name, field in schema.items():
                namespace['schema'][name] = Field.reconstruct(field)

        resource = type(str(description['title']), (resource,), namespace)
        resource.id_field = resource.schema.get(resource.configuration.id_field.name)

        endpoints = description.get('endpoints')
        if isinstance(endpoints, dict):
            for name, endpoint in endpoints.items():
                namespace['endpoints'][name] = Endpoint.reconstruct(resource, endpoint)

        return resource

@with_metaclass(ResourceMeta)
class Resource(object):
    """A resource definition."""

    configuration = None

    abstract = False
    composite_key = None
    name = None
    version = None

class ControllerMeta(type):
    def __new__(metatype, name, bases, namespace):
        controller = type.__new__(metatype, name, bases, namespace)
        metatype.__metaconstruct__(controller, name, bases, namespace)
        return controller

    @staticmethod
    def __metaconstruct__(controller, name, bases, namespace):
        resource = controller.resource
        if resource is not None:
            version = controller.version
            if not (isinstance(resource, type) and issubclass(resource, Resource)):
                raise SpecificationError('controller %r specifies a invalid resource' % name)

            if not (isinstance(version, tuple) and len(version) == 2 and isinstance(version[0], int)
                    and version[0] >= 1 and isinstance(version[1], int) and version[1] >= 0):
                raise SpecificationError('controller %r declares an invalid version: %r'
                    % (name, version))

            if version[0] in resource.versions:
                resource = controller.resource = resource.versions[version[0]]
            else:
                raise SpecificationError('controller %r specifies an unknown version %r of'
                    ' resource %r' % (name, version[0], resource.name))
        elif controller.version is not None:
            raise SpecificationError('abstract controller %s must not specify a version' % name)
        else:
            return controller

        controller.endpoints = {}
        for endpoint in resource.endpoints.keys():
            implementation = getattr(controller, endpoint, None)
            if implementation:
                controller.endpoints[endpoint] = implementation

        versions = getattr(controller, 'versions', None)
        if versions is None:
            versions = controller.versions = {}

        if controller.version in versions:
            raise SpecificationError('controller %r specifies a duplicate version' % name)
        elif versions:
            resources = set([resource.name]) | set(v.resource.name for v in versions.values())
            if len(resources) != 1:
                raise SpecificationError('mismatching resources')

        versions[controller.version] = controller
        controller.version_string = '%d.%d' % controller.version

        controller.__construct__()

    def __repr__(controller):
        name = controller.__name__
        if controller.resource:
            return '%s[%s/%s]' % (name, controller.resource.name, controller.version_string)
        else:
            return name

    @property
    def maximum_version(controller):
        return max(controller.versions.keys())

    @property
    def minimum_version(controller):
        return min(controller.versions.keys())

@with_metaclass(ControllerMeta)
class Controller(object):
    """A resource controller."""

    resource = None
    version = None

    @classmethod
    def __construct__(cls):
        pass

    def acquire(self, subject):
        """Acquires and returns the backend instance for the implemented resource identified
        by ``subject``. Mesh treats both ``subject`` and the returned value opaquely."""

        raise NotImplementedError()

    def dispatch(self, endpoint, request, response, subject, data):
        """Dispatches a request to this controller."""

        implementation = self.endpoints.get(endpoint.name)
        if implementation:
            content = implementation(self, request, response, subject, data)
            if content and content is not response:
                response(content)
        elif not self._dispatch_request(endpoint, request, response, subject, data):
            raise ValueError('not implementation available for %r' % definition.name)

    def _dispatch_request(self, endpoint, request, response, subject, data):
        return False
