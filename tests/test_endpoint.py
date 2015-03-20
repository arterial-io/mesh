from unittest import TestCase

from mesh.address import *
from mesh.constants import *
from mesh.endpoint import *
from mesh.exceptions import *
from mesh.transport.base import *
from scheme import *
from scheme.common import Errors

class TestEndpointResponse(TestCase):
    def test_construction(self):
        response = EndpointResponse()
        self.assertIs(response.schema, None)
        self.assertEqual(response.status, None)

        for argument in (Structure({}), {}):
            response = EndpointResponse(argument)
            self.assertIsInstance(response.schema, Structure)
            self.assertEqual(response.schema.name, 'response')

    def test_description(self):
        response = EndpointResponse(status=OK)
        self.assertEqual(response.describe(), {'status': OK, 'schema': None})

        response = EndpointResponse(Structure({}), OK)
        description = response.describe()
        self.assertEqual(description['status'], OK)
        self.assertIsInstance(description['schema'], dict)

class TestEndpoint(TestCase):
    def test_declarative_construction(self):
        class resource:
            schema = {'referenced': Integer(name='referenced')}

        class operation:
            schema = {'referenced': 'referenced'}
            title = 'operation'
            responses = {
                OK: EndpointResponse(),
                PARTIAL: {},
            }
            metadata = {'name': 'value'}

        endpoint = Endpoint.construct(resource, operation)

        self.assertFalse(endpoint.auto_constructed)
        self.assertFalse(endpoint.batch)
        self.assertIsNone(endpoint.description)
        self.assertEqual(endpoint.metadata, {'name': 'value'})
        self.assertEqual(endpoint.name, 'operation')
        self.assertIs(endpoint.resource, resource)
        self.assertIsInstance(endpoint.schema, Structure)
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['referenced']))
        self.assertFalse(endpoint.specific)
        self.assertTrue(endpoint.subject_required)
        self.assertEqual(endpoint.title, 'operation')
        self.assertFalse(endpoint.verbose)

        self.assertEqual(set(endpoint.responses.keys()), set([OK, PARTIAL]))
        for key in (OK, PARTIAL):
            self.assertEqual(endpoint.responses[key].status, key)
            self.assertIsInstance(endpoint.responses[key], EndpointResponse)

        class described:
            """description"""

        endpoint = Endpoint.construct(resource, described)
        self.assertEqual(endpoint.description, 'description')

        struct = Structure({'id': Integer()})
        class schema_already_structure:
            schema = struct

        endpoint = Endpoint.construct(resource, schema_already_structure)
        self.assertIs(endpoint.schema, struct)

    def test_declarative_inheritance(self):
        resource = object()

        class first(object):
            schema = {}
            responses = {
                OK: EndpointResponse({}),
            }
            title = 'first'
            metadata = {'alpha': 1, 'beta': 2}

            @classmethod
            def get_endpoint(cls, resource, declaration):
                return cls

        class second(first):
            schema = {'id': Integer()}
            responses = {
                PARTIAL: {},
            }
            title = 'second'
            metadata = {'alpha': 0, 'gamma': 3}

        endpoint = Endpoint.construct(resource, second)

        self.assertFalse(endpoint.auto_constructed)
        self.assertFalse(endpoint.batch)
        self.assertIsNone(endpoint.description)
        self.assertEqual(endpoint.metadata, {'alpha': 0, 'beta': 2, 'gamma': 3})
        self.assertEqual(endpoint.name, 'second')
        self.assertIs(endpoint.resource, resource)
        self.assertEqual(set(endpoint.responses.keys()), set([OK, PARTIAL]))
        self.assertIsInstance(endpoint.schema, Structure)
        self.assertIsInstance(endpoint.schema.structure['id'], Integer)
        self.assertFalse(endpoint.specific)
        self.assertTrue(endpoint.subject_required)
        self.assertEqual(endpoint.title, 'second')
        self.assertFalse(endpoint.verbose)

    def test_auto_construction_inheritance(self):
        class first(object):
            @staticmethod
            def get_endpoint(resource, declaration):
                return self._construct_example_endpoint(resource)

        class second(first):
            responses = {PARTIAL: {}}
            title = 'second'

        resource = object()
        endpoint = Endpoint.construct(resource, second)

        self.assertFalse(endpoint.auto_constructed)
        self.assertEqual(endpoint.name, 'second')
        self.assertIs(endpoint.resource, resource)
        self.assertEqual(set(endpoint.responses.keys()), set([OK, PARTIAL, INVALID]))
        self.assertIsInstance(endpoint.schema, Structure)
        self.assertIsInstance(endpoint.schema.structure['id'], Integer)
        self.assertEqual(endpoint.title, 'second')

    def test_field_injection(self):
        class resource:
            schema = {'referenced': Integer(name='referenced')}

        class first(object):
            @staticmethod
            def get_endpoint(resource, declaration):
                return self._construct_example_endpoint(resource,
                    schema={'id': Integer(), 'name': Text()})

        class second(first):
            fields = {
                'attr': Text(),
                'value': Float(name='value'),
                'name': None,
                'not_present': None,
                'referenced': 'referenced',
                'renamed': 'referenced',
            }

        endpoint = Endpoint.construct(resource, second)
        self.assertIsInstance(endpoint.schema, Structure)
        self.assertEqual(set(endpoint.schema.structure.keys()),
            set(['id', 'attr', 'value', 'referenced', 'renamed']))

        class invalid(first):
            fields = {'bad_ref': 'bad_ref'}

        with self.assertRaises(SpecificationError):
            Endpoint.construct(resource, invalid)

        class invalid(first):
            fields = {'bad_field': 12}

        with self.assertRaises(TypeError):
            Endpoint.construct(resource, invalid)

    def test_field_injection_with_empty_schema(self):
        resource = object()

        class operation:
            fields = {'attr': Text()}

        endpoint = Endpoint.construct(resource, operation)

        self.assertIsInstance(endpoint.schema, Structure)
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['attr']))

    def test_basic_successful_processing(self):
        endpoint = self._construct_example_endpoint(schema=False)
        controller = self._construct_controller_harness(data={'id': 1})
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)
        self.assertEqual(response.data, {'id': 1})

    def test_improper_subject(self):
        endpoint = self._construct_example_endpoint()
        controller = self._construct_controller_harness(data={'id': 1})
        request, response = self._construct_request_response(subject=2)
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, BAD_REQUEST)

    def test_improper_data_inclusion(self):
        endpoint = self._construct_example_endpoint(schema=False)
        controller = self._construct_controller_harness()
        request, response = self._construct_request_response(data={'id': 1})
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, BAD_REQUEST)

    def test_implicit_status(self):
        endpoint = self._construct_example_endpoint()
        controller = self._construct_controller_harness(status=None)
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)

    def test_controller_invocation(self):
        def callback(*args):
            raise StructuralError({'token': 'incorrect'})

        endpoint = self._construct_example_endpoint()
        controller = self._construct_controller_harness(callback=callback)
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, INVALID)
        self.assertEqual(response.data, ([{'token': 'incorrect'}], None))

    def test_request_error_passthrough(self):
        def callback(*args):
            raise ConflictError()

        endpoint = self._construct_example_endpoint()
        controller = self._construct_controller_harness(callback=callback)
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, CONFLICT)

    def test_undefined_response(self):
        endpoint = self._construct_example_endpoint()
        controller = self._construct_controller_harness(status=CONFLICT)
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, CONFLICT)

        controller = self._construct_controller_harness(status=CONFLICT, data='testing')
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, SERVER_ERROR)

    def test_subject_processing(self):
        endpoint = self._construct_example_endpoint(specific=True)

        controller = self._construct_controller_harness(expected_subject=2)
        request, response = self._construct_request_response(subject=2)
        endpoint.process(controller, request, response)
        
        self.assertEqual(response.status, GONE)

        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)
        
        self.assertEqual(response.status, BAD_REQUEST)

        controller = self._construct_controller_harness(expected_subject=2, subject=True)
        request, response = self._construct_request_response(subject=2)
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)

    def test_subject_not_required(self):
        endpoint = self._construct_example_endpoint(specific=True, subject_required=False)
        controller = self._construct_controller_harness(expected_subject=2, subject=None)
        request, response = self._construct_request_response(subject=2)
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)

    def test_request_validation(self):
        endpoint = self._construct_example_endpoint(schema={'id': Integer(maximum=1)})
        controller = self._construct_controller_harness()
        request, response = self._construct_request_response(data={'id': 1})
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)

        request, response = self._construct_request_response(data={'id': 2})
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, INVALID)
        self.assertEqual(response.data, (None, {'id': [{'token': 'maximum', 'title': 'maximum value',
            'message': 'id must be less then or equal to 1'}]}))

    def test_response_validation(self):
        endpoint = self._construct_example_endpoint(ok={'id': Integer(required=True)})
        controller = self._construct_controller_harness(data={'id': 1})
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)

        controller = self._construct_controller_harness(data={})
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, SERVER_ERROR)

        endpoint = self._construct_example_endpoint(ok=False)
        controller = self._construct_controller_harness(data={'id': 1})
        request, response = self._construct_request_response()
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, SERVER_ERROR)

    def test_general_validators(self):
        class Resource(object):
            @validator()
            def validate(cls, data):
                if data['id'] != 2:
                    raise ValidationError({'token': 'incorrect'})

        endpoint = self._construct_example_endpoint(Resource, validators=[Resource.validate])
        controller = self._construct_controller_harness()
        request, response = self._construct_request_response(data={'id': 2})
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)

        request, response = self._construct_request_response(data={'id': 1})
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, INVALID)
        self.assertEqual(response.data, ([{'token': 'incorrect'}], None))

    def test_specific_validators(self):
        class Resource(object):
            @validator('id')
            def validate(cls, data):
                if data['id'] != 2:
                    raise ValidationError({'token': 'incorrect'})

        endpoint = self._construct_example_endpoint(Resource, validators=[Resource.validate])
        controller = self._construct_controller_harness()
        request, response = self._construct_request_response(data={'id': 2})
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, OK)

        request, response = self._construct_request_response(data={'id': 1})
        endpoint.process(controller, request, response)

        self.assertEqual(response.status, INVALID)
        self.assertEqual(response.data, (None, {'id': [{'token': 'incorrect'}]}))

    def test_mediation_before_validation(self):
        class TestMediator(Mediator):
            def before_validation(self, definition, request, response):
                if request.address.subject == 1:
                    response(GONE)
                elif request.address.subject != 2:
                    raise ValidationError({'token': 'incorrect'})

        endpoint = self._construct_example_endpoint(specific=True)
        controller = self._construct_controller_harness(expected_subject=2, subject=2)
        request, response = self._construct_request_response(subject=2)
        endpoint.process(controller, request, response, [TestMediator()])

        self.assertEqual(response.status, OK)

        controller = self._construct_controller_harness(expected_subject=1, subject=1)
        request, response = self._construct_request_response(subject=1)
        endpoint.process(controller, request, response, [TestMediator()])

        self.assertEqual(response.status, GONE)

        controller = self._construct_controller_harness(expected_subject=3, subject=3)
        request, response = self._construct_request_response(subject=3)
        endpoint.process(controller, request, response, [TestMediator()])

        self.assertEqual(response.status, INVALID)
        self.assertEqual(response.data, ([{'token': 'incorrect'}], None))

    def test_description(self):
        endpoint = self._construct_example_endpoint()
        desc = endpoint.describe()

        self.assertIsInstance(desc, dict)
        self.assertEqual(desc['name'], 'test')
        self.assertIsInstance(desc['schema'], dict)
        self.assertEqual(desc['schema']['fieldtype'], 'structure')
        self.assertIsInstance(desc['responses'], dict)
        self.assertEqual(set(desc['responses'].keys()), set([OK, INVALID]))

    def test_reconstruction(self):
        original = self._construct_example_endpoint(method=POST, metadata={'attr': 'value'})
        desc = original.describe()
        endpoint = Endpoint.reconstruct(original.resource, desc)

        self.assertIsInstance(endpoint, Endpoint)
        self.assertIsNot(endpoint, original)
        self.assertEqual(endpoint.name, original.name)
        self.assertEqual(endpoint.method, original.method)
        self.assertEqual(endpoint.metadata, {})

    def test_attach(self):
        class resource(object):
            name = 'example'

        endpoint = self._construct_example_endpoint(resource=resource)
        addr = Address(bundle=('bundle', (1, 0)))
        attached = endpoint.attach(addr)

        self.assertIsNot(attached, addr)
        self.assertIsInstance(attached, Address)
        self.assertEqual(str(attached), 'test::/bundle/1.0/example')

    def _construct_controller_harness(self, expected_subject=None, subject=None, status=OK,
            data=None, callback=None):

        testcase = self
        class Controller(object):
            def acquire(self, received_subject):
                testcase.assertEqual(received_subject, expected_subject)
                return subject

            def dispatch(self, endpoint, request, response, dispatched_subject, dispatched_data):
                testcase.assertIsInstance(endpoint, Endpoint)
                testcase.assertIsInstance(request, Request)
                testcase.assertIsInstance(response, Response)
                testcase.assertEqual(dispatched_subject, subject)
                if callback:
                    callback(endpoint, request, response, dispatched_subject, dispatched_data)
                else:
                    response(status, data)

        return Controller

    def _construct_example_endpoint(self, resource=None, name='test', method=None, schema=None,
            ok=None, specific=False, auto_constructed=True, batch=False, subject_required=True,
            validators=None, metadata=None):

        if resource is None:
            resource = object()

        if schema is None:
            schema = Structure({'id': Integer()})
        elif schema is False:
            schema = None
        elif isinstance(schema, dict):
            schema = Structure(schema)

        if ok is None:
            ok = EndpointResponse(Structure({'id': Integer()}))
        elif ok is False:
            ok = EndpointResponse()
        elif isinstance(ok, dict):
            ok = EndpointResponse(Structure(ok))

        responses = {OK: ok, INVALID: EndpointResponse(Errors)}
        return Endpoint(resource=resource, name=name, method=method, schema=schema,
            responses=responses, specific=specific, auto_constructed=auto_constructed, batch=batch,
            subject_required=subject_required, validators=validators, metadata=metadata)

    def _construct_request_response(self, endpoint='test', subject=None, data=None):
        addr = Address(endpoint, None, ('bundle', (1, 0)), 'resource', subject)
        return Request(addr, data=data), Response()

class TestValidator(TestCase):
    def test_construction(self):
        @validator('id', ['one', 'two'])
        def val():
            pass

        self.assertEqual(val.__func__.attr, 'id')
        self.assertEqual(val.__func__.endpoints, ['one', 'two'])

        @validator(None, 'one two')
        def val():
            pass

        self.assertEqual(val.__func__.attr, None)
        self.assertEqual(val.__func__.endpoints, ['one', 'two'])

        class test(object):
            pass

        @validator(None, [test])
        def val():
            pass

        self.assertEqual(val.__func__.attr, None)
        self.assertEqual(val.__func__.endpoints, ['test'])

        @validator(None, test)
        def val():
            pass

        self.assertEqual(val.__func__.attr, None)
        self.assertEqual(val.__func__.endpoints, ['test'])
