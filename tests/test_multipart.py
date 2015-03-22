import os
from io import BytesIO
from tempfile import mkstemp

try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

from scheme import formats

from mesh.transport.multipart import *

INLINE_PAYLOAD = '%s\n%s\n%s' % ('a' * 60, 'b' * 60, 'c' * 60)
FILE1_CONTENT = 'abc' * 1000
FILE2_CONTENT = 'def' * 700

EXPECTED_ENCODING = '\r\n'.join([
    '--%(boundary)s',
    'Content-Disposition: inline',
    'Content-Type: text/plain',
    '',
    INLINE_PAYLOAD,
    '--%(boundary)s',
    'Content-Disposition: attachment; name="file1"',
    '',
    FILE1_CONTENT,
    '--%(boundary)s',
    'Content-Disposition: attachment; name="file2"',
    '',
    FILE2_CONTENT,
    '--%(boundary)s--\r\n'
])

class TestMultipartMixedEncoder(TestCase):
    def setUp(self):
        fileno, self.file1 = mkstemp('.txt', 'mesh_test')
        os.write(fileno, FILE1_CONTENT.encode('utf8'))
        os.close(fileno)

        fileno, self.file2 = mkstemp('.txt', 'mesh_test')
        os.write(fileno, FILE2_CONTENT.encode('utf8'))
        os.close(fileno)

    def tearDown(self):
        os.unlink(self.file1)
        os.unlink(self.file2)

    def test_encoding(self):
        payload = MultipartPayload(INLINE_PAYLOAD, 'text/plain')
        payload.attach('file1', self.file1)
        payload.attach('file2', self.file2)


        for chunksize in (3, 10, 50, 100, 300, 800, 1200, 2400, 4200, 5000, 6000):
            encoder = MultipartMixedEncoder(payload)
            content_type = encoder.headers['Content-Type']
            content_length = int(encoder.headers['Content-Length'])

            preamble, sep, boundary = content_type.partition('=')
            expected = (EXPECTED_ENCODING % {'boundary': boundary}).encode('utf8')

            content = []
            while True:
                chunk = encoder.next_chunk(chunksize)
                if chunk:
                    content.append(chunk)
                else:
                    content = b''.join(content)
                    break

            self.assertEqual(len(content), content_length)
            self.assertEqual(content, expected)

class TestMultipartMixedParser(TestCase):
    BOUNDARY = 'f674299ece60410f923111b471f33ef0'

    def test_parsing(self):
        encoded = EXPECTED_ENCODING % {'boundary': self.BOUNDARY}
        stream = BytesIO(encoded.encode('utf8'))

        parser = MultipartMixedParser()
        payload = parser.parse(stream, 'multipart/mixed; boundary=' + self.BOUNDARY)

        self.assertIsInstance(payload, MultipartPayload)
        self.assertEqual(payload.mimetype, 'text/plain')
        self.assertEqual(payload.payload, INLINE_PAYLOAD)
        self.assertEqual(set(payload.files.keys()), set(['file1', 'file2']))

        for name, expected in (('file1', FILE1_CONTENT), ('file2', FILE2_CONTENT)):
            subject = payload.files[name]
            self.assertEqual(subject.name, name)
            self.assertTrue(os.path.exists(subject.filename))

            with open(subject.filename) as openfile:
                self.assertEqual(openfile.read(), expected)

            os.unlink(subject.filename)
