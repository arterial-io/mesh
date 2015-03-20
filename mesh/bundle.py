from scheme.fields import Field

from mesh.address import *
from mesh.exceptions import *
from mesh.resource import Controller
from mesh.util import LogHelper, import_object, string

log = LogHelper(__name__)

def format_version(version):
    if isinstance(version, string):
        return version
    return '%d.%d' % version

def parse_version(version, silent=False):
    if not isinstance(version, string):
        return version

    try:
        major, minor = version.split('.')
        return (int(major), int(minor))
    except Exception:
        if silent:
            return version
        else:
            raise

class mount(object):
    """Mounts a resource/controller pair within a bundle."""

    def __init__(self, resource, controller=None, min_version=None, max_version=None):
        self.constructed = False
        self.controller = controller
        self.max_version = max_version
        self.min_version = min_version
        self.resource = resource

    def __repr__(self):
        return 'mount(%r, %r)' % (self.resource.name, identify_class(self.controller))

    def clone(self):
        return mount(self.resource, self.controller, self.min_version, self.max_version)

    def construct(self, subject=None):
        self.constructed = False

        resource = self.resource
        if isinstance(resource, string):
            resource = import_object(resource, True)
            if resource:
                self.resource = resource

        if not resource:
            return False

        controller = self.controller
        if isinstance(controller, string):
            try:
                controller = import_object(controller)
            except Exception:
                log('exception', 'failed to import %r for %r', controller, subject)
                controller = None

        if not controller:
            controller = resource.configuration.create_controller(resource)
        if not controller:
            return False

        self.controller = controller
        self.min_version = self._validate_version(resource, controller,
            self.min_version, 'minimum_version')
        self.max_version = self._validate_version(resource, controller,
            self.max_version, 'maximum_version')

        self.versions = []
        for candidate in controller.versions.keys():
            if candidate >= self.min_version and candidate <= self.max_version:
                self.versions.append(candidate)

        self.versions.sort()
        self.constructed = True
        return True

    def get(self, version):
        for candidate in reversed(self.versions):
            if version >= candidate:
                controller = self.controller.versions[candidate]
                return controller.resource.name, (controller.resource, controller)

    def _validate_version(self, resource, controller, value, attr):
        if value is not None:
            if isinstance(value, tuple) and len(value) == 2:
                if controller:
                    if value in controller.versions:
                        return value
                    else:
                        raise SpecificationError()
                elif value[0] in resource.versions and value[1] == 0:
                    return value
                else:
                    raise SpecificationError()
            else:
                raise SpecificationError()
        elif controller:
            return getattr(controller, attr)
        else:
            return (getattr(resource, attr), 0)

class recursive_mount(mount):
    """A recursive mount.

    :param bundles: dict (version -> bundle instances)
    """

    def __init__(self, bundles):
        self.bundles = bundles

    def clone(self):
        return recursive_mount(self.bundles)

    def construct(self, bundle):
        self.versions = sorted(self.bundles.keys())
        return True

    def get(self, version):
        for candidate in reversed(self.versions):
            if version >= candidate:
                bundle = self.bundles[candidate]
                return bundle.name, bundle

class Bundle(object):
    """A bundle of resource/controller pairs."""

    def __init__(self, name, *mounts, **params):
        self.description = params.get('description', None)
        self.name = name
        self.ordering = []
        self.versions = {}

        self.mounts = []
        if mounts:
            self.attach(mounts)

    def attach(self, mounts):
        for mount in mounts:
            if mount.construct(self):
                self.mounts.append(mount)

        if self.mounts:
            self._collate_mounts()

    def clone(self, name=None, transformer=None, description=None):
        mounts = []
        for mount in self.mounts:
            mount = mount.clone()
            if transformer:
                mount = transformer(mount)
                if mount:
                    mounts.append(mount)
            else:
                mounts.append(mount)

        params = {'description': description or self.description}
        return Bundle(name or self.name, *mounts, **params)

    def describe(self, address=None, targets=None, verbose=False, omissions=None):
        """Constructs and returns a serializable description of this bundle.

        :param targets: Optional, default is ``None``; a list of resource names within this bundle
            to which to limit the constructed description, specified as either a ``list`` or a
            space-delimited ``str``.

        :param boolean verbose: Optional, default is ``False``; if ``True``, the constructed
            description will contain all attribute/value pairs on nested objects, even those
            attributes which have the default value. When ``False``, attributes which have a
            default value are omitted from the description.
        """

        if not address:
            address = Address()

        if isinstance(targets, string):
            targets = targets.split(' ')

        description = {'__subject__': 'bundle', 'name': self.name, 'versions': {}}
        if verbose or self.description:
            description['description'] = self.description

        if not address.bundle:
            description['__version__'] = 1

        for version, resources in sorted(self.versions.items()):
            items = description['versions'][format_version(version)] = {}
            for name, candidate in resources.items():
                if not targets or name in targets:
                    if isinstance(candidate, Bundle):
                        items[name] = candidate.describe(address.extend(self.name, version),
                            verbose=verbose, omissions=omissions)
                    else:
                        omitted = None
                        if omissions:
                            pass #FIX
                        resource, controller = candidate
                        items[name] = resource.describe(controller, 
                            address.extend(self.name, version), verbose, omitted)

        return description

    def enumerate_resources(self, address=None):
        if not address:
            address = Address()

        for version, candidates in sorted(self.versions.items()):
            subaddress = address.extend(self.name, version)
            for name, candidate in sorted(candidates.items()):
                if isinstance(candidate, Bundle):
                    for result in candidate.enumerate_resources(subaddress):
                        yield result
                else:
                    resource, controller = candidate
                    yield subaddress.clone(resource=resource.name), resource, controller

    def slice(self, version=None, min_version=None, max_version=None):
        versions = self.versions
        if version is not None:
            if version in self.versions:
                return [version]
            else:
                return []

        versions = sorted(versions.keys())
        if min_version is not None:
            try:
                while versions[0] < min_version:
                    versions = versions[1:]
            except IndexError:
                return versions

        if max_version is not None:
            try:
                while versions[-1] > max_version:
                    versions = versions[:-1]
            except IndexError:
                return versions

        return versions

    def specify(self):
        return Specification(self.describe())

    def _collate_mounts(self):
        ordering = set()
        for mount in self.mounts:
            ordering.update(mount.versions)

        self.ordering = sorted(ordering)
        self.versions = {}

        for mount in self.mounts:
            for version in self.ordering:
                contribution = mount.get(version)
                if contribution:
                    name, contribution = contribution
                    if version not in self.versions:
                        self.versions[version] = {name: contribution}
                    elif name not in self.versions[version]:
                        self.versions[version][name] = contribution
                    else:
                        raise SpecificationError()

class Specification(object):
    """A bundle specification for a particular version."""

    def __init__(self, specification):
        self.cache = {}
        self.description = specification.get('description')
        self.name = specification['name']

        self.versions = {}
        for version, resources in specification['versions'].items():
            self.versions[parse_version(version)] = resources
            for candidate in resources.values():
                if candidate['__subject__'] == 'bundle':
                    self._parse_bundle(candidate)
                elif candidate['__subject__'] == 'resource':
                    self._parse_resource(candidate)

    def __repr__(self):
        return 'Specification(name=%r)' % self.name

    def find(self, address):
        if isinstance(address, string):
            address = Address.parse(address)
        if not address.validate(bundle=True):
            raise ValueError(address)

        signature = address.render('ebr')
        try:
            return self.cache[signature]
        except KeyError:
            pass

        steps = list(address.bundle)
        if steps.pop(0) != self.name:
            raise KeyError(signature)

        subject = None
        versions = self.versions

        while steps:
            version = steps.pop(0)
            if version in versions:
                subject = versions[version]
                if steps:
                    name = steps.pop(0)
                    if name in subject and subject[name]['__subject__'] == 'bundle':
                        versions = subject[name]['__subject__']
                    else:
                        raise KeyError(signature)
            else:
                raise KeyError(signature)
        
        resource = address.resource
        if resource:
            if resource in subject:
                subject = subject[resource]
            else:
                raise KeyError(signature)

        endpoint = address.endpoint
        if endpoint:
            if resource and endpoint in subject['endpoints']:
                subject = subject['endpoints'][endpoint]
            else:
                raise KeyError(signature)

        self.cache[signature] = subject
        return subject

    def _parse_bundle(self, bundle):
        versions = {}
        for version, resources in bundle['versions'].items():
            versions[parse_version(version)] = resources
            for resource in resources.values():
                self._parse_resource(resource)

        bundle['versions'] = versions

    def _parse_resource(self, resource):
        schema = resource.get('schema')
        if isinstance(schema, dict):
            for name, field in schema.items():
                schema[name] = Field.reconstruct(field)

        endpoints = resource.get('endpoints')
        if isinstance(endpoints, dict):
            for endpoint in endpoints.values():
                if 'schema' in endpoint and endpoint['schema']:
                    endpoint['schema'] = Field.reconstruct(endpoint['schema'])
                for response in endpoint['responses'].values():
                    if 'schema' in response and response['schema']:
                        response['schema'] = Field.reconstruct(response['schema'])
