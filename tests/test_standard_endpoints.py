from datetime import date, time
from unittest import TestCase

from mesh.standard import *
from mesh.transport.internal import *

class TestCreateEndpoint(TestCase):
    def test_construction(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'create'

            class schema:
                attr = Text()
                readonly = Text(readonly=True)


        endpoint = Example.endpoints['create']
        self.assertTrue(endpoint.auto_constructed)
        self.assertFalse(endpoint.batch)
        self.assertEqual(endpoint.method, POST)
        self.assertEqual(endpoint.name, 'create')
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['attr']))
        self.assertFalse(endpoint.specific)
        self.assertTrue(endpoint.subject_required)
        self.assertEqual(endpoint.title, 'Creating a new example')

        ok = endpoint.responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id']))

    def test_id_oncreate(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'create'

            class schema:
                id = Text(oncreate=True)
                attr = Text()

        endpoint = Example.endpoints['create']
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['id', 'attr']))

    def test_field_oncreate(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'create'

            class schema:
                attr = Text()
                update_only = Text(oncreate=False)

        endpoint = Example.endpoints['create']
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['attr']))

    def test_returning(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'create'

            class schema:
                attr = Text()

            class create(Resource.create):
                support_returning = True

        endpoint = Example.endpoints['create']
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['attr', 'returning']))

        ok = endpoint.responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id', 'attr']))

    def test_returned_field(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'create'

            class schema:
                attr = Text(returned='create')


        ok = Example.endpoints['create'].responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id', 'attr']))

class TestDeleteEndpoint(TestCase):
    def test_construction(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'delete'

            class schema:
                attr = Text()

        endpoint = Example.endpoints['delete']
        self.assertTrue(endpoint.auto_constructed)
        self.assertFalse(endpoint.batch)
        self.assertEqual(endpoint.method, DELETE)
        self.assertEqual(endpoint.name, 'delete')
        self.assertIsNone(endpoint.schema)
        self.assertTrue(endpoint.specific)
        self.assertTrue(endpoint.subject_required)
        self.assertEqual(endpoint.title, 'Deleting a specific example')

        ok = endpoint.responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id']))

class TestGetEndpoint(TestCase):
    def test_construction(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'get'

            class schema:
                attr = Text()

        endpoint = Example.endpoints['get']
        self.assertTrue(endpoint.auto_constructed)
        self.assertFalse(endpoint.batch)
        self.assertEqual(endpoint.method, GET)
        self.assertEqual(endpoint.name, 'get')
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['exclude', 'include', 'fields']))
        self.assertTrue(endpoint.specific)
        self.assertTrue(endpoint.subject_required)
        self.assertEqual(endpoint.title, 'Getting a specific example')

        schema = endpoint.schema.structure
        self.assertEqual(set(schema['fields'].item.enumeration), set(['id', 'attr']))
        self.assertEqual(set(schema['exclude'].item.enumeration), set(['attr']))
        self.assertEqual(set(schema['include'].item.enumeration), set(['id', 'attr']))

        ok = endpoint.responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id', 'attr']))

class TestPutEndpoint(TestCase):
    def test_construction(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'put'

            class schema:
                attr = Text()
                readonly = Text(readonly=True)

        endpoint = Example.endpoints['put']
        self.assertTrue(endpoint.auto_constructed)
        self.assertFalse(endpoint.batch)
        self.assertEqual(endpoint.method, PUT)
        self.assertEqual(endpoint.name, 'put')
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['attr']))
        self.assertTrue(endpoint.specific)
        self.assertFalse(endpoint.subject_required)
        self.assertEqual(endpoint.title, 'Putting a specific example')

        ok = endpoint.responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id']))

    def test_field_onput(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'put'

            class schema:
                attr = Text()
                update_only = Text(onput=False)

        endpoint = Example.endpoints['put']
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['attr']))

    def test_returning(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'put'

            class schema:
                attr = Text()

            class put(Resource.put):
                support_returning = True

        endpoint = Example.endpoints['put']
        self.assertEqual(set(endpoint.schema.structure.keys()), set(['attr', 'returning']))

        ok = endpoint.responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id', 'attr']))

    def test_returned_field(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'put'

            class schema:
                attr = Text(returned='put')

        ok = Example.endpoints['put'].responses[OK]
        self.assertEqual(set(ok.schema.structure.keys()), set(['id', 'attr']))

class TestQueryEndpoint(TestCase):
    def test_construction(self):
        class Example(Resource):
            name = 'example'
            version = 1
            endpoints = 'query'

            class schema:
                alpha = Text(sortable=True, operators=['equal', 'in'])
                beta = Integer(sortable=True, operators=['gt', 'lt'])

        endpoint = Example.endpoints['query']
        self.assertTrue(endpoint.auto_constructed)
        self.assertFalse(endpoint.batch)
        self.assertEqual(endpoint.method, GET)
        self.assertEqual(endpoint.name, 'query')
        self.assertFalse(endpoint.specific)
        self.assertTrue(endpoint.subject_required)
        self.assertEqual(endpoint.title, 'Querying examples')

        schema = endpoint.schema.structure
        self.assertEqual(set(schema.keys()), set(['exclude', 'fields', 'include', 'limit', 'offset', 'total', 'sort', 'query']))
        self.assertEqual(set(schema['exclude'].item.enumeration), set(['alpha', 'beta']))
        self.assertEqual(set(schema['fields'].item.enumeration), set(['id', 'alpha', 'beta']))
        self.assertEqual(set(schema['include'].item.enumeration), set(['id','alpha', 'beta']))
        self.assertIsInstance(schema['limit'], Integer)
        self.assertIsInstance(schema['offset'], Integer)
        self.assertIsInstance(schema['total'], Boolean)
        self.assertEqual(set(schema['sort'].item.enumeration), set(['alpha', 'alpha+', 'alpha-', 'beta', 'beta+', 'beta-']))
        self.assertEqual(set(schema['query'].structure.keys()), set(['alpha', 'alpha__in', 'beta__gt', 'beta__lt']))

        ok = endpoint.responses[OK].schema.structure
        self.assertEqual(set(ok.keys()), set(['total', 'resources']))
