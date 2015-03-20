import errno
import re
import socket
from cgi import parse_header

try:
    from httplib import HTTPConnection, HTTPSConnection
except ImportError:
    from http.client import HTTPConnection, HTTPSConnection

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from scheme import Format
from scheme.fields import INBOUND, OUTBOUND
from scheme.formats import *

from mesh.address import *
from mesh.bundle import Specification
from mesh.constants import *
from mesh.exceptions import *
from mesh.transport.base import *
from mesh.transport.multipart import *
from mesh.util import LogHelper, string

__all__ = ('HttpClient', 'HttpProxy', 'HttpRequest', 'HttpResponse', 'HttpServer')

log = LogHelper(__name__)

STATUS_CODES = {
    OK: 200,
    CREATED: 201,
    ACCEPTED: 202,
    SUBSET: 203,
    PARTIAL: 206,
    BAD_REQUEST: 400,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    METHOD_NOT_ALLOWED: 405,
    INVALID: 406,
    TIMEOUT: 408,
    CONFLICT: 409,
    GONE: 410,
    SERVER_ERROR: 500,
    UNIMPLEMENTED: 501,
    BAD_GATEWAY: 502,
    UNAVAILABLE: 503,
}

STATUS_CODES.update(dict((code, status) for status, code in STATUS_CODES.items()))

STATUS_LINES = {
    OK: '200 OK',
    CREATED: '201 Created',
    ACCEPTED: '202 Accepted',
    SUBSET: '203 Subset',
    PARTIAL: '206 Partial',
    BAD_REQUEST: '400 Bad Request',
    FORBIDDEN: '403 Forbidden',
    NOT_FOUND: '404 Not Found',
    METHOD_NOT_ALLOWED: '405 Method Not Allowed',
    INVALID: '406 Invalid',
    TIMEOUT: '408 Request Timeout',
    CONFLICT: '409 Conflict',
    GONE: '410 Gone',
    SERVER_ERROR: '500 Internal Server Error',
    UNIMPLEMENTED: '501 Not Implemented',
    BAD_GATEWAY: '502 Bad Gateway',
    UNAVAILABLE: '503 Service Unavailable',
}

class Connection(object):
    """An HTTP connection."""

    http_connection = HTTPConnection
    https_connection = HTTPSConnection

    def __init__(self, url, timeout=None):
        self.scheme, self.host, self.path = urlparse(url)[:3]
        self.path = self.path.rstrip('/')
        self.timeout = timeout

        if self.scheme == 'https':
            self.implementation = self.https_connection
        elif self.scheme == 'http':
            self.implementation = self.http_connection
        else:
            raise ValueError(url)

    def request(self, method, url=None, body=None, headers=None, mimetype=None, serialize=False):
        if url:
            if url[0] != '/':
                url = '/' + url
        else:
            url = ''

        url = self.path + url

        multipart = isinstance(body, MultipartMixedEncoder)
        if body and not multipart:
            if method == 'GET':
                url = '%s?%s' % (url, body)
                body = None
            elif serialize:
                if mimetype:
                    body = Format.serialize(body, mimetype)
                else:
                    raise ValueError(mimetype)

        headers = headers or {}
        if 'Content-Type' not in headers and mimetype:
            headers['Content-Type'] = mimetype

        connection = self.implementation(self.host, timeout=self.timeout)
        try:
            if multipart:
                self._send_multipart_request(connection, method, url, body, headers)
            else:
                connection.request(method, url, body, headers)
        except socket.error as Exception:
            if exception.errno in (errno.EACCES, errno.EPERM, errno.ECONNREFUSED):
                raise ConnectionRefused(url)
            elif exception.errno == errno.ETIMEDOUT:
                raise ConnectionTimedOut(url)
            else:
                raise ConnectionFailed(url)
        except socket.timeout:
            raise ConnectionTimedOut(url)

        try:
            response = connection.getresponse()
        except socket.error as exception:
            raise ConnectionFailed(url)
        except socket.timeout:
            raise ConnectionTimedOut(url)

        return HttpResponse(STATUS_CODES[response.status], response.read() or None,
            response.getheader('Content-Type', None),
            dict((key.title(), value) for key, value in response.getheaders()))

    def _send_multipart_request(self, connection, method, url, body, headers):
        connection.connect()
        connection.putrequest(method, url)

        for header, value in headers.items():
            connection.putheader(header, value)

        connection.endheaders()
        while True:
            chunk = body.next_chunk()
            if chunk:
                connection.send(chunk)
            else:
                break

class HttpRequest(Request):
    """An HTTP mesh request."""

    token = 'http'

    def __init__(self, address, method, data=None, context=None, mimetype=None, headers=None,
            identity=None, serialized=True):

        super(HttpRequest, self).__init__(address, data, context, identity, serialized)
        self.accept = self._parse_accept_header(headers)
        self.context = context
        self.format = None
        self.headers = headers
        self.method = method
        self.mimetype = mimetype
        self.signature = address.render_prefixed_path('id', 'id')
        self.subject = address.subject

    @property
    def description(self):
        aspects = ['%s %s' % (self.method, self.path)]
        if self.mimetype:
            aspects.append('(%s)' % self.mimetype)
        return ' '.join(aspects)

    def _parse_accept_header(self, headers):
        if not headers:
            return

        header = headers.get('HTTP_ACCEPT')
        if not header:
            return

        mimetype = header.split(';', 1)[0]
        if mimetype in Format.formats:
            return parse_header(header)

class HttpResponse(Response):
    """An HTTP response."""

    def __init__(self, status=None, data=None, context=None, mimetype=None, headers=None):
        super(HttpResponse, self).__init__(status, data, context, mimetype)
        self.headers = headers or {}

    @property
    def status_code(self):
        return STATUS_CODES[self.status]

    @property
    def status_line(self):
        return STATUS_LINES[self.status]

    def construct_headers(self, prefix=None):
        headers = self.headers
        if 'Cache-Control' not in headers:
            headers['Cache-Control'] = 'must-revalidate, no-cache'

        if 'Content-Type' not in headers and self.mimetype:
            headers['Content-Type'] = self.mimetype

        if 'Content-Length' not in headers:
            if isinstance(self.data, list):
                content_length = 0
                for chunk in self.data:
                    content_length += len(chunk)
                headers['Content-Length'] = str(content_length)
            else:
                headers['Content-Length'] = str(len(self.data))

        prefix = prefix or ''
        if self.context:
            for name, value in self.context.items():
                headers[prefix + name] = value

        return list(headers.items())

    def header(self, name, value, conditional=False):
        name = name.lower()
        if not (name in self.headers or conditional):
            self.headers[name] = value

class WsgiServer(Server):
    DefaultFormat = Json

    def __init__(self, bundles, default_format=None, available_formats=None, mediators=None,
            context_environ_key=None, context_header_prefix=None):

        super(WsgiServer, self).__init__(bundles, default_format, available_formats, mediators)
        self.context_environ_key = context_environ_key
        self.context_header_prefix = context_header_prefix
        self.multipart_parser = MultipartMixedParser()

    def __call__(self, environ, start_response):
        try:
            method = environ['REQUEST_METHOD']
            mimetype = environ.get('CONTENT_TYPE')

            try:
                data = self._parse_request_data(method, mimetype, environ)
            except Exception:
                log('exception', 'exception raised during wsgi request parsing')
                start_response('400 Bad Request', [])
                return []

            key = self.context_environ_key
            if key and key in environ:
                context = environ[key]
            else:
                context = {}

            identity = self._identify_ipaddr(environ)
            response = self.dispatch(method, environ['PATH_INFO'], mimetype, context,
                environ, data, identity)

            headers = response.construct_headers(self.context_header_prefix)
            data = response.data

            if data:
                if isinstance(data, string):
                    data = data.encode('utf8')
                if not isinstance(data, list):
                    data = [data]
            else:
                data = []

            start_response(response.status_line, headers)
            return data
        except Exception:
            log('exception', 'uncaught exception raised during wsgi dispatch')
            start_response('500 Internal Server Error', [])
            return []

    def _identify_ipaddr(self, environ):
        if 'HTTP_X_FORWARDED_FOR' in environ:
            return environ['HTTP_X_FORWARDED_FOR']
        elif 'REMOTE_ADDR' in environ:
            return environ['REMOTE_ADDR']

    def _parse_request_data(self, method, mimetype, environ):
        if method == 'GET':
            return environ['QUERY_STRING']
        elif method in ('HEAD', 'OPTIONS'):
            return None

        length = int(environ.get('CONTENT_LENGTH') or 0)
        if length > 0:
            if mimetype and 'multipart/mixed' in mimetype:
                return self.multipart_parser.parse(environ['wsgi.input'], mimetype)
            else:
                return environ['wsgi.input'].read(int(length)).decode('utf-8')

        encoding = environ.get('TRANSFER_ENCODING')
        if encoding:
            raise NotImplementedError()
        else:
            return None

class HttpServer(WsgiServer):
    """The HTTP mesh server."""

    def __init__(self, bundles, prefix=None, default_format=None, available_formats=None,
            mediators=None, context_key=None):

        super(HttpServer, self).__init__(bundles, default_format, available_formats,
            mediators, context_key)

        self.prefix = None
        address = None

        if prefix:
            self.prefix = '/' + prefix.strip('/')
            address = Address(prefix=self.prefix)

        self.paths = {}
        for name, bundle in self.bundles.items():
            for resource_addr, resource, controller in bundle.enumerate_resources(address):
                for addr, endpoint in resource.enumerate_endpoints(resource_addr):
                    if endpoint.method:
                        signature = addr.render_prefixed_path('id', 'id')
                        if signature not in self.paths:
                            self.paths[signature] = {}
                        self.paths[signature][endpoint.method] = (resource, controller, endpoint)

    def dispatch(self, method, path, mimetype, context, headers, data, identity):
        response = HttpResponse()
        if method == GET and path.strip('/') in self.bundles:
            return response(OK)

        mimetype = mimetype or URLENCODED
        if ';' in mimetype:
            mimetype, charset = mimetype.split(';', 1)
        if mimetype not in self.formats:
            mimetype = URLENCODED

        try:
            address = Address.parse(path, self.prefix)
        except ValueError:
            log('info', 'no path found for %s', path)
            return response(NOT_FOUND)

        request = HttpRequest(address, method, data, context, mimetype, headers, identity)
        if request.accept:
            request.format = (self.formats[request.accept[0]], request.accept[1])
        elif request.address.format:
            request.format = self.formats[request.address.format]
        elif request.mimetype and request.mimetype != URLENCODED:
            request.format = self.formats[request.mimetype]
        else:
            request.format = self.default_format

        candidates = self.paths.get(request.signature)
        if candidates:
            candidate = candidates.get(request.method)
            if candidate:
                resource, controller, endpoint = candidate
            else:
                return response(METHOD_NOT_ALLOWED)
        else:
            return response(NOT_FOUND)

        if data:
            if isinstance(data, MultipartPayload):
                try:
                    request.data = data.unserialize(self.formats)
                except Exception:
                    log('exception', 'failed to parse data for %r', request)
                    return response(BAD_REQUEST)
            else:
                try:
                    request.data = self.formats[mimetype].unserialize(data)
                except Exception:
                    log('exception', 'failed to parse data for %r', request)
                    return response(BAD_REQUEST)

        try:
            endpoint.process(controller, request, response, self.mediators)
        except Exception as exception:
            log('exception', 'uncaught exception raised during endpoint processing')
            return response(SERVER_ERROR)

        format = request.format
        if isinstance(format, tuple):
            format, params = format
            response.data = format.serialize(response.data, **params)
        else:
            response.data = format.serialize(response.data)

        response.mimetype = format.mimetype
        return response

class HttpClient(Client):
    """An HTTP client."""

    ConnectionImplementation = Connection
    DefaultHeaderPrefix = None
    DefaultFormat = Json

    def __init__(self, url, specification=None, context=None, format=None, formats=None,
            context_header_prefix=None, timeout=None, bundle=None):

        super(HttpClient, self).__init__(specification, context, format, formats)
        if '//' not in url:
            url = 'http://' + url

        self.connection = self.ConnectionImplementation(url, timeout)
        self.context_header_prefix = context_header_prefix or self.DefaultHeaderPrefix
        self.url = url.rstrip('/')

    def execute(self, target, subject=None, data=None, format=None, context=None):
        endpoint, method, path, mimetype, data, headers = self._prepare_request(target, subject,
            data, format, context)

        try:
            response = self.connection.request(method, path, data, headers)
        except socket.timeout:
            raise TimeoutError()

        status = response.status
        if status in endpoint['responses']:
            schema = endpoint['responses'][status]['schema']
        elif not (status in ERROR_STATUS_CODES and not response.data):
            exception = RequestError.construct(status)
            if exception:
                raise exception
            else:
                raise Exception('server returned unknown status: %s' % status)

        if response.data:
            response.data = schema.process(self.formats[response.mimetype]
                .unserialize(response.data.decode('utf8')), INBOUND, True)

        if response.ok:
            return response
        else:
            raise RequestError.construct(status, response.data)

    def prepare(self, target, subject=None, data=None, format=None, context=None,
            preparation=None):

        endpoint, method, path, mimetype, data, headers = self._prepare_request(target, subject,
            data, format, context)

        preparation = preparation or {}
        preparation.update(method=method, url=self.url + path)

        if mimetype:
            preparation['mimetype'] = mimetype
        if data:
            preparation['data'] = data
        if headers:
            preparation['headers'] = headers
        return preparation

    def _prepare_request(self, target, subject=None, data=None, format=None, context=None):
        endpoint = None
        if isinstance(target, dict):
            endpoint = target
        elif isinstance(target, string):
            target = Address.parse(target)
            if not subject and target.subject:
                subject = target.subject
        elif not isinstance(target, Address):
            raise TypeError(target)

        if not endpoint:
            endpoint = self.specification.find(target)

        address = Address(*endpoint['address'])
        if subject:
            address.subject = subject

        headers = {}
        if context is not False:
            prefix = self.context_header_prefix or ''
            for name, value in self._construct_context(context).items():
                headers[prefix + name] = value

        format = format or self.format
        mimetype = None

        if data is not None:
            if isinstance(data, MultipartPayload):
                data.payload = endpoint['schema'].process(data.payload, OUTBOUND, True)
                data = MultipartMixedEncoder(data, format)
                headers.update(data.headers)
            else:
                data = endpoint['schema'].process(data, OUTBOUND, True)
                if endpoint['method'] == GET:
                    data = UrlEncoded.serialize(data)
                    mimetype = fields.UrlEncoded.mimetype
                else:
                    data = format.serialize(data)
                    mimetype = format.mimetype

        if mimetype:
            headers['Content-Type'] = mimetype

        path = address.prefixed_path
        return endpoint, endpoint['method'], path, mimetype, data, headers

    def _provide_binding(self):
        return self.specification

class HttpProxy(WsgiServer):
    """The HTTP mesh proxy."""

    PROXIED_REQUEST_HEADERS = {
        'HTTP_ACCEPT': 'Accept',
        'HTTP_COOKIE': 'Cookie',
    }
