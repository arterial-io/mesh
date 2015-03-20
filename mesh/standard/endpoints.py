from scheme import *

from mesh.constants import *
from mesh.exceptions import *
from mesh.endpoint import *
from mesh.resource import *
from mesh.util import string

def clone_field(field, name=None, description=None):
    return field.clone(name=name, description=description, nonnull=True, default=None,
        required=False, notes=None, readonly=False, deferred=False, sortable=False,
        ignore_null=False, operators=None)

class OperatorConstructor(object):
    operators = {
        'equal': 'Equals',
        'iequal': 'Case-insensitive equals.',
        'not': 'Not equal.',
        'inot': 'Case-insensitive not equal.',
        'prefix': 'Prefix search.',
        'iprefix': 'Case-insensitive prefix search.',
        'suffix': 'Suffix search.',
        'isuffix': 'Case-insensitive suffix search.',
        'contains': 'Contains.',
        'icontains': 'Case-insensitive contains.',
        'gt': 'Greater then.',
        'gte': 'Greater then or equal to.',
        'lt': 'Less then.',
        'lte': 'Less then or equal to.',
        'null': 'Is null.',
        'in': 'In given values.',
        'notin': 'Not in given values.',
    }

    @classmethod
    def construct(cls, operators, field):
        supported = field.operators
        if isinstance(supported, string):
            supported = supported.split(' ')

        for operator in supported:
            if isinstance(operator, Field):
                operators[operator.name] = operator
                continue

            description = cls.operators.get(operator)
            if description:
                constructor = getattr(cls, '_construct_%s_operator' % operator, None)
                if constructor:
                    operator_field = constructor(field, description)
                else:
                    name = '%s__%s' % (field.name, operator)
                    operator_field = clone_field(field, name, description)
                operators[operator_field.name] = operator_field

        return operators

    @classmethod
    def _construct_equal_operator(cls, field, description):
        return clone_field(field, field.name, description)

    @classmethod
    def _construct_in_operator(cls, field, description):
        return Sequence(clone_field(field), name='%s__in' % field.name,
            description=description, nonnull=True)

    @classmethod
    def _construct_notin_operator(cls, field, description):
        return Sequence(clone_field(field), name='%s__notin' % field.name,
            description=description, nonnull=True)

    @classmethod
    def _construct_null_operator(cls, field, description):
        return Boolean(name='%s__null' % field.name, description=description, nonnull=True)

class StandardConstructor(EndpointConstructor):
    def _construct_fields_field(self, fields, original=None, field_name='fields',
            include_identifier=True,
            description='The exact fields which should be returned in this request.'):

        tokens = []
        if original:
            tokens.extend(original.item.enumeration)

        for name, field in fields.items():
            if include_identifier or not field.is_identifier:
                tokens.append(name)

        return Sequence(Enumeration(sorted(tokens), nonnull=True), name=field_name,
            unique=True, description=description)

    def _construct_exclude_field(self, fields, original=None, field_name='exclude'):
        return self._construct_fields_field(fields, original, field_name, False,
            'Fields which should not be returned for this request.')

    def _construct_include_field(self, fields, original=None, field_name='include'):
        return self._construct_fields_field(fields, original, field_name, True,
            'Fields which should be returned for this request.')

    def _construct_responses(self, declaration, valid_schema, invalid_schema=Errors, 
            valid=[OK], invalid=[INVALID]):

        if not isinstance(valid_schema, Structure):
            valid_schema = Structure(valid_schema)

        if declaration:
            valid = getattr(declaration, 'valid_responses', valid)
            invalid = getattr(declaration, 'invalid_responses', invalid)

        responses = {}
        for valid_status in valid:
            responses[valid_status] = EndpointResponse(valid_schema)
        for invalid_status in invalid:
            responses[invalid_status] = EndpointResponse(invalid_schema)

        return responses

    def _construct_returning(self, resource):
        return Sequence(Enumeration(sorted(resource.schema.keys()), nonnull=True))

    def _filter_schema_for_response(self, resource):
        id_field = resource.id_field
        schema = {}

        for name, field in resource.schema.items():
            if name == id_field.name:
                schema[name] = field.clone(required=True)
            elif field.required:
                schema[name] = field.clone(required=False)
            else:
                schema[name] = field

        return schema

    def _is_returned(self, field, endpoint):
        returned = field.returned
        if not returned:
            return False

        if isinstance(returned, string):
            returned = returned.split(' ')
        return (endpoint in returned)

    def _supports_returning(self, resource, declaration):
        supported = False
        if declaration:
            supported = getattr(declaration, 'support_returning', False)
            if supported and RETURNING in resource.schema:
                raise Exception('cannot support returning for this resource')

        return supported

class ConstructCreateEndpoint(StandardConstructor):
    def construct(self, resource, declaration=None):
        endpoint_schema = {}
        for name, field in resource.filter_schema(readonly=False).items():
            if field.is_identifier:
                if field.oncreate is True:
                    endpoint_schema[name] = field.clone(ignore_null=True)
            elif field.oncreate is not False:
                endpoint_schema[name] = field

        support_returning = self._supports_returning(resource, declaration)
        if support_returning:
            endpoint_schema[RETURNING] = self._construct_returning(resource)

        response_schema = {}
        for name, field in resource.schema.items():
            if field.is_identifier or self._is_returned(field, 'create'):
                response_schema[name] = field.clone(required=True)
            elif support_returning:
                response_schema[name] = field.clone(required=False)

        responses = self._construct_responses(declaration, response_schema)
        return Endpoint(resource, 'create', POST,
            schema=Structure(endpoint_schema, name='resource'),
            responses=responses,
            title='Creating a new %s' % resource.title.lower(),
            auto_constructed=True)

class ConstructDeleteEndpoint(StandardConstructor):
    def construct(self, resource, declaration=None):
        id_field = resource.id_field
        response_schema = Structure({
            id_field.name: id_field.clone(required=True),
        })

        responses = self._construct_responses(declaration, response_schema)
        return Endpoint(resource, 'delete', DELETE,
            responses=responses,
            specific=True,
            title='Deleting a specific %s' % resource.title.lower(),
            auto_constructed=True)

class ConstructGetEndpoint(StandardConstructor):
    def construct(self, resource, declaration=None):
        fields = self._filter_schema_for_response(resource)
        endpoint_schema = {
            'exclude': self._construct_exclude_field(fields),
            'fields': self._construct_fields_field(fields),
            'include': self._construct_include_field(fields),
        }

        responses = self._construct_responses(declaration, fields)
        return Endpoint(resource, 'get', GET,
            schema=Structure(endpoint_schema),
            responses=responses,
            specific=True,
            title='Getting a specific %s' % resource.title.lower(),
            auto_constructed=True)

class ConstructPutEndpoint(StandardConstructor):
    def construct(self, resource, declaration=None):
        endpoint_schema = {}
        for name, field in resource.filter_schema(readonly=False).items():
            if not field.is_identifier and field.onput is not False:
                endpoint_schema[name] = field

        support_returning = self._supports_returning(resource, declaration)
        if support_returning:
            endpoint_schema[RETURNING] = self._construct_returning(resource)

        response_schema = {}
        for name, field in resource.schema.items():
            if field.is_identifier or self._is_returned(field, 'put'):
                response_schema[name] = field.clone(required=True)
            elif support_returning:
                response_schema[name] = field.clone(required=False)

        responses = self._construct_responses(declaration, response_schema)
        return Endpoint(resource, 'put', PUT,
            schema=Structure(endpoint_schema, name='resource'),
            responses=responses,
            specific=True,
            subject_required=False,
            title='Putting a specific %s' % resource.title.lower(),
            auto_constructed=True)

class ConstructQueryEndpoint(StandardConstructor):
    def construct(self, resource, declaration=None):
        fields = self._filter_schema_for_response(resource)
        endpoint_schema = {
            'exclude': self._construct_exclude_field(fields),
            'fields': self._construct_fields_field(fields),
            'include': self._construct_include_field(fields),
            'limit': Integer(minimum=0, description='The maximum number of resources to return.'),
            'offset': Integer(minimum=0, default=0,
                description='The offset of the first resource to return.'),
            'total': Boolean(default=False, nonnull=True,
                description='If true, only return the total for this query.'),
        }

        tokens = []
        for name, field in fields.items():
            if field.sortable:
                for suffix in ('', '+', '-'):
                    tokens.append(name + suffix)

        if tokens:
            endpoint_schema['sort'] = Sequence(Enumeration(sorted(tokens), nonnull=True),
                description='The sort order for this query.')

        operators = {}
        for name, field in fields.items():
            if field.operators:
                OperatorConstructor.construct(operators, field)

        if declaration:
            additional_operators = getattr(declaration, 'operators', None)
            if additional_operators:
                operators.update(additional_operators)

        if operators:
            endpoint_schema['query'] = Structure(operators,
                description='The query by which to filter resources.')

        response_schema = Structure({
            'total': Integer(nonnull=True, minimum=0,
                description='The total number of resources matching this query.'),
            'resources': Sequence(Structure(fields), nonnull=True),
        })

        responses = self._construct_responses(declaration, response_schema)
        return Endpoint(resource, 'query', GET,
            schema=Structure(endpoint_schema),
            responses=responses,
            title='Querying %s' % pluralize(resource.title.lower()),
            auto_constructed=True)

class ConstructUpdateEndpoint(StandardConstructor):
    def construct(self, resource, declaration=None):
        endpoint_schema = {}
        for name, field in resource.filter_schema(readonly=False).items():
            if not field.is_identifier and field.onupdate is not False:
                if field.required:
                    field = field.clone(required=False)
                endpoint_schema[name] = field

        support_returning = self._supports_returning(resource, declaration)
        if support_returning:
            endpoint_schema[RETURNING] = self._construct_returning(resource)

        response_schema = {}
        for name, field in resource.schema.items():
            if field.is_identifier or self._is_returned(field, 'update'):
                response_schema[name] = field.clone(required=True)
            elif support_returning:
                response_schema[name] = field.clone(required=False)

        responses = self._construct_responses(declaration, response_schema)
        return Endpoint(resource, 'update', POST,
            schema=Structure(endpoint_schema, name='resource'),
            responses=responses,
            specfic=True,
            title='Updating a specific %s' % resource.title.lower(),
            auto_constructed=True)

DEFAULT_ENDPOINTS = ['create', 'delete', 'get', 'query', 'update']
STANDARD_ENDPOINTS = {
    'create': ConstructCreateEndpoint(),
    'delete': ConstructDeleteEndpoint(),
    'get': ConstructGetEndpoint(),
    'put': ConstructPutEndpoint(),
    'query': ConstructQueryEndpoint(),
    'update': ConstructUpdateEndpoint(),
}
VALIDATED_ENDPOINTS = ['create', 'put', 'update']
