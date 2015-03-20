from copy import deepcopy

from mesh.binding.python import Model, Query

class ResultSet(list):
    def __init__(self, status, models, total=None):
        super(ResultSet, self).__init__(models)
        self.status = status
        self.total = total

class Query(Query):
    """A standard resource query."""

    def count(self):
        """Executes this query with ``total`` set to ``True``, so that only the total number
        of resource instances matching this query is returned, and not the full result set."""

        params = self.params.copy()
        params['total'] = True

        response = self.model._get_client().execute(self.model._resource, 'query', None, params)
        return response.data.get('total')

    def exclude(self, *fields):
        """Constructs and returns a clone of this query which excludes one or more fields from
        each resource instance matched by this query, specified as postitional arguments."""

        fields = set(fields)
        if 'exclude' in self.params:
            fields.update(self.params['exclude'])

        return self.clone(exclude=list(fields))

    def fields(self, *fields):
        """Constructs and returns a clone of this query which will return exactly the set of
        fields specified as positional arguments for each resource instance matched by this
        query. The returned query will not specified either ``exclude`` or ``include``, even
        if this query does, as those parameters are ignored when ``fields`` is specified."""

        params = self.params.copy()
        if 'exclude' in params:
            del params['exclude']
        if 'include' in params:
            del params['include']

        params['fields'] = list(fields)
        return type(self)(self.model, **params)

    def filter(self, **params):
        """Constructs and returns a clone of this query which will filter resources instances
        for this query using the field/value tests specified as keyword parameters."""

        query = params
        if 'query' in self.params:
            query = deepcopy(self.params['query'])
            query.update(params)

        return self.clone(query=query)

    def include(self, *fields):
        """Constructs and returns a clone of this query which includes the fields specified
        as positional arguments on each resource instance matched by this query."""

        fields = set(fields)
        if 'include' in self.params:
            fields.update(self.params['include'])

        return self.clone(include=list(fields))

    def limit(self, value):
        """Constructs and returns a clone of this query which will be limited to the specified
        number of resource instances."""

        if self.params.get('limit') == value:
            return self
        else:
            return self.clone(limit=value)

    def offset(self, offset):
        """Constructs and returns a clone of this query set to return resource instances starting
        at the specified offset."""

        if self.params.get('offset') == value:
            return self
        else:
            return self.clone(offset=value)

    def one(self):
        return self.limit(1)._execute_query()[0]

    def set(self, **params):
        return self.clone(**params)

    def sort(self, *fields):
        """Constructs and returns a clone of this query which will sort resource instances matched
        by this query using the fields specified as positional arguments."""

        fields = list(fields)
        if self.params.get('sort') == fields:
            return self
        else:
            return self.clone(sort=fields)

    def _execute_query(self):
        model = self.model
        response = model._get_client().execute(model._resource, 'query', None, self.params or None)

        models = []
        for resource in response.data.get('resources') or []:
            models.append(model(**resource))

        return ResultSet(response.status, models, response.data.get('total'))

class Model(Model):
    query_class = Query
