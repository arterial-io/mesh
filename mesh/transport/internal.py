from scheme.formats import *

from mesh.bundle import Bundle, Specification, format_version
from mesh.address import *
from mesh.constants import *
from mesh.exceptions import *
from mesh.transport.base import *
from mesh.util import LogHelper, string

__all__ = ('InternalClient', 'InternalServer')

log = LogHelper(__name__)

class InternalServer(Server):
    """An process-internal mesh server."""

    def __init__(self, bundles, default_format=None, available_formats=None, mediators=None):
        super(InternalServer, self).__init__(bundles, default_format, available_formats, mediators)

        self.endpoints = {}
        for name, bundle in self.bundles.items():
            for resource_addr, resource, controller in bundle.enumerate_resources():
                for endpoint_addr, endpoint in resource.enumerate_endpoints(resource_addr):
                    self.endpoints[endpoint_addr.address] = (resource, controller, endpoint)

    def dispatch(self, address, context=None, data=None, mimetype=None):
        request = Request(address, data, context, mimetype, None, bool(mimetype))
        response = Response()

        endpoint = self.endpoints.get(address.render('ebr'))
        if endpoint:
            resource, controller, endpoint = endpoint
        else:
            return response(NOT_FOUND)

        format = None
        if request.serialized:
            try:
                format = self.formats[request.mimetype]
                request.data = format.unserialize(data)
            except Exception:
                return response(BAD_REQUEST)

        try:
            endpoint.process(controller, request, response, self.mediators)
        except Exception as exception:
            log('exception', 'uncaught exception raised during endpoint processing')
            return response(SERVER_ERROR)

        if request.serialized:
            response.mimetype = format.mimetype
            if response.data:
                response.data = format.serialize(response.data)

        return response

class InternalClient(Client):
    """The internal mesh client."""

    def __init__(self, server, bundle, context=None, format=None, formats=None):
        if isinstance(bundle, string):
            if bundle in server.bundles:
                bundle = server.bundles[bundle]
            else:
                raise ValueError(bundle)

        super(InternalClient, self).__init__(bundle, context, format, formats)
        self.server = server

    def execute(self, address, subject=None, data=None, format=None, context=None):
        context = self._construct_context(context)

        if not isinstance(address, Address):
            address = Address.parse(address)
            if subject:
                address.subject = subject
        elif subject:
            address = address.clone(subject=subject)

        if format:
            format = self.formats[format]
        else:
            format = self.format

        mimetype = None
        if format and data:
            data = format.serialize(data)
            mimetype = format.mimetype

        response = self._dispatch_request(address, data, context, mimetype)
        if response.mimetype and response.data:
            response.data = response.unserialize()

        return response

    def _dispatch_request(self, address, data, context, mimetype):
        response = self.server.dispatch(address, context, data, mimetype)
        if response.ok:
            return response
        else:
            raise RequestError.construct(response.status, response.data)
