import io
import unittest
import wave
from unittest.mock import patch

from magicpointer.audio import Chimes, tone
from test_app import debug_session
from test_two_camera_debug import dual_session
from test_wilor_debug import FakeDebug


class ClickAudioTests(unittest.TestCase):
    def test_clicks_are_short_distinct_valid_wavs(self):
        sounds = [tone(key) for key in (True,False,'left','right')]
        self.assertEqual(len(set(sounds)),4)
        for data in sounds[2:]:
            with wave.open(io.BytesIO(data)) as sound:
                self.assertEqual((sound.getnchannels(),sound.getsampwidth()),(1,2))
                self.assertGreater(sound.getnframes(),0)
                self.assertLess(sound.getnframes()/sound.getframerate(),.1)

    def test_click_sound_dispatched_once_for_one_click(self):
        _, _, _, _, audio = debug_session()
        clicks = [call.args[0] for call in audio.play.call_args_list if call.args[0] in ('left','right')]
        self.assertEqual(clicks,['left'])

    def test_mute_suppresses_all_sound_events(self):
        with patch('magicpointer.audio.threading.Thread'):
            chimes = Chimes(muted=True)
            for value in (True, False, 'left', 'right'):
                chimes.play(value)
            self.assertTrue(chimes.messages.empty())

    def test_wilor_desktop_sounds_follow_emitted_left_and_right_clicks(self):
        with patch('magicpointer.wilor_debug.WiLoRDebug', return_value=FakeDebug()):
            _, _, _, _, _, audio, _ = dual_session(frame_count=102,
                force_uncalibrated=True, desktop_control=True,
                capture_args=('--hand-backend','wilor'))
        clicks = [call.args[0] for call in audio.play.call_args_list
                  if call.args[0] in ('left','right')]
        self.assertEqual(clicks,['left','right'])
