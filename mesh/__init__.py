import os

if os.environ.get('SHELL_DEBUG_LOGGING') == 'true':
    import logging
    from mesh.util import LogFormatter
    log = logging.getLogger('mesh')
    log.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter())
    log.addHandler(handler)
