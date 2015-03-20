from scheme.doc.domain import *

_option_spec = FieldDefinition.option_spec
_option_spec.update({
    'deferred': directives.flag,
    'readonly': directives.flag,
})

class FieldDefinition(FieldDefinition):
    flags = ('deferred', 'ignore_null', 'nonnull', 'polymorphic', 'readonly',
        'required', 'unique')
    option_spec = _option_spec

class EndpointDefinition(Directive):
    has_content = True
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        'title': directives.unchanged,
        'endpoint': directives.unchanged,
    }

    def run(self):
        name = title = self.arguments[0]
        if 'title' in self.options:
            title = '%s: %s' % (title, self.options['title'])

        paragraph = nodes.paragraph('', '')
        if 'endpoint' in self.options:
            paragraph += strong(self.options['endpoint'])

        block = section(name, title)
        block += paragraph

        self.state.nested_parse(self.content, self.content_offset, block)
        return [block]

class ResourceDefinition(Directive):
    has_content = True
    required_arguments = 2
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {
        'module': directives.unchanged,
        'version': directives.unchanged,
    }

    def run(self):
        name, title = self.arguments
        definition = section(name, '%s (%s)' % (title, self.options['version']))

        self.state.nested_parse(self.content, self.content_offset, definition)
        return [definition]

class ResourceIndex(Index):
    name = 'resourceindex'
    localname = 'Resource Index'
    shortname = 'resources'

    def generate(self, docnames=None):
        pass

class MeshDomain(Domain):
    name = 'mesh'
    label = 'Mesh'
    object_types = {
        'resource': ObjType('resource', 'resource'),
    }
    directives = {
        'endpoint': EndpointDefinition,
        'field': FieldDefinition,
        'resource': ResourceDefinition,
        'structure': StructureDefinition,
    }
    roles = {}
    initial_data = {
        'objects': {},
        'resources': {},
    }
    indices = []

    def get_objects(self):
        for refname, obj in self.data['objects'].items():
            yield (refname, refname, obj[1], obj[0], refname, 1)

def setup(app):
    app.add_domain(MeshDomain)
