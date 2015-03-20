from unittest import TestCase

from scheme import formats

from mesh.address import *
from mesh.constants import *
from mesh.transport.base import *

from tests.fixtures import *

class TestServer(TestCase):
    def test_construction(self):
        server = Server([ExampleBundle])

        self.assertEqual(server.bundles, {'examples': ExampleBundle})
        self.assertIsNone(server.default_format)
        self.assertIsNone(server.mediators)
        self.assertEqual(server.formats, {'json': formats.Json, 'application/json': formats.Json})

        server = Server([ExampleBundle], formats.Json, (formats.Json, formats.Yaml))

        self.assertIs(server.default_format, formats.Json)
        self.assertEqual(set(server.formats.keys()),
            set(['json', 'application/json', 'yaml', 'application/x-yaml']))

    def test_duplicate_bundle(self):
        with self.assertRaises(ValueError):
            Server([ExampleBundle, ExampleBundle])

    def test_invalid_bundle(self):
        with self.assertRaises(TypeError):
            Server([True])

class TestClient(TestCase):
    def test_construction(self):
        client = Client()

        self.assertEqual(client.context, {})
        self.assertIsNone(client.format, None)
        self.assertIsNone(client.name, None)

    def test_instantiation_with_bundle(self):
        client = Client(ExampleBundle)
        self.assertEqual(client.name, 'examples')

    def test_instantiation_with_specification(self):
        client = Client(ExampleBundle.specify())
        self.assertEqual(client.name, 'examples')

    def test_instantiation_with_description(self):
        client = Client(ExampleBundle.describe())
        self.assertEqual(client.name, 'examples')
    
    def test_client_registration(self):
        specification = ExampleBundle.specify()
        client = Client(specification)

        for arg in ('examples', specification):
            self.assertIsNone(Client.get_client(arg))

        returned = client.register()
        self.assertIs(returned, client)

        for arg in ('examples', specification):
            self.assertIs(Client.get_client(arg), client)

        returned = client.unregister()
        self.assertIs(returned, client)

        for arg in ('examples', specification):
            self.assertIsNone(Client.get_client(arg))

        returned = client.unregister()
        self.assertIs(returned, client)

    def test_get_endpoint(self):
        specification = ExampleBundle.specify()
        client = Client(specification)
        operation = client.get_endpoint('operation::/examples/1.0/example')

        self.assertIsInstance(operation, dict)
        self.assertEqual(set(operation.keys()),
            set(['address', 'method', 'specific', 'path', 'responses', 'name', 'schema']))
