"""

Zmq Serialization:

REQUEST

Frame #1:
    "mesh/1" "req" <address> <mimetype> <context-length> <data-length>
Frame #2 (if necessary):
    <context>
Frame #3 (if necessary):
    <data>

RESPONSE

Frame #1:
    "mesh/1" "rep" <status> <mimetype> <context-length> <data-length>
"""

from __future__ import absolute_import

from scheme import Format
from scheme.fields import INBOUND, OUTBOUND
from scheme.formats import Json

from mesh.address import *
from mesh.constants import *
from mesh.exceptions import *
from mesh.transport.base import *
from mesh.util import LogHelper, string

VERSION = 'mesh/1'

log = LogHelper(__name__)

class ZmqProtocol(object):
    @classmethod
    def _prepare_data(cls, data, mimetype=None):
        if not data:
            return 'none', None, 0

        if mimetype:
            format = Format.formats[mimetype]
        else:
            format = Json

        data = format.serialize(data).encode('utf8')
        return format.mimetype, data, len(data)

    @classmethod
    def _prepare_context(cls, context):
        if not context:
            return None, 0

        lines = []
        for key, value in context.items():
            lines.append('%s: %s' % (key, value))

        context = ('\n'.join(lines)).encode('utf8')
        return context, len(context)

class ZmqRequest(Request, ZmqProtocol):
    """A ZeroMQ message request."""

    token = 'zmq'

    def __init__(self, address=None, data=None, context=None, mimetype=None,
            identity=None, serialized=True):

        super(ZmqRequest, self).__init__(address, data, context,
            mimetype, identity, serialized)

    @classmethod
    def parse(cls, message, identity=None):
        request = cls(identity=identity)
        try:
            tokens = frames[0].decode('utf8').split(' ')
        except Exception:
            log('exception', 'failed to parse header for %s', request)
            raise BadRequestError()

        if tokens[0] != VERSION:
            raise BadRequestError()
        if tokens[1] != 'req':
            raise BadRequestError()

        try:
            request.address = Address.parse(tokens[2])
        except ValueError:
            log('info', 'invalid address for %s', request)
            raise NotFoundError()

        mimetype = tokens[3]
        format = None

        if mimetype in Format.formats:
            request.mimetype = mimetype
            format = Format.formats[mimetype]
        elif mimetype != 'none':
            raise BadRequestError()

        request.context = context = {}
        try:
            if int(tokens[4]) > 0:
                for line in message[1].decode('utf8').split('\n'):
                    key, value = line.split(':', 1)
                    context[key] = value
        except Exception:
            log('exception', 'failed to parse context for %s', request)
            raise BadRequestError()

        try:
            if int(tokens[5]) > 0:
                request.data = format.unserialize(message[-1])
        except Exception:
            log('exception', 'failed to parse data for %s', request)
            raise BadRequestError()

        return request

    def prepare(self, version=VERSION):
        context, context_length = self._prepare_context(self.context)
        mimetype, data, data_length = self._prepare_data(self.data, self.mimetype)

        header = '%s req %s %s %d %d' % (version, self.address.address,
            mimetype, context_length, data_length)

        message = [header.encode('utf8')]
        if context:
            message.append(context)
        if data:
            message.append(data)

        return message

class ZmqResponse(Response, ZmqProtocol):
    """A ZeroMQ mesh response."""

    def prepare(self, version=VERSION):
        context, context_length = self._prepare_context(self.context)
        mimetype, data, data_length = self._prepare_data(self.data, self.mimetype)

        header = '%s rep %s %s %d %d' % (version, self.status,
            mimetype, context_length, data_length)

        message = [header.encode('utf8')]
        if context:
            message.append(context)
        if data:
            message.append(data)

        return message

class ZmqServer(Server):
    """The ZeroMQ mesh server."""

    def __init__(self, bundles, default_format=None,
            available_formats=None, mediators=None):

        super(ZmqServer, self).__init__(bundles, default_format, available_formats, mediators)

        self.endpoints = {}
        for name, bundle in self.bundles.items():
            for resource_addr, resource, controller in bundle.enumerate_resources():
                for endpoint_addr, endpoint in resource.enumerate_endpoints(resource_addr):
                    self.endpoints[endpoint_addr.address] = (resource, controller, endpoint)

    def dispatch(self, message, identity=None):
        response = ZmqResponse()
        try:
            request = ZmqRequest.parse(message, identity)
        except RequestError as exception:
            return response(exception.status).prepare()

        endpoint = self.endpoints.get(request.address.render('ebr'))
        if endpoint:
            resource, controller, endpoint = endpoint
        else:
            return response(NOT_FOUND).prepare()

        try:
            endpoint.process(controller, request, response, self.mediators)
        except Exception:
            log('exception', 'endpoint processing failed for %s', request)
            return response(SERVER_ERROR).prepare()
        else:
            return response.prepare()
