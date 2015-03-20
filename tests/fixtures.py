from mesh.bundle import *
from mesh.constants import *
from mesh.endpoint import *
from mesh.resource import *
from scheme import *
from scheme.common import Errors

__all__ = ('Example', 'ExampleBundle', 'ExampleController')

def construct_example_endpoint(resource):
    return Endpoint(name='test', method=POST, auto_constructed=True, resource=resource,
        schema=Structure({'id': Integer()}),
        responses={OK: Structure({'id': Integer()}), INVALID: Errors})

ExampleConfiguration = Configuration({
    'test': construct_example_endpoint,
}, ['test'])

class Example(Resource):
    configuration = ExampleConfiguration
    name = 'example'
    version = 1

    class schema:
        attr = Text()

    class operation:
        specific = True
        method = 'OPERATION'
        schema = {'attr': Text()}
        responses = {OK: {'id': Integer()}, INVALID: Errors}

    class will_raise_exception:
        pass

class ExampleController(Controller):
    resource = Example
    version = (1, 0)

    def acquire(self, subject):
        return subject

    def test(self, request, response, subject, data):
        return data

    def operation(self, request, response, subject, data):
        return {'id': int(subject)}

    def will_raise_exception(self, request, response, subject, data):
        raise Exception('testing')

ExampleBundle = Bundle('examples',
    mount(Example, ExampleController),
)
