import sys
from imp import new_module
from inspect import getsource
from os.path import exists, join as joinpath
from types import ModuleType

from scheme.surrogate import surrogate
from scheme.util import StructureFormatter

from mesh.address import Address
from mesh.bundle import Bundle, Specification
from mesh.constants import *
from mesh.exceptions import *
from mesh.transport.base import Client
from mesh.util import get_package_data, import_object, string

class ReadOnlyError(Exception):
    """..."""

class Attribute(object):
    """A model attribute."""

    def __init__(self, name, field):
        self.field = field
        self.name = name

    def __get__(self, instance, owner):
        if instance is not None:
            try:
                return instance._data[self.name]
            except KeyError:
                return None
        else:
            return self

    def __set__(self, instance, value):
        if isinstance(value, Model):
            value = value.id
        instance._data[self.name] = value

class CompositeIdentifier(object):
    """A model attribute for composite identifiers."""

    def __init__(self, name, keys):
        self.keys = keys
        self.name = name

    def __get__(self, instance, owner):
        if instance is not None:
            values = []
            for key in self.keys:
                value = instance._data.get(key)
                if value is not None:
                    values.append(value)
                else:
                    return None
            else:
                return ';'.join(values)
        else:
            return self

    def __set__(self, instance, value):
        values = value.split(';')
        for i, key in enumerate(self.keys):
            instance._data[key] = values[i]

class Query(object):
    """A resource query."""

    def __init__(self, model, **params):
        self.model = model
        self.params = params

    def __iter__(self):
        return iter(self._execute_query())

    def all(self):
        """Executes this query and returns a list containing all of the resulting model
        instances. If the query results in zero instances, an empty list will be returned."""

        return self._execute_query()

    def clone(self, **params):
        """Constructs and returns a clone of this query, applying all keyword parameters
        to the clone. If any of the keyword parameters has a value of ``None``, that
        parameter is removed from this query, instead of remaining with a ``None`` value."""

        parameters = self.params.copy()
        for name, value in params.items():
            if value is None and name in parameters:
                del parameters[name]
            else:
                parameters[name] = value

        return type(self)(self.model, **parameters)

    def one(self):
        """Executes this query and returns the first model instance resulting. If the query
        does not result in any model instances, ``None`` is returned."""

        results = self._execute_query()
        if results:
            return results[0]

    def _execute_query(self):
        model = self.model
        models = []
        for result in model._get_client().execute(model._resource, 'query',
                None, self.params or None):
            models.append(model(**result))
        return models

class Model(object):
    """A resource model."""

    query_class = Query
    repr_attrs = ('id', 'name', 'status')

    def __init__(self, **params):
        self._data = {}
        for key, value in params.items():
            if key in self._attributes:
                setattr(self, key, value)
            else:
                raise AttributeError(key)

    def __repr__(self):
        attrs = []
        for attr in self.repr_attrs:
            value = getattr(self, attr, None)
            if value is not None:
                attrs.append('%s=%r' % (attr, value))

        classname = type(self).__name__
        return '%s(%s)' % (classname, ', '.join(attrs))

    def construct_surrogate(self, implementation, **params):
        return surrogate.construct(implementation, self._data, *params)

    @classmethod
    def create(cls, **params):
        """Creates a new instance of this resource by submitting the specified parameters in
        a ``create`` request to the host API. If successful, an instance of this model will be
        returned."""

        endpoint = cls._get_endpoint('create')
        parameters = {}

        for field, value in endpoint['schema'].extract(params).items():
            if field in cls._attributes:
                parameters[field] = value

        instance = cls(**parameters)
        return instance.save(endpoint, **params)

    def destroy(self, quiet=False, **params):
        """Attempts to destroy the resource instance represented by this client model by
        submitting a ``delete`` request to the host API.

        :param boolean quiet: Optional, default is ``False``; if ``True``, :exc:`GoneError` will
            not be raised if the host API reports the resource instance represented by this
            client model does not exist.

        :param **params: Optional; additional keyword parameters will be included with the
            `delete` request to the host API.
        """

        endpoint = self._get_endpoint('delete')
        if self.id is None:
            return self

        try:
            response = self._execute_request(endpoint, params or None)
        except GoneError:
            if not quiet:
                raise
        else:
            return response.data

    @classmethod
    def execute(cls, endpoint, data, subject=None):
        return cls._get_client().execute(cls._resource, endpoint, subject, data)

    def extract_dict(self, attrs=None, exclude=None, drop_none=False, **extraction):
        """Constructs and returns a ``dict`` containing field/value pairs extracted from this
        client model. By default, the constructed dictionary will contain values for all
        fields defined by the resource.

        :param attrs: Optional, default is ``None``; the names of the exact set of fields to
            extract from this model, specified as either a ``list`` or as a single
            space-delimited string.

        :param exclude: Optional, default is ``None``; the names of one or more fields to
            exclude from the extraction, specified as either a ``list`` or a single
            space-delimited string. 

        :param boolean drop_none: Optional, default is ``False``; if ``True``, the extracted
            ``dict`` will not contain key/value pairs for those attributes of this model
            which have a value of ``None``.

        :param **params: Optional; additional keyword parameters provide the initial values
            for the extracted dictionary (and might therefore be overridden by values obtained
            from this model).
        """

        if isinstance(attrs, string):
            attrs = attrs.split(' ')
        elif not attrs:
            attrs = self._data.keys()
        if isinstance(attrs, (tuple, list)):
            attrs = dict(zip(attrs, attrs))

        if exclude:
            if isinstance(exclude, string):
                exclude = exclude.split(' ')
            for attr in exclude:
                attrs.pop(attr, None)

        for attr, name in attrs.items():
            value = self._data.get(attr)
            if not (drop_none and value is None):
                extraction[name] = value

        return extraction

    @classmethod
    def generate_model(cls, specification, resource, mixins):
        bases = [cls]
        if mixins:
            for mixin in mixins:
                bases.append(mixin)

        composite_key = resource.get('composite_key')
        namespace = {
            '_composite_key': composite_key,
            '_name': resource['name'],
            '_resource': resource,
            '_specification': specification,
        }

        attributes = namespace['_attributes'] = {}
        if composite_key:
            namespace['id'] = attributes['id'] = CompositeIdentifier('id', composite_key)

        for attr, field in resource['schema'].items():
            if attr not in attributes:
                namespace[attr] = attributes[attr] = Attribute(attr, field)

        return type(str(resource['classname']), tuple(bases), namespace)

    @classmethod
    def get(cls, id, **params):
        """Attempts to get the resource instance identified by ``id`` by submitting a ``get``
        request to the host API. If successful, an instance of this class representing the
        resource instance will be returned.
        
        :param id: The id of the resource instance to get.
        
        :param **params: Optional; additional keyword parameters to include in the ``get``
            request to the host API."""

        if isinstance(id, (list, tuple)):
            attrs = []
            for i, key in enumerate(self._composite_key):
                attrs[key] = id[i]
        else:
            attrs = {'id': id}

        return cls(**attrs).refresh(**params)

    def refresh(self, **params):
        """Attempts to refresh this model instance by submitting a ``get`` request to the host
        API. If successful, this model instance is returned, with the values of the resource
        fields updated to reflect their value on the host.

        :param **params: Optional; additional keyword parameters to include in the ``get``
            request to the host API.
        """

        endpoint = self._get_endpoint('get')
        if self.id is None:
            return self

        response = self._execute_request(endpoint, params or None)
        self._update_model(response.data)
        return self

    def put(self, **params):
        """Attempts to put this model instance by submitting a ``put`` request to the host
        API, which will either create or update the resource instance as appropriate. If
        successful, this model instance is returned.

        :param **params: Optional; additional keyword parameters to include in the ``put``
            request to the host API.
        """

        endpoint = self._get_endpoint('put')
        return self.save(endpoint, **params)

    @classmethod
    def query(cls, **params):
        """Constructs and returns a query instance for this model."""

        return cls.query_class(cls, **params)

    def save(self, _endpoint=None, **params):
        """Attempts to save local changes to this model by submitting either a ``create``
        or ``update`` request to the host API, depending on whether the local instance
        has a valid value for the ``id`` field.
        
        :param **params: Optional; additional keyword parameters to include in the request
            to the host API (potentially overridding the values obtained from this model).
        """

        endpoint = _endpoint
        if not endpoint:
            if getattr(self, 'id', None) is not None:
                endpoint = self._get_endpoint('update')
            else:
                endpoint = self._get_endpoint('create')

        data = endpoint['schema'].extract(self._data)
        if params:
            data.update(params)

        response = self._execute_request(endpoint, data)
        self._update_model(response.data)
        return self

    def set(self, **params):
        """Sets the specified attributes on this model to the specified values, then returns
        this model."""

        for attr, value in params.items():
            setattr(self, attr, value)
        return self

    def update(self, attrs, **params):
        """Updates the attributes of this model with the values from ``attrs``, then saves this
        model, which submits either a ``create`` or ``update`` request to the host API, then
        returns this model.

        :param dict attrs: The attribute/value pairs to update this model with.

        :param **params: Optional; additional keyword parameters to include in the request
            to the host API.
        """

        self._update_model(attrs)
        return self.save(**params)

    def _execute_request(self, endpoint, data=None):
        subject = None
        if endpoint['specific']:
            subject = self.id

        return self._get_client().execute(endpoint, subject, data)

    @classmethod
    def _get_client(cls):
        return Client.get_client(cls._specification)

    @classmethod
    def _get_endpoint(cls, name):
        endpoint = cls._resource['endpoints'].get(name)
        if endpoint:
            return endpoint
        else:
            raise ValueError(name)

    def _update_model(self, data):
        if data:
            self._data.update(data)

class ResourceSet(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

def bind(binding, name, mixin_modules=None):
    """Generates a client binding for the resource identified by ``name``, using the resource
    definition specified by ``binding``.

    :param binding: The resource bundle to bind, specified as either (a) a binding module, either
        pre-generated or generated through the import of a .mesh file; (b) a :class:`Bundle`
        instance; (c) a serialized description of a bundle, as a ``dict``; (d) a
        :class:`mesh.bundle.Specification` instance; or (e) a ``str`` containing the full package
        path to one of the above.

    :param str name: The mesh designation of either a specific versioned resource or a specific
        bundle version

    """

    try:
        provide_binding = binding._provide_binding
    except AttributeError:
        pass
    else:
        return Binding(provide_binding(), mixin_modules).generate(name)

    if isinstance(binding, string):
        binding = import_object(binding)

    if isinstance(binding, ModuleType):
        binding = getattr(binding, 'binding', None)
    elif isinstance(binding, Bundle):
        binding = binding.specify()

    if isinstance(binding, (Specification, dict)):
        binding = Binding(binding, mixin_modules)

    if isinstance(binding, Binding):
        return binding.generate(name)
    else:
        raise TypeError(binding)

class Binding(object):
    """A python binding manager."""

    def __init__(self, specification, mixin_modules=None,
            mixin_classes=None, binding_module='mesh.standard.python'):

        if isinstance(specification, string):
            specification = import_object(specification)
        if isinstance(specification, Bundle):
            specification = specification.specify()
        elif not isinstance(specification, Specification):
            specification = Specification(specification)

        if isinstance(binding_module, string):
            binding_module = import_object(binding_module)

        self.cache = {}
        self.binding_module = binding_module
        self.mixins = {}
        self.specification = specification

        if mixin_classes:
            for mixin_class in mixin_classes:
                self._associate_mixin_class(mixin_class)

        if mixin_modules:
            self._enumerate_mixin_classes(mixin_modules)

    def __repr__(self):
        return 'Binding(%s)' % self.specification.name

    def generate(self, name):
        try:
            return self.cache[name]
        except KeyError:
            pass

        resource = self.specification.find(name)
        if '__subject__' in resource:
            target = self._generate_model(resource)
        else:
            target = ResourceSet()
            for candidate in resource.values():
                if candidate['__subject__'] == 'resource':
                    target[candidate['classname']] = self._generate_model(candidate)

        self.cache[name] = target
        return target

    def _associate_mixin_class(self, mixin_class):
        try:
            targets = mixin_class.mixin
        except Exception:
            return

        mixins = self.mixins
        if isinstance(targets, string):
            targets = targets.split(' ')

        if isinstance(targets, (list, tuple)):
            for target in targets:
                if target in mixins:
                    mixins[target].append(mixin_class)
                else:
                    mixins[target] = [mixin_class]

    def _enumerate_mixin_classes(self, modules):
        if isinstance(modules, string):
            modules = modules.split(' ')

        for name in modules:
            module = import_object(name)
            for attr in dir(module):
                self._associate_mixin_class(getattr(module, attr))

    def _generate_model(self, resource):
        return self.binding_module.Model.generate_model(self.specification, resource,
            self.mixins.get(resource['classname']))

class BindingGenerator(object):
    """Generates python bindings for one or more mesh bundles.

    :param list mixin_modules: Optional, default is ``None``; one of more mixin modules to evaluate
        when generating bindings, specified as either a ``list`` or a space-delimited ``str`` of
        dotted package paths.

    :param str binding_module: Optional, default is ``mesh.standard.python``; the
        dotted package path of the module to be used as the basis for generating
        bindings.
    """

    CONSTRUCTOR_PARAMS = ('mixin_modules', 'binding_module')
    MODULE_TMPL = get_package_data('mesh.binding', 'templates/module.py.tmpl')

    def __init__(self, mixin_modules=None, binding_module='mesh.standard.python'):
        if isinstance(mixin_modules, string):
            mixin_modules = mixin_modules.split(' ')

        self.binding_module = binding_module
        self.formatter = StructureFormattor()
        self.mixin_modules = mixin_modules

    def generate(self, bundle):
        """Generates a binding for the specified bundle using this generator."""

        if isinstance(bundle, string):
            bundle = import_object(bundle)

        source = self._generate_binding(bundle)
        return '%s.py' % bundle.name, source

    def generate_dynamically(self, bundle):
        if isinstance(bundle, string):
            bundle = import_object(bundle)

        source = self._generate_binding(bundle)
        module = new_module(bundle.name)

        exec(source, module.__dict__)
        return module

    def _generate_binding(self, bundle):
        specification = self.formatter.format(bundle.describe())
        mixins, mixin_classes = self._generate_mixins()

        return self.MODULE_TMPL % {
            'binding_module': self.binding_module,
            'mixins': mixins,
            'mixin_classes': mixin_classes,
            'specification': specification,
        }

    def _generate_mixins(self):
        if not self.mixin_modules:
            return '', ''

        mixins = []
        mixin_classes = []

        for name in self.mixin_modules:
            module = import_object(name)
            for attr in dir(module):
                value = getattr(module, attr)
                try:
                    targets = value.mixin
                except Exception:
                    continue
                mixins.append(getsource(value))
                mixin_classes.append(attr)

        return '\n'.join(mixins), ', '.join(mixin_classes)

class BindingLoader(object):
    """Import loader for mesh bindings.

    When installed in ``sys.meta_path``, .mesh files will be dynamically converted to binding
    modules when imported.
    """
    
    def __init__(self, filename):
        self.filename = filename

    def __repr__(self):
        return 'BindingLoader(%s)' % self.filename

    @classmethod
    def find_module(cls, fullname, path=None):
        if path:
            path = path[0]
        else:
            return

        module = fullname.rpartition('.')[-1]
        if exists(joinpath(path, '%s.py' % module)):
            return

        filename = joinpath(path, '%s.mesh' % module)
        if exists(filename):
            return cls(filename)

    def load_module(self, fullname):
        namespace = {}
        execfile(self.filename, namespace)

        specification = namespace.get('bundle')
        if specification is None:
            specification = namespace.get('specification')
            if specification is None:
                raise ImportError(fullname)

        if fullname in sys.modules:
            module = sys.modules[fullname]
        else:
            module = sys.modules[fullname] = new_module(fullname)

        module.__file__ = self.filename
        module.__loader__ = self
        module.__package__ = fullname.rpartition('.')[0]

        module.binding = Binding(specification, namespace.get('mixins'))
        module.specification = module.binding.specification
        return module

def install_binding_loader():
    """Installs the mesh binding loader into ``sys.meta_path``, enabling the use of .mesh files,
    which will be dynamically converted into binding modules upon import. This function can be
    called multiple times without error.
    """

    if BindingLoader not in sys.meta_path:
        sys.meta_path.insert(0, BindingLoader)
