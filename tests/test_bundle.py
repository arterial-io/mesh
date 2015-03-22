try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

from scheme.util import format_structure

from mesh.address import Address
from mesh.bundle import *
from mesh.resource import *

def ps(*args):
    for arg in args:
        print(format_structure(arg))

class TestHarness(TestCase):
    def setUp(self):
        self.configuration = Configuration()

        class Example(Resource):
            configuration = self.configuration
            name = 'example'
            version = 1

        self.example_1 = Example

        class Example(Example):
            name = 'example'
            version = 2

        self.example_2 = Example

        class ExampleController(Controller):
            resource = Example
            version = (1, 0)

        self.example_controller_1_0 = ExampleController

        class ExampleController(ExampleController):
            resource = Example
            version = (1, 1)

        self.example_controller_1_1 = ExampleController

        class ExampleController(ExampleController):
            resource = Example
            version = (2, 0)

        self.example_controller_2_0 = ExampleController

        class ExampleController(ExampleController):
            resource = Example
            version = (2, 1)

        self.example_controller_2_1 = ExampleController

        self.Example = Example
        self.ExampleController = ExampleController

        class Another(Resource):
            configuration = self.configuration
            name = 'another'
            version = 1

        self.another_1 = Another

        class AnotherController(Controller):
            resource = Another
            version = (1, 0)

        self.another_controller_1_0 = AnotherController

        self.Another = Another
        self.AnotherController = AnotherController

class TestMount(TestHarness):
    def test_mount_with_controller(self):
        m = mount(self.Example, self.ExampleController)
        constructed = m.construct(None)

        self.assertTrue(constructed)
        self.assertTrue(m.constructed)
        self.assertIs(m.resource, self.Example)
        self.assertIs(m.controller, self.ExampleController)
        self.assertEqual(m.min_version, (1, 0))
        self.assertEqual(m.max_version, (2, 1))
        self.assertEqual(m.versions, [(1, 0), (1, 1), (2, 0), (2, 1)])

    def test_construction_via_import(self):
        m = mount('tests.fixtures.Example', 'tests.fixtures.ExampleController')
        constructed = m.construct()

        from tests.fixtures import Example, ExampleController

        self.assertTrue(constructed)
        self.assertTrue(m.constructed)
        self.assertIs(m.resource, Example)
        self.assertIs(m.controller, ExampleController)

    def test_failed_resource_import(self):
        m = mount('tests.fixtures.NotPresent')
        constructed = m.construct(None)

        self.assertFalse(constructed)
        self.assertFalse(m.constructed)
        self.assertEqual(m.resource, 'tests.fixtures.NotPresent')

    def test_failed_controller_import(self):
        m = mount('tests.fixtures.Example', 'tests.fixtures.NotPresentController')
        constructed = m.construct()

        from tests.fixtures import Example

        self.assertTrue(constructed)
        self.assertTrue(m.constructed)
        self.assertIs(m.resource, Example)
        self.assertNotEqual(m.controller, 'tests.fixtures.NotPresentController')

    def test_mount_with_min_version(self):
        m = mount(self.Example, self.ExampleController, min_version=(1, 1))
        constructed = m.construct(None)

        self.assertTrue(constructed)
        self.assertEqual(m.min_version, (1, 1))
        self.assertEqual(m.max_version, (2, 1))
        self.assertEqual(m.versions, [(1, 1), (2, 0), (2, 1)])

    def test_mount_with_max_version(self):
        m = mount(self.Example, self.ExampleController, max_version=(2, 0))
        constructed = m.construct(None)

        self.assertTrue(constructed)
        self.assertEqual(m.min_version, (1, 0))
        self.assertEqual(m.max_version, (2, 0))
        self.assertEqual(m.versions, [(1, 0), (1, 1), (2, 0)])

    def test_mount_with_min_and_max_version(self):
        m = mount(self.Example, self.ExampleController, min_version=(1, 1), max_version=(2, 0))
        constructed = m.construct(None)

        self.assertTrue(constructed)
        self.assertEqual(m.min_version, (1, 1))
        self.assertEqual(m.max_version, (2, 0))
        self.assertEqual(m.versions, [(1, 1), (2, 0)])

    def test_clone(self):
        m = mount(self.Example, self.ExampleController)
        cloned = m.clone()

        self.assertIsNot(m, cloned)
        self.assertIsInstance(cloned, mount)
        for attr in ('resource', 'controller', 'min_version', 'max_version'):
            self.assertEqual(getattr(m, attr), getattr(cloned, attr))

    def test_get(self):
        expected = {
            (3, 0): (2, 1),
            (2, 2): (2, 1),
            (2, 1): (2, 1),
            (2, 0): (2, 0),
            (1, 2): (1, 1),
            (1, 1): (1, 1),
            (1, 0): None,
        }

        m = mount(self.Example, self.ExampleController, min_version=(1, 1))
        m.construct(None)

        for version, correct in expected.items():
            result = m.get(version)
            if correct:
                self.assertEqual(result[1][1].version, correct)
            else:
                self.assertIs(result, None)

class TestBundle(TestHarness):
    def assert_viable_description(self, description, name=None, version=1):
        self.assertIsInstance(description, dict)
        self.assertEqual(description['__subject__'], 'bundle')
        self.assertEqual(description['__version__'], version)
        self.assertIsInstance(description['versions'], dict)
        
        if name is not None:
            self.assertEqual(description['name'], name)

    def test_construction(self):
        example_mount = mount(self.Example, self.ExampleController)
        bundle = Bundle('bundle', example_mount, description='description')

        self.assertEqual(bundle.name, 'bundle')
        self.assertEqual(bundle.description, 'description')
        self.assertEqual(bundle.mounts, [example_mount])

        bundle = Bundle('bundle')

        self.assertEqual(bundle.mounts, [])

    def test_clone(self):
        example_mount = mount(self.Example, self.ExampleController)
        bundle = Bundle('bundle', example_mount, description='description')
        cloned = bundle.clone()

        self.assertIsNot(cloned, bundle)
        self.assertIsInstance(cloned, Bundle)
        self.assertEqual(cloned.name, 'bundle')
        self.assertEqual(cloned.description, 'description')
        self.assertIsNot(cloned.mounts[0], bundle.mounts[0])
        self.assertIsInstance(cloned.mounts[0], mount)

        cloned = bundle.clone(name='new')

        self.assertIsNot(cloned, bundle)
        self.assertIsInstance(cloned, Bundle)
        self.assertEqual(cloned.name, 'new')

    def test_description(self):
        example_mount = mount(self.Example, self.ExampleController)
        bundle = Bundle('bundle', example_mount)
        desc = bundle.describe()

        self.assert_viable_description(desc, 'bundle')
        self.assertEqual(set(desc['versions'].keys()), set(['1.0', '1.1', '2.0', '2.1']))

        bundle = Bundle('bundle', example_mount, description='description')
        desc = bundle.describe()

        self.assert_viable_description(desc, 'bundle')
        self.assertEqual(desc['description'], 'description')

    def test_description_with_targets(self):
        bundle = Bundle('bundle',
            mount(self.Example, self.ExampleController),
            mount(self.Another, self.AnotherController),
        )
        desc = bundle.describe(targets=['example'])

        self.assert_viable_description(desc, 'bundle')
        for subdesc in desc['versions'].values():
            self.assertEqual(set(subdesc.keys()), set(['example']))

        desc = bundle.describe(targets='another')

        self.assert_viable_description(desc, 'bundle')
        for subdesc in desc['versions'].values():
            self.assertEqual(set(subdesc.keys()), set(['another']))

        desc = bundle.describe(targets='example another')

        self.assert_viable_description(desc, 'bundle')
        for subdesc in desc['versions'].values():
            self.assertEqual(set(subdesc.keys()), set(['example', 'another']))

    def test_enumerate_resources(self):
        bundle = Bundle('bundle',
            mount(self.Example, self.ExampleController),
            mount(self.Another, self.AnotherController),
        )
        resources = list(bundle.enumerate_resources())

        expected_values = [
            ('/bundle/1.0/another', self.another_1, self.another_controller_1_0),
            ('/bundle/1.0/example', self.example_1, self.example_controller_1_0),
            ('/bundle/1.1/another', self.another_1, self.another_controller_1_0),
            ('/bundle/1.1/example', self.example_1, self.example_controller_1_1),
            ('/bundle/2.0/another', self.another_1, self.another_controller_1_0),
            ('/bundle/2.0/example', self.example_2, self.example_controller_2_0),
            ('/bundle/2.1/another', self.another_1, self.another_controller_1_0),
            ('/bundle/2.1/example', self.example_2, self.example_controller_2_1),
        ]

        for resource, expected in zip(resources, expected_values):
            self.assertEqual(resource[0].address, expected[0])
            self.assertIs(resource[1], expected[1])
            self.assertIs(resource[2], expected[2])

    def test_slice(self):
        bundle = Bundle('bundle',
            mount(self.Example, self.ExampleController),
            mount(self.Another, self.AnotherController),
        )

        self.assertEqual(bundle.slice(), [(1, 0), (1, 1), (2, 0), (2, 1)])

        self.assertEqual(bundle.slice(version=(1, 0)), [(1, 0)])
        self.assertEqual(bundle.slice(version=(3, 0)), [])

        self.assertEqual(bundle.slice(min_version=(0, 0)), [(1, 0), (1, 1), (2, 0), (2, 1)])
        self.assertEqual(bundle.slice(min_version=(1, 0)), [(1, 0), (1, 1), (2, 0), (2, 1)])
        self.assertEqual(bundle.slice(min_version=(1, 1)), [(1, 1), (2, 0), (2, 1)])
        self.assertEqual(bundle.slice(min_version=(1, 2)), [(2, 0), (2, 1)])
        self.assertEqual(bundle.slice(min_version=(2, 0)), [(2, 0), (2, 1)])
        self.assertEqual(bundle.slice(min_version=(2, 1)), [(2, 1)])
        self.assertEqual(bundle.slice(min_version=(2, 2)), [])

        self.assertEqual(bundle.slice(max_version=(3, 0)), [(1, 0), (1, 1), (2, 0), (2, 1)])
        self.assertEqual(bundle.slice(max_version=(2, 2)), [(1, 0), (1, 1), (2, 0), (2, 1)])
        self.assertEqual(bundle.slice(max_version=(2, 1)), [(1, 0), (1, 1), (2, 0), (2, 1)])
        self.assertEqual(bundle.slice(max_version=(2, 0)), [(1, 0), (1, 1), (2, 0)])
        self.assertEqual(bundle.slice(max_version=(1, 2)), [(1, 0), (1, 1)])
        self.assertEqual(bundle.slice(max_version=(1, 1)), [(1, 0), (1, 1)])
        self.assertEqual(bundle.slice(max_version=(1, 0)), [(1, 0)])
        self.assertEqual(bundle.slice(max_version=(0, 1)), [])

        self.assertEqual(bundle.slice(min_version=(1, 0), max_version=(2, 1)), [(1, 0), (1, 1), (2, 0), (2, 1)])
        self.assertEqual(bundle.slice(min_version=(1, 1), max_version=(2, 0)), [(1, 1), (2, 0)])
