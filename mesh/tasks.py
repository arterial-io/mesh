from bake import *
from scheme import *
from scheme.util import StructureFormatter

class GenerateDocs(Task):
    name = 'mesh.docs'
    description = 'generate documentation for a mesh bundle'
    parameters = {
        'bundle': Object(description='module path of bundle', required=True),
        'docroot': FilePath(description='path to docroot', required=True),
        'nocache': Boolean(default=False),
        'sphinx': Text(default='sphinx-build'),
        'view': Boolean(description='view documentation after build', default=False),
    }

    def run(self, runtime):
        from mesh.doc.generator import DocumentationGenerator
        DocumentationGenerator(self['docroot']).generate(self['bundle'])

        runtime.execute('sphinx.html', sourcedir=self['docroot'], view=self['view'],
            nocache=self['nocache'], binary=self['sphinx'])

class GenerateSpecification(Task):
    name = 'mesh.spec'
    description = 'generate the specification for a bundle'
    parameters = {
        'bundle': Object(required=True),
        'format': Enumeration('json python', default='python'),
        'path': FilePath(required=True),
        'targets': Sequence(Text()),
    }

    def run(self, runtime):
        description = self['bundle'].describe(self['targets'])
        if self['format'] == 'python':
            content = StructureFormatter().format(description)
        elif self['format'] == 'json':
            content = Json.serialize(description)
        self['path'].write_bytes(content)
