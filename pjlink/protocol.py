def read_until(f, term):
    assert len(term) == 1
    data = []
    c = f.read(1)
    while c and c != term:
        data.append(c)
        c = f.read(1)
    return b''.join(data)

def to_binary(body, param, sep=b' '):
    assert body.isupper()

    assert len(body) == 4
    assert len(param) <= 128

    return b'%1' + body + sep + param + b'\r'

def parse_response(f, data=b''):
    if len(data) < 7:
        data += f.read(2 + 4 + 1 - len(data))

    header = data[0:1]
    if header != b'%':
        raise ValueError('Invalid header in %r' % (data,))

    version = data[1:2]
    # only class 1 is currently defined
    if version != b'1':
        raise ValueError('Invalid version in %r' % (data,))

    body = data[2:6]
    # commands are case-insensitive, but let's turn them upper case anyway
    # this will avoid the rest of our code from making this mistake
    # FIXME: AFAIR this takes the current locale into consideration, it shouldn't.
    body = body.upper()

    sep = data[6:]
    if sep != b'=':
        raise ValueError('Invalid separator in %r' % (data,))

    param = read_until(f, b'\r')

    return (body, param)

ERRORS = {
    b'ERR1': b'undefined command',
    b'ERR2': b'out of parameter',
    b'ERR3': b'unavailable time',
    b'ERR4': b'projector failure',
}

def send_command(f, req_body, req_param):
    data = to_binary(req_body, req_param)
    f.write(data)
    f.flush()

    resp_body, resp_param = parse_response(f)
    assert resp_body == req_body

    if resp_param in ERRORS:
        return False, ERRORS[resp_param]
    return True, resp_param

