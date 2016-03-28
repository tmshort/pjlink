from contextlib import contextmanager
import hashlib
import socket

from six.moves import socketserver

from pjlink import projector

MAX_PACKET_SIZE = 1024

class FakeProjector(object):
    """Fake implementation of a PJLink projector."""

    def __init__(self):
        self.name = 'FakeProjector'
        self.manufacturer = 'flowblok'
        self.product_name = 'python pjlink'
        self.other_info = 'testing'

        self.power = 'off'
        self.input = ('RGB', 1)
        self.mute_video = False
        self.mute_audio = False

        # This projector has one lamp which has been on for 42 hours.
        self.lamps = [(42, False)]

        self.inputs = [
            # Some sane cases:
            ('RGB', 1), ('RGB', 2),
            ('VIDEO', 1),
            # All the available inputs:
            ('DIGITAL', 1), ('DIGITAL', 2), ('DIGITAL', 3),
            ('DIGITAL', 4), ('DIGITAL', 5), ('DIGITAL', 6),
            ('DIGITAL', 7), ('DIGITAL', 8), ('DIGITAL', 9),
            # No STORAGE inputs.
            # A badly numbered input:
            ('NETWORK', 5),
        ]

        self.errors = {
            'fan': 'ok',
            'lamp': 'ok',
            'temperature': 'ok',
            'cover': 'ok',
            'filter': 'ok',
            'other': 'ok',
        }

    def handle_power(self, param):
        if param == '?':
            return projector.POWER_STATES[self.power]
        elif param == '1':
            if self.power == 'off':
                self.power = 'warm-up'
            return 'OK'
        elif param == '0':
            if self.power == 'on':
                self.power = 'cooling'
            return 'OK'
        return 'ERR2'

    def handle_input(self, param):
        if param == '?':
            source, number = self.input
            return projector.SOURCE_TYPES[source] + str(number)

        if len(param) != 2:
            return 'ERR2'
        source, number = param

        if source not in projector.SOURCE_TYPES_REV:
            return 'ERR2'

        if number not in '123456789':
            return 'ERR2'

        self.input = projector.SOURCE_TYPES_REV[source], int(number)
        return 'OK'

    def handle_mute(self, param):
        if param == '?':
            if self.mute_audio and self.mute_video:
                return '31'
            elif self.mute_audio:
                return '21'
            elif self.mute_video:
                return '11'
            else:
                return '30'

        if param not in ('10', '11', '20', '21', '30', '31'):
            return 'ERR2'

        what, state = param
        state = state == '1'

        if what in '13':
            self.mute_video = state
        if what in '23':
            self.mute_audio = state
        return 'OK'

    def handle_errors(self, param):
        if param == '?':
            return ''.join(
                str(projector.ERROR_STATES[self.errors[kind]])
                for kind in 'fan lamp temperature cover filter other'.split()
            )
        return 'ERR2'

    def handle_lamps(self, param):
        if param != '?':
            return 'ERR2'

        result = []
        for n_hours, state in self.lamps:
            assert 0 <= n_hours < 100000
            result.append(str(n_hours))
            result.append('1' if state else '0')
        return ' '.join(result)

    def handle_inputs(self, param):
        if param != '?':
            return 'ERR2'

        result = []
        for source, number in self.inputs:
            result.append(projector.SOURCE_TYPES[source] + str(number))
        return ' '.join(result)

    def handle_info(self, body, param):
        if param != '?':
            return 'ERR2'
        if body == 'NAME':
            return self.name
        elif body == 'INF1':
            return self.manufacturer
        elif body == 'INF2':
            return self.product_name
        else:
            assert body == 'INFO'
            return self.other_info

class FakeProjectorSession(object):
    def __init__(self, fp, auth=None):
        self.fp = fp

        self.stdin = ''

        self.lockdown = False

        if auth is False:
            # Skip the authentication stage.
            self.auth = None
            self.stdout = b''

        elif auth is None:
            # No password.
            self.auth = None
            self.stdout = b'PJLINK 0\r'

        else:
            # Auth is a tuple of (password, salt).
            password, salt = auth
            assert len(salt) == 8

            data = (salt + password).encode('utf-8')
            self.auth = hashlib.md5(data).hexdigest()
            self.stdout = ('PJLINK 1 ' + salt + '\r').encode('utf-8')

    @property
    def stdio_clean(self):
        return not self.stdin and not self.stdout

    # This class functions as a file-like object.

    def write(self, data):
        # Write data to stdin.
        self.stdin += data.decode('utf-8')
        # Note that in order to expose bugs, we don't process it yet!
        # Instead, we wait until an explicit flush(), or a blocking read().

    def read(self, n=None):
        if n is None:
            n = len(self.stdout)

        # If we don't have enough data to read, try processing stdin.
        if len(self.stdout) < n:
            self.flush()
        # Rather than returning less than the requested amount of data
        # (which would be allowable), throw an error to help debug.
        assert len(self.stdout) >= n, 'Caller tried to read() too much.'
        result, self.stdout = self.stdout[:n], self.stdout[n:]
        return result

    def flush(self):
        # If we have authentication data, it means the client hasn't authed yet.
        if self.auth:
            # The MD5 hex digest is 32 characters long.
            if len(self.stdin) < 32:
                return
            # Pull it off stdin.
            data, self.stdin = self.stdin[:32], self.stdin[32:]
            # If it's wrong, put the projector into lockdown mode,
            # otherwise, start processing commands.
            if data != self.auth:
                self.lockdown = True
                # This isn't quite accurate with what I've observed in reality:
                # it gets sent back after the first command is sent.
                self.stdout += b'PJLINK ERRA\r'
            # Clear auth, so we stop checking the password.
            self.auth = None

        # If we're in lockdown mode, don't process commands.
        if self.lockdown:
            return

        while '\r' in self.stdin:
            command, self.stdin = self.stdin.split('\r', 1)
            assert command.startswith('%1') and ' ' in command
            body, param = command[2:].split(' ', 1)
            assert len(body) == 4

            if body == 'POWR':
                response = self.fp.handle_power(param)
            elif body == 'INPT':
                response = self.fp.handle_input(param)
            elif body == 'AVMT':
                response = self.fp.handle_mute(param)
            elif body == 'ERST':
                response = self.fp.handle_errors(param)
            elif body == 'LAMP':
                response = self.fp.handle_lamps(param)
            elif body == 'INST':
                response = self.fp.handle_inputs(param)
            elif body in ('NAME', 'INF1', 'INF2', 'INFO'):
                response = self.fp.handle_info(body, param)
            else:
                response = 'ERR1'

            self.stdout += ('%1' + body + '=' + response + '\r').encode('utf-8')

def make_request_handler(fp, auth):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            fps = FakeProjectorSession(fp, auth=auth)

            # This is only mildly hacky, in that we know communication will
            # strictly alternate.
            while True:
                if fps.stdout:
                    self.request.sendall(fps.read())

                data = self.request.recv(MAX_PACKET_SIZE)
                if not data:
                    break
                fps.write(data)
                fps.flush()

    return Handler

@contextmanager
def fake_projection_server(fp, auth=None, hostport=('localhost', 0)):
    server = socketserver.TCPServer(hostport, make_request_handler(fp, auth))
    try:
        host, port = server.server_address
        yield (host, port)
        server.handle_request()
    finally:
        server.server_close()
