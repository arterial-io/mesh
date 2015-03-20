from unittest import TestCase

from mesh.transport.http import *

from tests.fixtures import *

class WsgiHarness(object):
    def request(self, server, method, path, data=None, mimetype=None,
            context=None, headers=None, identity=None):

        environ = {
            'REQUEST_METHOD': method,
            'SCRIPT_NAME': '',
            'PATH_INFO': path,
            'SERVER_NAME': 'mock-wsgi',
            'SERVER_PORT': '0',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'wsgi.version': (1, 1),
            'wsgi.url_scheme': 'http',
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
        }



class TestHttpServer(TestCase, WsgiHarness):
    pass
