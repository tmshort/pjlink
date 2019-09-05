import itertools

import pytest

from pjlink.projector import MUTE_AUDIO, MUTE_VIDEO, Projector, ProjectorError

from server import FakeProjector, FakeProjectorSession

def make_fakes(auth=None, small_pjlink=False):
    fp = FakeProjector()
    fps = FakeProjectorSession(fp, auth=auth, small_pjlink=small_pjlink)
    p = Projector(fps)
    return fp, fps, p

def test_authenticate_none():
    # No authentication:
    fp, fps, p = make_fakes()
    assert p.authenticate(None) is None
    assert fps.stdio_clean and not fps.lockdown

    # Unauthenticated:
    fp, fps, p = make_fakes(auth=('foobar', 'ABCDEFGH'))
    assert not fps.stdio_clean and not fps.lockdown and fps.auth

def test_authenticate_correct():
    fp, fps, p = make_fakes(auth=('foobar', 'ABCDEFGH'))
    assert p.authenticate(lambda: 'foobar') is True
    assert fps.stdio_clean and not fps.lockdown

    fp, fps, p = make_fakes(auth=('foobar', 'QWERTYUI'))
    assert p.authenticate(lambda: 'foobar') is True
    assert fps.stdio_clean and not fps.lockdown

    fp, fps, p = make_fakes(auth=('', 'AAAAAAAA'))
    assert p.authenticate(lambda: '') is True
    assert fps.stdio_clean and not fps.lockdown

def test_authenticate_incorrect():
    # Incorrect password:
    fp, fps, p = make_fakes(auth=('bazzz', 'ABCDEFGH'))
    assert p.authenticate(lambda: 'foobar') is False
    assert fps.lockdown

def test_authenticate_small_letters_none():
    # No authentication:
    fp, fps, p = make_fakes(small_pjlink=True)
    assert p.authenticate(None) is None
    assert fps.stdio_clean and not fps.lockdown

    # Unauthenticated:
    fp, fps, p = make_fakes(auth=('foobar', 'ABCDEFGH'), small_pjlink=True)
    assert not fps.stdio_clean and not fps.lockdown and fps.auth

def test_authenticate_small_letters_correct():
    fp, fps, p = make_fakes(auth=('foobar', 'ABCDEFGH'), small_pjlink=True)
    assert p.authenticate(lambda: 'foobar') is True
    assert fps.stdio_clean and not fps.lockdown

    fp, fps, p = make_fakes(auth=('foobar', 'QWERTYUI'), small_pjlink=True)
    assert p.authenticate(lambda: 'foobar') is True
    assert fps.stdio_clean and not fps.lockdown

    fp, fps, p = make_fakes(auth=('', 'AAAAAAAA'), small_pjlink=True)
    assert p.authenticate(lambda: '') is True
    assert fps.stdio_clean and not fps.lockdown

def test_authenticate_small_letters_incorrect():
    # Incorrect password:
    fp, fps, p = make_fakes(auth=('bazzz', 'ABCDEFGH'), small_pjlink=True)
    assert p.authenticate(lambda: 'foobar') is False
    assert fps.lockdown

def test_power():
    fp, fps, p = make_fakes(auth=False)

    # Projector starts off:
    assert p.get_power() == fp.power == 'off'

    # Gets turned on, and hence enters the warm-up state:
    p.set_power('on')
    assert p.get_power() == fp.power == 'warm-up'

    # Can't request cooling or warm-up states:
    with pytest.raises(ValueError):
        p.set_power('cooling')
    with pytest.raises(ValueError):
        p.set_power('warm-up')

    # The projector is now on, and reports as such:
    fp.power = 'on'
    assert p.get_power() == 'on'

    # Turning it off enters the cooling state:
    p.set_power('off')
    assert p.get_power() == fp.power == 'cooling'

    # The projector is now off, and reports as such:
    fp.power = 'off'
    assert p.get_power() == 'off'

    # Forcibly requesting a bad state results in a parameter error:
    with pytest.raises(ProjectorError) as error:
        p.set_power('cooling', force=True)
    assert error.value.args == (b'out of parameter',)

def test_input_valid():
    fp, fps, p = make_fakes(auth=False)

    # Projector starts in RGB1:
    assert p.get_input() == fp.input == ('RGB', 1)

    for source in ('RGB', 'VIDEO', 'DIGITAL', 'STORAGE', 'NETWORK'):
        for number in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            # Change to that source.
            p.set_input(source, number)
            # Check it changed to that source.
            assert p.get_input() == fp.input == (source, number)

def test_input_invalid():
    fp, fps, p = make_fakes(auth=False)

    assert p.get_input() == fp.input == ('RGB', 1)

    with pytest.raises(ValueError):
        p.set_input('RGB', 0)

    with pytest.raises(ValueError):
        p.set_input('RGB', -1)

    with pytest.raises(ValueError):
        p.set_input('RGB', 13)

    with pytest.raises(ValueError):
        p.set_input('FOO', 1)

    with pytest.raises(ValueError):
        p.set_input('rgb', 1)

def test_mute_valid():
    fp, fps, p = make_fakes(auth=False)

    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (False, False)

    # Mute/unmute audio:
    p.set_mute(MUTE_AUDIO, True)
    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (False, True)

    p.set_mute(MUTE_AUDIO, False)
    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (False, False)

    # Mute/unmite video:
    p.set_mute(MUTE_VIDEO, True)
    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (True, False)

    p.set_mute(MUTE_VIDEO, False)
    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (False, False)

    # Mute/unmite both:
    p.set_mute(MUTE_AUDIO | MUTE_VIDEO, True)
    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (True, True)

    p.set_mute(MUTE_AUDIO | MUTE_VIDEO, False)
    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (False, False)

    # Mute both, unmute video only:
    p.set_mute(MUTE_AUDIO | MUTE_VIDEO, True)
    p.set_mute(MUTE_VIDEO, False)
    assert p.get_mute() == (fp.mute_video, fp.mute_audio) == (False, True)

def test_errors():
    fp, fps, p = make_fakes(auth=False)

    # Manually test some simple cases:
    assert p.get_errors() == fp.errors

    fp.errors['fan'] = 'error'
    assert p.get_errors() == fp.errors

    # Exhaustively test all options:
    kinds = 'fan lamp temperature cover filter other'.split()
    assert sorted(fp.errors.keys()) == sorted(kinds)

    states = 'ok warning error'.split()

    for v in itertools.product(*[states] * len(kinds)):
        fp.errors = dict(zip(kinds, v))

        assert p.get_errors() == fp.errors

def test_lamps():
    fp, fps, p = make_fakes(auth=False)

    assert p.get_lamps() == [(42, False)]

    fp.lamps = [(66, True)]
    assert p.get_lamps() == fp.lamps

    fp.lamps = [(100, False), (50, True)]
    assert p.get_lamps() == fp.lamps

    fp.lamps = [(0, False)]
    assert p.get_lamps() == fp.lamps

    fp.lamps = [(99999, True)]
    assert p.get_lamps() == fp.lamps

    fp.lamps = [(99999, True)] * 8
    assert p.get_lamps() == fp.lamps

def test_inputs_valid():
    fp, fps, p = make_fakes(auth=False)

    assert p.get_inputs() == fp.inputs

    fp.inputs = [('RGB', 1)]
    assert p.get_inputs() == fp.inputs

def test_inputs_invalid():
    fp, fps, p = make_fakes(auth=False)

    with pytest.raises(AssertionError):
        fp.inputs = [('RGB', 0)]
        assert p.get_inputs() == fp.inputs

    with pytest.raises(AssertionError):
        fp.inputs = [('RGB', 'Z')]
        assert p.get_inputs() == fp.inputs

def test_info():
    fp, fps, p = make_fakes(auth=False)

    assert p.get_name() == 'FakeProjector'
    assert p.get_manufacturer() == 'flowblok'
    assert p.get_product_name() == 'python pjlink'
    assert p.get_other_info() == 'testing'

    # TODO: test these are all handled as UTF-8, with max lengths
