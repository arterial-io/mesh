from wsgiref.simple_server import WSGIServer


class MockWSGIServer(object):
    application = None

    def setup_environ(self):
        env = self.base_environ = {}
        env['SERVER_NAME'] = 'mock-wsgi-server'
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'
        env['SERVER_PORT'] = 'XXX'
        env['REMOTE_HOST'] = ''
        env['CONTENT_LENGTH'] = ''
        env['SCRIPT_NAME'] = ''

    def get_app(self):
        return self.application

    def set_app(self, application):
        self.application = application
