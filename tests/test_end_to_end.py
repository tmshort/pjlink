# -*- coding: utf-8 -*-

import subprocess
from tempfile import NamedTemporaryFile

import pytest

from server import FakeProjector, fake_projection_server

def start_cli(*args):
    p = subprocess.Popen(
        ('pjlink',) + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p.stdin.close()
    return p

def finish_cli(p):
    rv = p.wait()
    stdout = p.stdout.read().decode('utf-8')
    stderr = p.stderr.read().decode('utf-8')
    if rv != 0 or stderr:
        raise ValueError(
            'Process exited with return code %d.\n' % rv +
            'STDERR:\n' + stderr + '\n\n' +
            'STDOUT:\n' + stdout
        )
    return stdout

def run_command(fp, *args):
    with fake_projection_server(fp) as addr:
        p = start_cli('-p', '%s:%d' % addr, *args)
    return finish_cli(p)

def run_command_with_auth(fp, client_pw, server_pw, salt, *args):
    with NamedTemporaryFile() as conf_file:
        with fake_projection_server(fp, (server_pw, salt)) as (host, port):
            conf_file.write(
                ('[default]\nhost = %s\nport = %s\npassword = %s\n' % (
                    host, port, client_pw,
                )).encode('utf-8')
            )
            conf_file.flush()

            p = start_cli('-c', conf_file.name, *args)
        return finish_cli(p)

def test_auth():
    fp = FakeProjector()

    # No auth.
    assert run_command(fp, 'power') == 'off\n'
    # Correct auth.
    assert run_command_with_auth(fp, 'foobar', 'foobar', 'ABCDEFGH', 'power') == 'off\n'
    # Invalid auth.
    with pytest.raises(ValueError) as e:
        run_command_with_auth(fp, 'baz', 'foobar', 'ABCDEFGH', 'power')
    assert e.value.args == (
        'Process exited with return code 0.\n'
        'STDERR:\nIncorrect password.\n\n'
        'STDOUT:\n',
    )

def test_power():
    fp = FakeProjector()

    assert run_command(fp, 'power') == 'off\n'

    # Turn power on:
    assert run_command(fp, 'power', 'on') == ''
    assert run_command(fp, 'power') == 'warm-up\n'
    fp.power = 'on'
    assert run_command(fp, 'power') == 'on\n'

    # Turn power off:
    assert run_command(fp, 'power', 'off') == ''
    assert run_command(fp, 'power') == 'cooling\n'
    fp.power = 'off'
    assert run_command(fp, 'power') == 'off\n'

def test_input():
    fp = FakeProjector()

    assert fp.input == ('RGB', 1)
    assert run_command(fp, 'input') == 'RGB 1\n'

    assert run_command(fp, 'input', 'RGB', '2') == ''
    assert run_command(fp, 'input') == 'RGB 2\n'

    assert run_command(fp, 'input', 'DIGITAL', '9') == ''
    assert run_command(fp, 'input') == 'DIGITAL 9\n'

def test_mute():
    fp = FakeProjector()

    assert run_command(fp, 'mute') == 'video: unmuted\naudio: unmuted\n'
    assert run_command(fp, 'unmute') == 'video: unmuted\naudio: unmuted\n'

    assert run_command(fp, 'mute', 'video') == ''
    assert run_command(fp, 'mute') == 'video: muted\naudio: unmuted\n'
    assert run_command(fp, 'mute', 'audio') == ''
    assert run_command(fp, 'mute') == 'video: muted\naudio: muted\n'

    assert run_command(fp, 'unmute', 'audio') == ''
    assert run_command(fp, 'mute') == 'video: muted\naudio: unmuted\n'
    assert run_command(fp, 'unmute', 'video') == ''
    assert run_command(fp, 'mute') == 'video: unmuted\naudio: unmuted\n'

def test_inputs():
    fp = FakeProjector()

    assert run_command(fp, 'inputs') == (
        'RGB-1\n'
        'RGB-2\n'
        'VIDEO-1\n'
        'DIGITAL-1\n'
        'DIGITAL-2\n'
        'DIGITAL-3\n'
        'DIGITAL-4\n'
        'DIGITAL-5\n'
        'DIGITAL-6\n'
        'DIGITAL-7\n'
        'DIGITAL-8\n'
        'DIGITAL-9\n'
        'NETWORK-5\n'
    )

def test_info():
    fp = FakeProjector()
    fp.name = u'Möse'

    assert run_command(fp, 'info') == (
        u'Name: Möse\n'
        'Manufacturer: flowblok\n'
        'Product Name: python pjlink\n'
        'Other Info: testing\n'
    )

def test_lamps():
    fp = FakeProjector()

    assert run_command(fp, 'lamps') == 'Lamp 1: off (42 hours)\n'

    fp.lamps = [(99999, True), (0, False)]
    assert run_command(fp, 'lamps') == (
        'Lamp 1: on (99999 hours)\n'
        'Lamp 2: off (0 hours)\n'
    )

def test_errors():
    fp = FakeProjector()

    fp.errors['temperature'] = 'warning'
    fp.errors['other'] = 'error'
    assert run_command(fp, 'errors') == (
        'cover: ok\n'
        'fan: ok\n'
        'filter: ok\n'
        'lamp: ok\n'
        'other: error\n'
        'temperature: warning\n'
    )
