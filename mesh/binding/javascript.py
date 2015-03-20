import json
import os

from scheme import Field

from mesh.constants import *
from mesh.transport.http import STATUS_CODES
from mesh.util import get_package_data, string, write_file

class JavascriptConstructor(object):
    RESERVED_WORDS = ['delete', 'default', 'export']

    def __init__(self, indent=4, constructor_attr=None):
        self.constructor_attr = constructor_attr
        self.indent = ' ' * indent

    def construct(self, value, indent=0, initial_indent=0):
        source = self._construct_value(value, indent)
        if isinstance(source, list):
            if initial_indent > 0:
                source[0] = '%s%s' % (self.indent * initial_indent, source[0])
            if indent > 0:
                source[-1] = '%s%s' % (self.indent * indent, source[-1])
            source = '\n'.join(source)
        return source

    def _construct_array(self, obj, indent):
        inner_indent = self.indent * (indent + 1)
        single_line = True

        lines = []
        for value in obj:
            description = self._construct_value(value, indent + 1)
            if isinstance(description, list):
                single_line = False
                lines.append('%s%s' % (inner_indent, description[0]))
                lines.extend(description[1:-1])
                lines.append('%s%s,' % (inner_indent, description[-1]))
            else:
                lines.append('%s%s,' % (inner_indent, description))

        if single_line:
            single_line = '[' + ', '.join(l.strip().rstrip(',') for l in lines) + ']'
            if len(single_line) <= 60:
                return single_line

        if lines[-1][-1] == ',':
            lines[-1] = lines[-1][:-1]
        return ['['] + lines + [']']

    def _construct_object(self, obj, indent):
        inner_indent = self.indent * (indent + 1)
        singles, multiples = [], []

        constructor = None
        if self.constructor_attr in obj:
            constructor = obj.pop(self.constructor_attr)

        for key, value in sorted(obj.items()):
            if isinstance(key, string) and (key in self.RESERVED_WORDS or ':' in key
                    or '-' in key or '/' in key):
                key = '"%s"' % key
            description = self._construct_value(value, indent + 1)
            if isinstance(description, list):
                multiples.append('%s%s: %s' % (inner_indent, key, description[0]))
                multiples.extend(description[1:-1])
                multiples.append('%s%s,' % (inner_indent, description[-1]))
            else:
                singles.append('%s%s: %s,' % (inner_indent, key, description))

        prefix = '{'
        if constructor:
            prefix = '%s({' % constructor

        lines = [prefix] + singles + multiples
        if lines[-1][-1] == ',':
            lines[-1] = lines[1][:-1]

        suffix = '}'
        if constructor:
            suffix += ')'

        return lines + [suffix]

    def _construct_value(self, value, indent):
        if isinstance(value, dict):
            return self._construct_object(value, indent)
        elif isinstance(value, (list, tuple)):
            return self._construct_array(value, indent)
        else:
            return json.dumps(value)

class Generator(object):
    """Generates javascript bindings."""

    FIELDS = {

    }
    IGNORED_ATTRS = ('description', 'notes', 'structural', '__type__', 'operators')
    MODEL_TMPL = get_package_data('mesh.binding', 'templates/model.js.tmpl')

    def __init__(self, template_dir=None, mimetype=None):
        self.constructor = JavascriptConstructor(constructor_attr='__type__')
        self.mimetype = mimetype or JSON
        self.template_dir = template_dir

    def generate(self, bundle, omissions=None):
        description = bundle.describe(verbose=True, omissions=omissions)
        files = {}

        self._generate_versions(bundle, description['versions'], files)
        return {bundle.name: files}

    def _generate_versions(self, bundle, versions, files):
        for version, candidates in versions.items():
            items = files[version] = {}
            for name, candidate in candidates.items():
                if candidate['__subject__'] = 'resource':
                    items['%s.js' % name] = self._construct_resource(candidate, bundle.name)
                elif candidate['__subject__'] == 'bundle':
                    subitems = items[candidate['name']] = {}
                    self._generate_versions(bundle, candidate['versions'], subitems)

    def _construct_field(self, field):
        specification = {'__type__': self.FIELDS[field['__type__']]}
        for name, value in field.items():
            if name not in self.IGNORED_ATTRS:
                if isinstance(value, dict) and '__type__' in value:
                    value = self._construct_field(value)
                specification[name] = value

        if field.get('structural'):
            specification.update(Field.visit(field, self._construct_field))
        return specification

    def _construct_endpoint(self, endpoint, bundle):
        mimetype = self.mimetype
        if endpoint['endpoint'][0] == GET:
            mimetype = URLENCODED
