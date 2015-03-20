from unittest import TestCase

from scheme import formats

from mesh.address import *
from mesh.constants import *
from mesh.exceptions import *
from mesh.transport.internal import *

from tests.fixtures import *

class TestInternalClient(TestCase):
    def setUp(self):
        self.server = InternalServer([ExampleBundle])

    def test_instantiation(self):
        client = InternalClient(self.server, ExampleBundle)
        self.assertEqual(client.name, 'examples')

    def test_instantiation_with_bundle_name(self):
        client = InternalClient(self.server, 'examples')
        self.assertEqual(client.name, 'examples')

    def test_instantiation_with_invalid_bundle_name(self):
        with self.assertRaises(ValueError):
            InternalClient(self.server, 'invalid')

class TestInternalTransport(TestCase):
    def setUp(self):
        self.server = InternalServer([ExampleBundle])
        self.client = InternalClient(self.server, 'examples')

    def test_execution_with_data(self):
        response = self.client.execute('test::/examples/1.0/example', data={'id': 2})
        self.assertEqual(response.status, OK)
        self.assertEqual(response.data, {'id': 2})

    def test_execution_with_subject(self):
        response = self.client.execute('operation::/examples/1.0/example', 3)
        self.assertEqual(response.status, OK)
        self.assertEqual(response.data, {'id': 3})

        response = self.client.execute(Address('operation', None, ('examples', (1, 0)), 'example'), 3)
        self.assertEqual(response.status, OK)
        self.assertEqual(response.data, {'id': 3})

    def test_serialized_request(self):
        response = self.client.execute('test::/examples/1.0/example', data={'id': 2}, format='json')
        self.assertEqual(response.status, OK)
        self.assertEqual(response.data, {'id': 2})

    def test_invalid_endpoint(self):
        for invalid in ('invalid::/examples/1.0/example', 'operation::/examples/1.0/invalid'):
            with self.assertRaises(NotFoundError):
                self.client.execute(invalid)
