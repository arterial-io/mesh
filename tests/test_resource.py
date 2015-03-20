from unittest import TestCase

from mesh.constants import *
from mesh.endpoint import *
from mesh.resource import *
from scheme import *

class TestHarness(TestCase):
    def setUp(self):
        self.configuration = Configuration({
            'test': self._construct_example_endpoint,
            'noop': lambda *a: None,
        }, ['test'])

    @staticmethod
    def _construct_example_endpoint(resource):
        return Endpoint(name='test', auto_constructed=True, resource=resource,
            schema=Structure({'id': Integer()}),
            responses={OK: EndpointResponse(Structure({'id': Integer()}))})

    def _construct_example_resource(self):
        class Example(Resource):
            """description"""

            configuration = self.configuration
            name = 'example'
            version = 1

            class schema:
                name = Text()

        return Example

    def _construct_example_controller(self, example_resource):
        class ExampleController(Controller):
            resource = example_resource
            version = (1, 0)

            def test(self):
                pass

        return ExampleController

class TestResource(TestHarness):
    def test_resource_declaration(self):
        Example = self._construct_example_resource()

        self.assertIs(Example.configuration, self.configuration)
        self.assertEqual(Example.name, 'example')
        self.assertEqual(Example.version, 1)
        self.assertIsInstance(Example.schema, dict)
        self.assertIsInstance(Example.endpoints, dict)

        self.assertIs(Example[1], Example)
        self.assertEqual(Example.description, 'description')
        self.assertEqual(Example.minimum_version, 1)
        self.assertEqual(Example.maximum_version, 1)
        self.assertEqual(Example.title, 'Example')

        id_field = Example.schema.get('id')

        self.assertIsInstance(id_field, Integer)
        self.assertEqual(id_field.name, 'id')
        self.assertIs(Example.id_field, id_field)

        name_field = Example.schema.get('name')

        self.assertIsInstance(name_field, Text)
        self.assertEqual(name_field.name, 'name')

        endpoint = Example.endpoints.get('test')

        self.assertIsInstance(endpoint, Endpoint)
        self.assertTrue(endpoint.auto_constructed)
        self.assertEqual(endpoint.name, 'test')
        self.assertIs(endpoint.resource, Example)
        self.assertFalse(endpoint.specific)

    def test_composite_key(self):
        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1
            composite_key = 'id attr'

            class schema:
                attr = Text()

        self.assertEqual(Example.composite_key, ['id', 'attr'])

    def test_invalid_base_class(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource, Endpoint):
                configuration = self.configuration

    def test_only_abstract_bases(self):
        with self.assertRaises(SpecificationError):
            class AbstractResource(Resource):
                configuration = self.configuration
                abstract = True
                version = 1

            class Example(AbstractResource):
                configuration = self.configuration
                name = 'example'
                version = 1

    def test_abstract_resource_has_invalid_base_class(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource):
                configuration = self.configuration
                name = 'example'
                version = 1

            class AbstractResource(Example):
                configuration = self.configuration
                abstract = True
                version = 1

    def test_invalid_configuration(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource):
                configuration = True

    def test_invalid_schema(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource):
                configuration = self.configuration
                schema = True

    def test_invalid_version(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource):
                configuration = self.configuration
                name = 'example'
                version = 0

    def test_duplicate_version(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource):
                configuration = self.configuration
                name = 'example'
                version = 1

            class Example(Example):
                version = 1

    def test_unknown_standard_endpoint(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource):
                configuration = self.configuration
                name = 'example'
                version = 1
                endpoints = 'invalid'

    def test_invalid_composite_key(self):
        with self.assertRaises(SpecificationError):
            class Example(Resource):
                configuration = self.configuration
                name = 'example'
                version = 1
                composite_key = 'id attr'

                class schema:
                    id = Integer()

    def test_abstract_resources(self):
        class AbstractResource(Resource):
            configuration = self.configuration
            abstract = True
            version = 1

            class schema:
                value = Integer()

        self.assertTrue(AbstractResource.abstract)

    def test_explicit_endpoints(self):
        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1
            endpoints = []

        self.assertEqual(Example.endpoints, {})

        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1
            endpoints = 'test'

        self.assertEqual(set(Example.endpoints.keys()), set(['test']))

    def test_endpoint_declaration(self):
        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1

            class operation:
                schema = {'id': Integer()}
                responses = {OK: {'id': Integer()}}

        self.assertIsInstance(Example.endpoints, dict)
        self.assertEqual(len(Example.endpoints), 2)

        operation = Example.endpoints['operation']

        self.assertEqual(operation.name, 'operation')
        self.assertFalse(operation.auto_constructed)
        self.assertIsInstance(operation.schema, Structure)

    def test_endpoint_constructor(self):
        class ExampleConstructor(EndpointConstructor):
            def construct(self, resource, declaration=None):
                return Endpoint(name='example', auto_constructed=True, resource=resource)

        example_configuration = Configuration({'example': ExampleConstructor()}, ['example'])

        class Example(Resource):
            configuration = example_configuration
            name = 'example'
            version = 1

        self.assertEqual(set(Example.endpoints.keys()), set(['example']))

    def test_endpoint_as_attribute(self):
        Example = self._construct_example_resource()
        test = Example.test
        endpoint = test.get_endpoint(Example)

        self.assertIsInstance(endpoint, Endpoint)
        self.assertIs(endpoint, Example.endpoints['test'])

        with self.assertRaises(AttributeError):
            Example.invalid

        with self.assertRaises(AttributeError):
            Resource.no_endpoints

    def test_validator_declaration(self):
        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1

            class schema:
                name = Text()

            @validator('name')
            def validate_name(cls, data):
                pass

            @validator('name', 'test not_present')
            def validate_name_again(cls, data):
                pass

            @classmethod
            def ignored_method(cls):
                pass

        self.assertEqual(set(Example.validators.keys()), set(['validate_name', 'validate_name_again']))
        self.assertEqual(Example.validators['validate_name'].endpoints, [])

    def test_resource_inheritance(self):
        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1

            class schema:
                name = Text()
                something = Text()

            class operation:
                schema = {'id': Integer()}
                responses = {OK: {'id': Integer()}}

        first = Example

        self.assertEqual(first.version, 1)
        self.assertEqual(set(first.endpoints.keys()), set(['test', 'operation']))

        class Example(Example):
            name = 'example'
            version = 2

            class schema:
                added = Text()
                something = None
                not_present = None

            operation = None

        self.assertEqual(Example.version, 2)
        self.assertEqual(set(Example.schema.keys()), set(['id', 'name', 'added']))
        self.assertEqual(set(Example.endpoints.keys()), set(['test']))

        self.assertIs(Example[1], first)
        self.assertIs(Example[2], Example)
        self.assertEqual(Example.minimum_version, 1)
        self.assertEqual(Example.maximum_version, 2)

    def test_description_without_controller(self):
        Example = self._construct_example_resource()
        desc = Example.describe()

        self.assertEqual(desc['__subject__'], 'resource')
        self.assertFalse(desc['abstract'])
        self.assertEqual(desc['classname'], 'Example')
        self.assertIsNone(desc['composite_key'])
        self.assertIsNone(desc['controller'])
        self.assertEqual(desc['description'], 'description')
        self.assertIsNone(desc['id'])
        self.assertEqual(desc['name'], 'example')
        self.assertEqual(desc['resource'], 'tests.test_resource.Example')
        self.assertEqual(desc['title'], 'Example')
        self.assertEqual(desc['version'], (1, 0))

    def test_description_with_controller(self):
        Example = self._construct_example_resource()
        ExampleController = self._construct_example_controller(Example)
        desc = Example.describe(controller=ExampleController)

        self.assertEqual(desc['__subject__'], 'resource')
        self.assertFalse(desc['abstract'])
        self.assertEqual(desc['classname'], 'Example')
        self.assertIsNone(desc['composite_key'])
        self.assertEqual(desc['controller'], 'tests.test_resource.ExampleController')
        self.assertEqual(desc['description'], 'description')
        self.assertIsNone(desc['id'])
        self.assertEqual(desc['name'], 'example')
        self.assertEqual(desc['resource'], 'tests.test_resource.Example')
        self.assertEqual(desc['title'], 'Example')
        self.assertEqual(desc['version'], (1, 0))

    def test_reconstruction(self):
        Original = self._construct_example_resource()
        description = Original.describe()
        Example = Resource.reconstruct(description, self.configuration)

        self.assertTrue(issubclass(Example, Resource))
        self.assertIsNot(Example, Original)
        self.assertEqual(Example.name, Original.name)
        self.assertEqual(Example.version, Original.version)

    def test_reconstruction_with_implicit_configuration(self):
        class ConfiguredResource(Resource):
            configuration = self.configuration

        class Example(ConfiguredResource):
            name = 'example'
            version = 1

            class schema:
                attr = Text()

        description = Example.describe()
        Reconstructed = ConfiguredResource.reconstruct(description)

        self.assertTrue(issubclass(Reconstructed, ConfiguredResource))
        self.assertIsNot(Reconstructed, Example)
        self.assertEqual(Reconstructed.name, Example.name)
        self.assertEqual(Reconstructed.version, Example.version)

    def test_reconstruction_with_configuration(self):
        Original = self._construct_example_resource()
        description = Original.describe()

        with self.assertRaises(TypeError):
            Resource.reconstruct(description)

    def test_enumerate_endpoints(self):
        Example = self._construct_example_resource()
        endpoints = list(Example.enumerate_endpoints())

        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0][0].address, 'test::/example')
        self.assertIs(endpoints[0][1], Example.endpoints['test'])

        endpoints = list(Example.enumerate_endpoints(Address(bundle=('bundle', (1, 0)))))

        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0][0].address, 'test::/bundle/1.0/example')
        self.assertIs(endpoints[0][1], Example.endpoints['test'])

    def test_filter_schema(self):
        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1

            class schema:
                name = Text()
                description = Text(readonly=True)

        filtered = Example.filter_schema(readonly=False)
        self.assertEqual(set(filtered.keys()), set(['id', 'name']))

        filtered = Example.filter_schema(readonly=True)
        self.assertEqual(set(filtered.keys()), set(['description']))

    def test_mirror_schema(self):
        Example = self._construct_example_resource()
        mirrored = Example.mirror_schema()

        self.assertEqual(set(mirrored.keys()), set(['id', 'name']))

        mirrored = Example.mirror_schema('name')

        self.assertEqual(set(mirrored.keys()), set(['id']))

class TestController(TestHarness):
    def test_controller_declaration(self):
        Example = self._construct_example_resource()
        ExampleController = self._construct_example_controller(Example)

        self.assertEqual(ExampleController.version, (1, 0))
        self.assertIs(ExampleController.resource, Example)

        self.assertEqual(ExampleController.minimum_version, (1, 0))
        self.assertEqual(ExampleController.maximum_version, (1, 0))
        self.assertEqual(len(ExampleController.versions), 1)

        self.assertIsInstance(ExampleController.endpoints, dict)
        self.assertEqual(ExampleController.endpoints['test'], ExampleController.test)

    def test_controller_inheritance(self):
        Example = self._construct_example_resource()

        class ExampleController(Controller):
            resource = Example
            version = (1, 0)

            def test(self):
                pass

        first = ExampleController

        class ExampleController(ExampleController):
            resource = Example
            version = (1, 1)

            def test(self):
                pass

        self.assertEqual(ExampleController.version, (1, 1))
        self.assertIs(ExampleController.resource, Example)

        self.assertEqual(ExampleController.minimum_version, (1, 0))
        self.assertEqual(ExampleController.maximum_version, (1, 1))
        self.assertEqual(len(ExampleController.versions), 2)

    def test_invalid_resource(self):
        with self.assertRaises(SpecificationError):
            class ExampleController(Controller):
                resource = object()
                version = (1, 0)

    def test_invalid_controller_version(self):
        Example = self._construct_example_resource()

        def has_invalid_version(test_version):
            class ExampleController(Controller):
                resource = Example
                version = test_version

        for candidate in (True, (1,), (1, 't'), ('t', 1), (0, 1), (1, -1)):
            with self.assertRaises(SpecificationError):
                has_invalid_version(candidate)

    def test_invalid_resource_version(self):
        Example = self._construct_example_resource()

        with self.assertRaises(SpecificationError):
            class ExampleController(Controller):
                resource = Example
                version = (2, 0)

    def test_specifies_version_when_abstract(self):
        with self.assertRaises(SpecificationError):
            class ExampleController(Controller):
                version = (1, 0)

    def test_duplicate_controller_version(self):
        Example = self._construct_example_resource()

        with self.assertRaises(SpecificationError):
            class ExampleController(Controller):
                resource = Example
                version = (1, 0)

            class Examplecontroller(ExampleController):
                resource = Example
                version = (1, 0)

    def test_mismatching_resources(self):
        Example = self._construct_example_resource()
        
        class Second(Resource):
            configuration = self.configuration
            name = 'second'
            version = 1

        with self.assertRaises(SpecificationError):
            class ExampleController(Controller):
                resource = Example
                version = (1, 0)

            class ExampleController(ExampleController):
                resource = Second
                version = (1, 1)
