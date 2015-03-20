import re

from mesh.constants import *
from mesh.exceptions import *

__all__ = ('Address',)

BUNDLE_EXPR = r"""(?x)
    /(?P<bundle>[\w.]+)
    /(?P<major>\d+)[.](?P<minor>\d+)"""

ADDRESS_EXPR = r"""(?x)
    (?:(?P<endpoint>[A-Za-z]+)::)?
    %s
    (?P<bundle>(?:/[\w.]+/\d+[.]\d+)+)
    (?:/(?P<resource>[\w.]+)
        (?:/(?P<subject>[-.:;\w]+)
            (?:/(?P<subresource>[\w.]+)
                (?:/(?P<subsubject>[-.:;\w]+))?
            )?
        )?
    )?
    (?:[!](?P<format>\w+))?
    /?$"""

class AddressParser(object):
    """Address parser."""

    def __init__(self):
        self.bundle_expr = re.compile(BUNDLE_EXPR)
        self.expressions = {None: re.compile(ADDRESS_EXPR % '')}

    def parse(self, address, prefix=None, **params):
        try:
            expr = self.expressions[prefix]
        except KeyError:
            expr = self.expressions[prefix] = re.compile(ADDRESS_EXPR % prefix)

        match = expr.match(address)
        if not match:
            raise ValueError(address)
        
        bundle = []
        for candidate in list(self.bundle_expr.finditer(match.group('bundle'))):
            version = (int(candidate.group('major')), int(candidate.group('minor')))
            bundle.extend([candidate.group('bundle'), version])

        return (match.group('endpoint') or params.get('endpoint'),
            prefix, tuple(bundle),
            match.group('resource') or params.get('resource'),
            match.group('subject') or params.get('subject'),
            match.group('subresource') or params.get('subresource'),
            match.group('subsubject') or params.get('subsubject'),
            match.group('format') or params.get('format'))

class Address(object):
    """An API request address."""

    ATTRS = ('endpoint', 'prefix', 'bundle', 'resource', 'subject', 'subresource',
        'subsubject', 'format')

    parser = AddressParser()

    def __init__(self, endpoint=None, prefix=None, bundle=None, resource=None, subject=None,
            subresource=None, subsubject=None, format=None):

        self.bundle = bundle
        self.endpoint = endpoint
        self.format = format
        self.prefix = prefix
        self.resource = resource
        self.subject = subject
        self.subresource = subresource
        self.subsubject = subsubject

    def __repr__(self):
        aspects = []
        for attr in self.ATTRS:
            value = getattr(self, attr, None)
            if value:
                aspects.append(repr(value))

        return 'Address(%s)' % ', '.join(aspects)

    def __str__(self):
        return self.address

    @property
    def address(self):
        return self.render()

    @property
    def prefixed_path(self):
        return self.render('pbrsuvf')

    @property
    def signature(self):
        signature = [self.endpoint, self.prefix, self.bundle, self.resource, self.subject,
            self.subresource, self.subsubject, self.format]

        while signature[-1] is None:
            signature = signature[:-1]

        return tuple(signature)

    @property
    def valid(self):
        return all([self.endpoint, self.bundle, self.resource])

    def clone(self, **params):
        for attr in self.ATTRS:
            if attr not in params:
                params[attr] = getattr(self, attr)

        return Address(**params)

    def render(self, format='ebrsuvf', subject=None, subsubject=None):
        address = []
        if 'e' in format and self.endpoint:
            address.append(self.endpoint + '::')

        if 'p' in format and self.prefix:
            address.append(self.prefix)

        bundle = self.bundle
        if 'b' in format and bundle:
            for i in range(0, len(bundle), 2):
                address.append('/%s/%d.%d' % (bundle[i], bundle[i + 1][0], bundle[i + 1][1]))

        if 'r' in format and self.resource:
            address.append('/' + self.resource)

        if 's' in format and self.subject:
            if self.subject is True:
                if subject:
                    address.append('/' + subject)
            else:
                address.append('/' + str(subject or self.subject))

        if 'u' in format and self.subresource:
            address.append('/' + self.subresource)

        if 'v' in format and self.subsubject:
            if self.subsubject is True:
                if subsubject:
                    address.append('/' + subsubject)
            else:
                address.append('/' + str(subsubject or self.subsubject))

        if 'f' in format and self.format:
            address.append('!' + self.format)

        return ''.join(address)

    def render_prefixed_path(self, subject=None, subsubject=None):
        return self.render('pbrsuvf', subject, subsubject)

    def extend(self, *segments):
        bundle = self.bundle
        if bundle:
            bundle = list(bundle) + list(segments)
        else:
            bundle = segments

        return Address(self.endpoint, self.prefix, tuple(bundle), self.resource, self.subject,
            self.subresource, self.subsubject, self.format)

    @classmethod
    def parse(cls, address, prefix=None, **params):
        return cls(*cls.parser.parse(address, prefix, **params))

    def validate(self, **params):
        for attr, test in params.items():
            value = getattr(self, attr, None)
            if test is True and not value:
                return False
            elif test is False and value:
                return False
        else:
            return True
