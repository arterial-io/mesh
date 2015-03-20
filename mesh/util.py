import logging
import os
import re
import sys
from datetime import datetime
from inspect import getargspec

try:
    string = basestring
except NameError:
    string = str

def call_with_supported_params(callable, *args, **params):
    arguments = getargspec(callable)[0]
    for key in list(params):
        if key not in arguments:
            del params[key]

    return callable(*args, **params)

def format_url_path(*segments):
    return '/' + '/'.join(segment.strip('/') for segment in segments)

def get_package_data(module, path):
    openfile = open(get_package_path(module, path))
    try:
        return openfile.read()
    finally:
        openfile.close()

def get_package_path(module, path):
    if isinstance(module, string):
        module = __import__(module, None, None, [module.split('.')[-1]])
    if not isinstance(module, list):
        module = module.__path__

    modulepath = module[0]
    for prefix in sys.path:
        if prefix in ('', '..'):
            prefix = os.getcwd()
        fullpath = os.path.abspath(os.path.join(prefix, modulepath))
        if os.path.exists(fullpath):
            break
    else:
        return None

    return os.path.join(fullpath, path)

def identify_class(cls):
    return '%s.%s' % (cls.__module__, cls.__name__)

def import_object(path, ignore_errors=False, report_errors=False):
    try:
        module, attr = path.rsplit('.', 1)
        return getattr(__import__(module, None, None, (attr,)), attr)
    except Exception:
        if not ignore_errors:
            raise

class LogFormatter(logging.Formatter):
    def __init__(self, format='%(timestamp)s %(name)s %(levelname)s %(message)s'):
        logging.Formatter.__init__(self, format)

    def format(self, record):
        record.timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        return logging.Formatter.format(self, record)

class LogHelper(object):
    LEVELS = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
    }

    def __init__(self, logger):
        if isinstance(logger, string):
            logger = logging.getLogger(logger)
        self.logger = logger

    def __call__(self, level, message, *args):
        if level == 'exception':
            self.logger.exception(message, *args)
        else:
            self.logger.log(self.LEVELS[level], message, *args)

def minimize_string(value):
    return re.sub(r'\s+', ' ', value).strip(' ')

def pull_class_dict(cls, attrs=None, superclasses=False):
    subjects = [cls]
    if superclasses:
        queue = list(cls.__bases__)
        while queue:
            candidate = queue.pop(0)
            subjects.insert(0, candidate)
            queue.extend(candidate.__bases__)

    result = {}
    for subject in subjects:
        for k, v in subject.__dict__.items():
            if (not attrs or k in attrs) and not k.startswith('__'):
                result[k] = v

    return result

PLURALIZATION_RULES = (
    (re.compile(r'ife$'), re.compile(r'ife$'), 'ives'),
    (re.compile(r'eau$'), re.compile(r'eau$'), 'eaux'),
    (re.compile(r'lf$'), re.compile(r'lf$'), 'lves'),
    (re.compile(r'[sxz]$'), re.compile(r'$'), 'es'),
    (re.compile(r'[^aeioudgkprt]h$'), re.compile(r'$'), 'es'),
    (re.compile(r'(qu|[^aeiou])y$'), re.compile(r'y$'), 'ies'),
)

def pluralize(word, quantity=None, rules=PLURALIZATION_RULES):
    if quantity == 1: 
        return word

    for pattern, target, replacement in rules:
        if pattern.search(word):
            return target.sub(replacement, word)
    else:
        return word + 's'

def set_function_attr(function, attr, value):
    try:
        function = function.__func__
    except AttributeError:
        pass

    setattr(function, attr, value)
    return function

def subclass_registry(collection, *attrs):
    """Metaclass constructor which maintains a registry of subclasses."""

    class registry(type):
        def __new__(metatype, name, bases, namespace):
            implementation = type.__new__(metatype, name, bases, namespace)
            subclasses = getattr(implementation, collection)

            identifier = None
            if attrs:
                for attr in attrs:
                    identifier = getattr(implementation, attr, None)
                    if identifier:
                        subclasses[identifier] = implementation
            else:
                module = namespace.get('__module__')
                if module and module != '__main__':
                    identifier = '%s.%s' % (module, name)
                if identifier:
                    subclasses[identifier] = implementation

            return implementation
    return registry

def with_metaclass(metaclass):
    def decorator(cls):
        namespace = cls.__dict__.copy()
        for attr in ('__dict__', '__weakref__'):
            namespace.pop(attr, None)
        else:
            return metaclass(cls.__name__, cls.__bases__, namespace)
    return decorator

def write_file(path, content):
    openfile = open(path, 'w+')
    try:
        openfile.write(content)
    finally:
        openfile.close()
