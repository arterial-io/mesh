from mesh.address import *
from mesh.bundle import *
from mesh.constants import *
from mesh.endpoint import *
from mesh.exceptions import *
from mesh.resource import *
from mesh.standard.endpoints import DEFAULT_ENDPOINTS, STANDARD_ENDPOINTS, VALIDATED_ENDPOINTS
from mesh.util import import_object

STANDARD_CONFIGURATION = Configuration(
    default_endpoints=DEFAULT_ENDPOINTS,
    standard_endpoints=STANDARD_ENDPOINTS,
    validated_endpoints=VALIDATED_ENDPOINTS,
)

class Resource(Resource):
    configuration = STANDARD_CONFIGURATION
