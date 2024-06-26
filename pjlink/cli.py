import argparse
from getpass import getpass
from os import path
from socket import socket
import sys
import textwrap

from six import print_, PY2
from six.moves.configparser import (
    NoSectionError,
    ConfigParser
)

import appdirs

from pjlink import Projector
from pjlink import projector
from pjlink.cliutils import make_command

if PY2:
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

def cmd_power(p, state=None):
    if state is None:
        print(p.get_power())
    else:
        p.set_power(state)

def cmd_input(p, source, number):
    if source is None:
        source, number = p.get_input()
        print('%s %s' % (source, number))
    else:
        p.set_input(source, number)

def cmd_inputs(p):
    for source, number in p.get_inputs():
        print('%s-%s' % (source, number))

def cmd_mute_state(p):
    video, audio = p.get_mute()
    print('video: %s' % ('muted' if video else 'unmuted'))
    print('audio: %s' % ('muted' if audio else 'unmuted'))

def cmd_mute(p, what):
    if what is None:
        return cmd_mute_state(p)
    what = {
        'video': projector.MUTE_VIDEO,
        'audio': projector.MUTE_AUDIO,
        'all': projector.MUTE_VIDEO | projector.MUTE_AUDIO,
    }[what]
    p.set_mute(what, True)

def cmd_unmute(p, what):
    if what is None:
        return cmd_mute_state(p)
    what = {
        'video': projector.MUTE_VIDEO,
        'audio': projector.MUTE_AUDIO,
        'all': projector.MUTE_VIDEO | projector.MUTE_AUDIO,
    }[what]
    p.set_mute(what, False)

def cmd_info(p):
    info = [
        ('Name', p.get_name()),
        ('Manufacturer', p.get_manufacturer()),
        ('Product Name', p.get_product_name()),
        ('Other Info', p.get_other_info())
    ]
    for key, value in info:
        print_(u'%s: %s' % (key, value))

def cmd_lamps(p):
    for i, (time, state) in enumerate(p.get_lamps(), 1):
        print('Lamp %d: %s (%d hours)' % (
            i,
            'on' if state else 'off',
            time,
        ))

def cmd_errors(p):
    for what, state in sorted(p.get_errors().items()):
        print('%s: %s' % (what, state))


def make_parser():
    ad = appdirs.user_data_dir('pjlink')
    cf = path.join(ad, 'pjlink.conf')

    parser = argparse.ArgumentParser(description="The pjlink utility controls and reports the status of projectors.",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent(f"""\
                                     Default config file is '{cf}'.

                                     Example config file:
                                        [default]
                                        host=192.168.100
                                        port=4352
                                        password=panasonic

                                     See https://blog.flowblok.id.au/2012-11/controlling-projectors-with-pjlink.html for additional information
                                     """))
    parser.add_argument(
        '-p', '--projector',
        help='host:port of the projector to connect to (e.g. 127.0.0.1:4352)',
    )
    parser.add_argument('-c', '--config')

    sub = parser.add_subparsers(title='command')

    power = make_command(sub, 'power', cmd_power)
    power.add_argument('state', nargs='?', choices=('on', 'off'))

    inpt = make_command(sub, 'input', cmd_input)
    inpt.add_argument('source', nargs='?', choices=projector.SOURCE_TYPES)
    inpt.add_argument('number', nargs='?', choices='123456789', default='1')

    make_command(sub, 'inputs', cmd_inputs)

    mute = make_command(sub, 'mute', cmd_mute)
    mute.add_argument('what', nargs='?', choices=('video', 'audio', 'all'))

    unmute = make_command(sub, 'unmute', cmd_unmute)
    unmute.add_argument('what', nargs='?', choices=('video', 'audio', 'all'))

    make_command(sub, 'info', cmd_info)
    make_command(sub, 'lamps', cmd_lamps)
    make_command(sub, 'errors', cmd_errors)
    make_command(sub, 'help', None)

    return parser

def resolve_projector(projector, conf_file):
    password = None

    # If the projector argument was specified, this takes precedence.
    if projector is not None and ':' in projector:
        host, port = projector.rsplit(':', 1)
        port = int(port)
        return host, port, password

    # Otherwise, try reading from a config file.
    if conf_file is None:
        appdir = appdirs.user_data_dir('pjlink')
        conf_file = path.join(appdir, 'pjlink.conf')

    try:
        config = ConfigParser({'port': '4352', 'password': ''})
        with open(conf_file, 'r') as f:
            config.readfp(f)

        section = projector
        if projector is None:
            section = 'default'

        host = config.get(section, 'host')
        port = config.getint(section, 'port')
        password = config.get(section, 'password') or None

    except (NoSectionError, IOError):
        if projector is None:
            raise KeyError('No default projector defined in %s' % conf_file)

        # no config file, or no projector defined for this host
        # thus, treat the projector as a hostname w/o port
        host = projector
        port = 4352

    return host, port, password

def main():
    parser = make_parser()
    args = parser.parse_args()

    kwargs = dict(args._get_kwargs())
    func = kwargs.pop('__func__', None)
    # If no command was selected, show usage and quit.
    if not func:
        parser.print_help()
        return
    projector = kwargs.pop('projector')
    config = kwargs.pop('config')
    host, port, password = resolve_projector(projector, config)

    sock = socket()
    sock.connect((host, port))
    f = sock.makefile('rwb')

    if password:
        get_password = lambda: password
    else:
        get_password = getpass

    proj = Projector(f)
    rv = proj.authenticate(get_password)
    if rv is False:
        sys.stderr.write('Incorrect password.')
        sys.stderr.flush()
        return

    func(proj, **kwargs)

if __name__ == '__main__':
    main()
