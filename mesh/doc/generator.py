import os
import shutil
import textwrap

from scheme import *
from scheme.doc.generator import *

from mesh.address import *
from mesh.bundle import *
from mesh.constants import *
from mesh.resource import *
from mesh.util import *

STATUS_CODES = (
    (OK, '200 OK'),
    (CREATED, '201 Created'),
    (ACCEPTED, '202 Accepted'),
    (SUBSET, '203 Subset'),
    (PARTIAL, '206 Partial'),
    (BAD_REQUEST, '400 Bad Request'),
    (FORBIDDEN, '403 Forbidden'),
    (NOT_FOUND, '404 Not Found'),
    (METHOD_NOT_ALLOWED, '405 Method Not Allowed'),
    (INVALID, '406 Invalid'),
    (CONFLICT, '409 Conflict'),
    (GONE, '410 Gone'),
    (SERVER_ERROR, '500 Internal Server Error'),
    (UNIMPLEMENTED, '501 Not Implemented'),
    (UNAVAILABLE, '503 Service Unavailable'),
)

RESOURCE_HEADER = """
.. default-domain:: mesh
"""

class DocumentationGenerator(DocumentationGenerator):
    CONF_TEMPLATE = get_package_data('mesh.doc', 'templates/sphinx-conf.py.tmpl')
    CSS_PATH = get_package_path('mesh.doc', 'templates/mesh.css.tmpl')
    INDEX_TEMPLATE = get_package_data('mesh.doc', 'templates/index.rst.tmpl')
    ROOT_TEMPLATE = get_package_data('mesh.doc', 'templates/root.rst.tmpl')
    SECTION_TEMPLATE = get_package_data('mesh.doc', 'templates/section.rst.tmpl')

    flag_attrs = {
        'deferred': [],
        'ignore_null': [],
        'nonnull': [],
        'readonly': [],
        'required': ['schema'],
    }

    def __init__(self, root_path, nested=False):
        self.nested = nested
        self.root_path = root_path

    def generate(self, bundle):
        if isinstance(bundle, Bundle):
            bundle = bundle.describe(verbose=True)

        self._prepare_root()
        if self.nested:
            bundle_path = os.path.join(str(self.root_path), bundle['name'])
            if not os.path.exists(bundle_path):
                os.mkdir(bundle_path)
        else:
            bundle_path = str(self.root_path)

        sections = []
        for version, resources in sorted(bundle['versions'].items(), reverse=True):
            refs = ['']

            version_path = os.path.join(bundle_path, version)
            if not os.path.exists(version_path):
                os.mkdir(version_path)

            for name, resource in sorted(resources.items()):
                content = self._document_resource(resource, version)
                with open(os.path.join(version_path, '%s.rst' % name), 'w+') as openfile:
                    openfile.write(content)
                refs.append(os.path.join(version, name))

            sections.append(self.SECTION_TEMPLATE % {
                'title': 'Version %s' % version,
                'refs': '\n    '.join(sorted(refs)),
            })

        self._generate_index(bundle, bundle_path, sections)

    def _collate_fields(self, fields, top=('id',)):
        for name in top:
            if name in fields:
                yield name, fields[name]

        buckets = [], [], [], [], [], []
        for name, field in sorted(fields.items()):
            if name not in top:
                structural = field.get('structural', False)
                if field.get('readonly'):
                    if structural:
                        buckets[5].append((name, field))
                    else:
                        buckets[4].append((name, field))
                elif field.get('required'):
                    if structural:
                        buckets[1].append((name, field))
                    else:
                        buckets[0].append((name, field))
                else:
                    if structural:
                        buckets[3].append((name, field))
                    else:
                        buckets[2].append((name, field))

        for bucket in buckets:
            for name, field in bucket:
                yield name, field

    def _collate_schema_fields(self, fields):
        if 'id' in fields:
            yield 'id', fields['id']

        buckets = [], [], [], []
        for name, field in sorted(fields.items()):
            if name != 'id':
                structural = field.get('structural', False)
                if field.get('readonly'):
                    if structural:
                        buckets[3].append((name, field))
                    else:
                        buckets[2].append((name, field))
                else:
                    if structural:
                        buckets[1].append((name, field))
                    else:
                        buckets[0].append((name, field))

        for bucket in buckets:
            for name, field in bucket:
                yield name, field

    def _document_endpoint(self, version, endpoint):
        block = directive('endpoint', endpoint['name'])
        if endpoint.get('title'):
            block.set('title', endpoint['title'])
        

        if endpoint.get('description'):
            block.append(endpoint['description'])
        if endpoint['schema']:
            block.append(self._document_field('ENDPOINT', endpoint['schema'],
                'endpoint', sectional=True))

        responses = endpoint['responses']
        for status, status_line in STATUS_CODES:
            if status in responses:
                response = responses[status]
                if response['schema']:
                    block.append(self._document_field(status_line, response['schema'],
                        'response', sectional=True))
        
        return block

    def _document_resource(self, resource, version):
        block = directive('resource', resource['name'], resource['title'])
        block.set('version', version)

        description = resource.get('description')
        if description:
            block.append(description)

        schema = directive('structure', 'SCHEMA')
        for name, field in self._collate_schema_fields(resource['schema']):
            schema.append(self._document_field(name, field, 'schema'))

        block.append(schema)
        for name, endpoint in sorted(resource['endpoints'].items()):
            block.append(self._document_endpoint(version, endpoint))

        return RESOURCE_HEADER + block.render()

    def _generate_index(self, bundle, bundle_path, sections):
        content = self.INDEX_TEMPLATE % {
            'name': bundle['name'],
            'description': bundle.get('description', ''),
            'sections': '\n\n'.join(sections),
        }

        with open(os.path.join(bundle_path, 'index.rst'), 'w+') as openfile:
            openfile.write(content)

    def _prepare_root(self):
        root = str(self.root_path)
        if not os.path.exists(root):
            os.mkdir(root)

        static = os.path.join(root, '_static')
        if not os.path.exists(static):
            os.mkdir(static)

        css = os.path.join(static, 'mesh.css')
        if not os.path.exists(css):
            shutil.copyfile(self.CSS_PATH, css)

        templates = os.path.join(root, '_templates')
        if not os.path.exists(templates):
            os.mkdir(templates)

        conf = os.path.join(root, 'conf.py')
        if not os.path.exists(conf):
            write_file(conf, self.CONF_TEMPLATE)

        if not self.nested:
            return

        root_index = os.path.join(root, 'index.rst')
        if not os.path.exists(root_index):
            write_file(root_index, self.ROOT_TEMPLATE)
