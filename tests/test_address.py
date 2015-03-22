try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

from mesh.address import *
from mesh.constants import *

class TestAddress(TestCase):
    ValidAddresses = (
        ('/outer/1.0', ('outer', (1, 0))),
        ('/outer/1.0/resource', ('outer', (1, 0))),
        ('/outer/1.0/resource/id', ('outer', (1, 0))),
        ('/outer/1.0/resource/id/subresource', ('outer', (1, 0))),
        ('/outer/1.0/resource/id/subresource/subid', ('outer', (1, 0))),
        ('/outer/1.0/inner/2.0/resource', ('outer', (1, 0), 'inner', (2, 0))),
        ('/outer/1.0/inner/2.0/resource/id', ('outer', (1, 0), 'inner', (2, 0))),
        ('/outer/1.0/inner/2.0/resource/id/subresource', ('outer', (1, 0), 'inner', (2, 0))),
        ('/outer/1.0/inner/2.0/resource/id/subresource/subid', ('outer', (1, 0), 'inner', (2, 0))),
    )

    def test_construction(self):
        addr = Address('create', None, ('bundle', (1, 0)), 'resource', 'subject')
        self.assertEqual(str(addr), 'create::/bundle/1.0/resource/subject')

    def test_validity(self):
        addr = Address()
        self.assertFalse(addr.valid)

        addr = Address('endpoint', None, ('bundle', (1, 0)), 'resource')
        self.assertTrue(addr.valid)

    def test_clone(self):
        addr = Address('test', None, ('bundle', (1, 0)), 'resource')
        cloned = addr.clone(endpoint='more', subject='id')

        self.assertIsNot(addr, cloned)
        self.assertIsInstance(cloned, Address)
        self.assertEqual(str(cloned), 'more::/bundle/1.0/resource/id')

    def test_extend(self):
        addr = Address(resource='test')
        extended = addr.extend('bundle', (1, 0))

        self.assertIsNot(extended, addr)
        self.assertIsInstance(extended, Address)
        self.assertEqual(str(extended), '/bundle/1.0/test')

        another = extended.extend('another', (1, 1))

        self.assertIsNot(another, extended)
        self.assertIsInstance(another, Address)
        self.assertEqual(str(another), '/bundle/1.0/another/1.1/test')

    def test_parsing(self):
        for address, bundle in self.ValidAddresses:
            addr = Address.parse(address, endpoint='create')
            self.assertEqual(str(addr), 'create::' + address)
            self.assertEqual(addr.bundle, bundle)

            addr = Address.parse('create::' + address)
            self.assertEqual(str(addr), 'create::' + address)
            self.assertEqual(addr.bundle, bundle)

            addr = Address.parse(address + '!json', endpoint='create')
            self.assertEqual(str(addr), 'create::' + address + '!json')
            self.assertEqual(addr.bundle, bundle)
            self.assertEqual(addr.format, 'json')

        with self.assertRaises(ValueError):
            Address.parse('invalid url', 'create')

    def test_prefixed_parsing(self):
        addr = Address.parse('/api/outer/1.0/resource', '/api', endpoint='create')
        self.assertEqual(str(addr), 'create::/outer/1.0/resource')
        self.assertEqual(addr.prefixed_path, '/api/outer/1.0/resource')

    def test_validate(self):
        addr = Address()
        self.assertTrue(addr.validate())
        self.assertTrue(addr.validate(bundle=False))
        self.assertFalse(addr.validate(bundle=True))
