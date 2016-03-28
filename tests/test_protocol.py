# -*- coding: utf-8 -*-

import pytest
from six import BytesIO

from pjlink import protocol

def test_read_until():
    assert protocol.read_until(BytesIO(b'foobar'), b'b') == b'foo'
    assert protocol.read_until(BytesIO(b'foobar'), b'f') == b''
    assert protocol.read_until(BytesIO(b'foobar'), b'q') == b'foobar'

    with pytest.raises(AssertionError):
        protocol.read_until(BytesIO(b'foobar'), b'oo')

def test_to_binary():
    # Normal usage:
    assert protocol.to_binary(b'POWR', b'foo') == b'%1POWR foo\r'
    assert protocol.to_binary(b'INPT', b'') == b'%1INPT \r'

    # Command must be 4 characters long:
    with pytest.raises(AssertionError):
        protocol.to_binary(b'INP', b'')

    with pytest.raises(AssertionError):
        protocol.to_binary(b'INPTT', b'')

    # Param must be <= 128 bytes:
    protocol.to_binary(b'INPT', b'a' * 127)
    protocol.to_binary(b'INPT', b'a' * 128)

    with pytest.raises(AssertionError):
        protocol.to_binary(b'INPT', b'a' * 129)

    with pytest.raises(AssertionError):
        protocol.to_binary(b'INPT', b'a' * 130)

def test_parse_response():
    # Normal case:
    assert protocol.parse_response(BytesIO(b'%1POWR=ON\r')) == \
        (b'POWR', b'ON')

    # Sane-looking messages:
    assert protocol.parse_response(BytesIO(b'%1aBc4=eFg=%1kL\r')) == \
        (b'ABC4', b'eFg=%1kL')

    # UTF-8 encoded data:
    param = u'möse'.encode('utf-8')
    assert protocol.parse_response(BytesIO(b'%1INFO=' + param + b'\r')) == \
        (b'INFO', param)

    # Various badly formed messages:
    with pytest.raises(ValueError):
        protocol.parse_response(BytesIO(b''))
    with pytest.raises(ValueError):
        protocol.parse_response(BytesIO(b'$'))
    with pytest.raises(ValueError):
        protocol.parse_response(BytesIO(b'%'))
    with pytest.raises(ValueError):
        protocol.parse_response(BytesIO(b'%0'))
    with pytest.raises(ValueError):
        protocol.parse_response(BytesIO(b'%1ABCD'))
    with pytest.raises(ValueError):
        protocol.parse_response(BytesIO(b'%1ABCD '))

class BytesI(BytesIO):
    def write(self, data):
        pass

    def flush(self):
        pass

def test_send_command():
    # Normal case:
    f = BytesI(b'%1POWR=ON\r')
    assert protocol.send_command(f, b'POWR', b'ON') == (True, b'ON')

    f = BytesI(b'%1INPT=VGA1\r')
    assert protocol.send_command(f, b'INPT', b'VGA1') == (True, b'VGA1')

    # Errors:
    f = BytesI(b'%1INPT=ERR1\r')
    assert protocol.send_command(f, b'INPT', b'VGA1') == \
        (False, b'undefined command')

    f = BytesI(b'%1INPT=ERR2\r')
    assert protocol.send_command(f, b'INPT', b'VGA1') == \
        (False, b'out of parameter')

    f = BytesI(b'%1INPT=ERR3\r')
    assert protocol.send_command(f, b'INPT', b'VGA1') == \
        (False, b'unavailable time')

    f = BytesI(b'%1INPT=ERR4\r')
    assert protocol.send_command(f, b'INPT', b'VGA1') == \
        (False, b'projector failure')
