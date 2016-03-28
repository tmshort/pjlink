import pytest
from six import StringIO

from pjlink import protocol

def test_read_until():
    assert protocol.read_until(StringIO('foobar'), 'b') == 'foo'
    assert protocol.read_until(StringIO('foobar'), 'f') == ''
    assert protocol.read_until(StringIO('foobar'), 'q') == 'foobar'

    with pytest.raises(AssertionError):
        protocol.read_until(StringIO('foobar'), 'oo')

def test_to_binary():
    # Normal usage:
    assert protocol.to_binary('POWR', 'foo') == '%1POWR foo\r'
    assert protocol.to_binary('INPT', '') == '%1INPT \r'

    # Command must be 4 characters long:
    with pytest.raises(AssertionError):
        protocol.to_binary('INP', '')

    with pytest.raises(AssertionError):
        protocol.to_binary('INPTT', '')

    # Param must be <= 128 bytes:
    protocol.to_binary('INPT', 'a' * 127)
    protocol.to_binary('INPT', 'a' * 128)

    with pytest.raises(AssertionError):
        protocol.to_binary('INPT', 'a' * 129)

    with pytest.raises(AssertionError):
        protocol.to_binary('INPT', 'a' * 130)

def test_parse_response():
    # Normal case:
    assert protocol.parse_response(StringIO('%1POWR=ON\r')) == \
        ('POWR', 'ON')

    # Sane-looking messages:
    assert protocol.parse_response(StringIO('%1aBc4=eFg=%1kL\r')) == \
        ('ABC4', 'eFg=%1kL')

    # Various badly formed messages:
    with pytest.raises(IndexError):
        protocol.parse_response(StringIO(''))
    with pytest.raises(AssertionError):
        protocol.parse_response(StringIO('$'))
    with pytest.raises(IndexError):
        protocol.parse_response(StringIO('%'))
    with pytest.raises(AssertionError):
        protocol.parse_response(StringIO('%0'))
    with pytest.raises(IndexError):
        protocol.parse_response(StringIO('%1ABCD'))
    with pytest.raises(AssertionError):
        protocol.parse_response(StringIO('%1ABCD '))

class StringI(StringIO):
    def write(self, data):
        pass

    def flush(self):
        pass

def test_send_command():
    # Normal case:
    f = StringI('%1POWR=ON\r')
    assert protocol.send_command(f, 'POWR', 'ON') == (True, 'ON')

    f = StringI('%1INPT=VGA1\r')
    assert protocol.send_command(f, 'INPT', 'VGA1') == (True, 'VGA1')

    # Errors:
    f = StringI('%1INPT=ERR1\r')
    assert protocol.send_command(f, 'INPT', 'VGA1') == \
        (False, 'undefined command')

    f = StringI('%1INPT=ERR2\r')
    assert protocol.send_command(f, 'INPT', 'VGA1') == \
        (False, 'out of parameter')

    f = StringI('%1INPT=ERR3\r')
    assert protocol.send_command(f, 'INPT', 'VGA1') == \
        (False, 'unavailable time')

    f = StringI('%1INPT=ERR4\r')
    assert protocol.send_command(f, 'INPT', 'VGA1') == \
        (False, 'projector failure')
