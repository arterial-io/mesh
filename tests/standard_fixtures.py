from scheme import *
from mesh.standard import *

class Example(Resource):
    name = 'example'
    version = 1
    endpoints = 'create delete get put query update'

    class schema:
        required = Text(required=True, nonnull=True, sortable=True,
            operators=['eq', 'ne', 'pre', 'suf', 'cnt'])
        deferred = Text(deferred=True)
        default = Integer(default=1)
        constrained = Integer(minimum=2, maximum=4)
        readonly = Integer(readonly=True)
        boolean = Boolean()
        integer = Integer(sortable=True, operators=['eq', 'in', 'gte', 'gt', 'lte', 'lt'])

class ExampleController(Controller):
    resource = Example
    version = (1, 0)

ExampleBundle = Bundle('examples',
    mount(Example, ExampleController),
)
