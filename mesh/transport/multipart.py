import os
import uuid
from cgi import parse_header
from tempfile import mkstemp

from scheme.util import set_nested_value, traverse_to_key

from mesh.util import string

__all__ = ('MultipartFile', 'MultipartMixedEncoder', 'MultipartMixedParser', 'MultipartPayload')

NEWLINE = b'\r\n'

class MultipartFile(object):
    def __init__(self, name, filename):
        self.filename = filename
        self.name = name

    @property
    def size(self):
        return os.stat(self.filename).st_size

class MultipartPayload(object):
    def __init__(self, payload=None, mimetype=None):
        self.files = {}
        self.mimetype = mimetype
        self.payload = payload

    def attach(self, name, filename):
        self.files[name] = MultipartFile(name, filename)
        return self

    def serialize(self, format):
        if format:
            return format.mimetype, format.serialize(self.payload)
        elif self.mimetype:
            return self.mimetype, self.payload
        else:
            raise ValueError()

    def unserialize(self, formats):
        data = formats[self.mimetype].unserialize(self.payload)
        for name, multipart_file in self.files.items():
            set_nested_value(data, name, multipart_file)
        return data

class BufferedStream(object):
    def __init__(self, stream):
        self.buffer = b''
        self.stream = stream

    def chomp(self, size):
        buffer = self.buffer
        if not buffer and not self.stream:
            raise ValueError()

        length = len(buffer)
        if length < size:
            chunk = self.stream.read(size - length)
            if chunk:
                buffer += chunk
            else:
                raise ValueError()

        self.buffer = buffer[size:]

    def read(self, chunksize, boundary=None):
        buffer = self.buffer
        if not buffer and not self.stream:
            return b''

        length = len(buffer)
        if self.stream and length < chunksize:
            chunk = self.stream.read(chunksize - length)
            if chunk:
                buffer += chunk
            else:
                self.stream = None

        if boundary:
            offset = buffer.find(boundary)
            if offset >= 0:
                self.buffer = buffer[offset:]
                buffer = buffer[:offset]
            else:
                length = len(boundary)
                self.buffer = buffer[-length:]
                buffer = buffer[:-length]
        else:
            self.buffer = b''

        return buffer

    def readline(self):
        buffer = self.buffer
        if not buffer:
            if self.stream:
                return self.stream.readline()
            else:
                return b''

        offset = buffer.find(NEWLINE)
        if offset >= 0:
            offset += 2
            self.buffer = buffer[offset:]
            return buffer[:offset]

        self.buffer = b''
        return buffer + self.stream.readline()

class MultipartMixedParser(object):
    def parse(self, stream, mimetype, chunksize=1024*1024):
        mimetype, params = parse_header(mimetype)
        if 'boundary' in params:
            boundary = b'--' + params['boundary'].encode('utf8')
        else:
            raise ValueError(mimetype)

        stream = BufferedStream(stream)
        payload = MultipartPayload()

        while True:
            delimiter = stream.readline()
            if delimiter:
                delimiter = delimiter.strip(NEWLINE)
                if delimiter == boundary + b'--':
                    break
                elif delimiter != boundary:
                    raise ValueError(delimiter)
            else:
                raise ValueError(delimiter)

            headers = self._parse_content_headers(stream)
            if 'Content-Disposition' in headers:
                disposition, params = headers['Content-Disposition']
                if disposition == 'inline':
                    if payload.payload:
                        raise ValueError('already have payload')
                    if 'Content-Type' in headers:
                        payload.mimetype, _ = headers['Content-Type']
                        payload.payload = self._parse_inline_data(stream, chunksize, boundary)
                    else:
                        raise ValueError('missing content type')
                elif disposition == 'attachment':
                    if 'name' in params:
                        name = params['name']
                        filename = self._parse_attachment_data(stream, chunksize, boundary)
                        payload.files[name] = MultipartFile(name, filename)
                    else:
                        raise ValueError('missing attachment name')
                else:
                    raise ValueError(disposition)
            else:
                raise ValueError(headers)

        return payload

    def _parse_attachment_data(self, stream, chunksize, boundary):
        boundary = NEWLINE + boundary
        handle, filename = mkstemp('.upload', 'mesh-multipart-')

        try:
            while True:
                chunk = stream.read(chunksize, boundary)
                if chunk:
                    os.write(handle, chunk)
                else:
                    break
        finally:
            os.close(handle)

        stream.chomp(2)
        return filename

    def _parse_content_headers(self, stream):
        headers = {}

        line = b''
        while True:
            line = stream.readline()
            if not line:
                raise ValueError()

            line = line.rstrip(NEWLINE)
            if line:
                break

        while True:
            chunk = stream.readline()
            if not chunk:
                raise ValueError()

            chunk = chunk.rstrip(NEWLINE)
            if chunk and chunk[0] in b'\t ':
                if line:
                    line = b'%s %s' % (line, chunk.lstrip())
                    continue
                else:
                    raise ValueError()

            if line:
                key, value = line.split(b':', 1)
                headers[key.decode('utf8')] = parse_header(value.decode('utf8'))

            if chunk:
                line = chunk
            else:
                break

        return headers

    def _parse_inline_data(self, stream, chunksize, boundary):
        boundary = NEWLINE + boundary
        data = []

        while True:
            chunk = stream.read(chunksize, boundary)
            if chunk:
                data.append(chunk)
            else:
                break

        stream.chomp(2)
        return b''.join(data).decode('utf8')

class MultipartMixedEncoder(object):
    AttachmentHeaders = '\r\n--%s\r\nContent-Disposition: attachment; name="%s"\r\n\r\n'
    InlineHeaders = '--%s\r\nContent-Disposition: inline\r\nContent-Type: %s\r\n\r\n%s'

    def __init__(self, payload, format=None):
        self.boundary = boundary = str(uuid.uuid4()).replace('-', '')
        mimetype, data = payload.serialize(format)

        segment = self.InlineHeaders % (boundary, mimetype, data)
        self.segments = segments = [segment.encode('utf8')]

        length = len(segments[0])
        for name, file in sorted(payload.files.items()):
            segment = (self.AttachmentHeaders % (boundary, name)).encode('utf8')
            segments.append(segment)
            length += len(segment)

            segments.append(file)
            length += file.size

        segment = ('\r\n--%s--\r\n' % boundary).encode('utf8')
        segments.append(segment)
        length += len(segment)

        self.openfile = None
        self.headers = {
            'Content-Type': 'multipart/mixed; boundary=%s' % boundary,
            'Content-Length': str(length),
        }

    def next_chunk(self, chunksize=2097152, chunk=b''):
        if self.openfile:
            data = self.openfile.read(chunksize - len(chunk))
            if data:
                chunk += data
            else:
                self.openfile.close()
                self.openfile = None

        if len(chunk) >= chunksize:
            return chunk
        if not self.segments:
            return chunk

        segment = self.segments.pop(0)
        if isinstance(segment, bytes):
            chunk += segment
            if len(chunk) >= chunksize:
                return chunk
            else:
                return self.next_chunk(chunksize, chunk)

        self.openfile = open(segment.filename, 'rb')
        return self.next_chunk(chunksize, chunk)
