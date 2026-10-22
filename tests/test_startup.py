from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import platform
import tempfile
import unittest
from unittest.mock import patch

from magicpointer.cli import main, parser
from magicpointer.cameras import Cameras


class StartupTests(unittest.TestCase):
    def test_help_without_hardware(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 0)
        self.assertIn('calibrate', output.getvalue())

    def test_invalid_numeric_options(self):
        for value in ('0', '-1', 'nan', 'inf'):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser().parse_args(['run', '--workspace-width', value])

    def test_same_camera_rejected_before_opening(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['run', '--left', '0', '--right', '0']), 1)

    def test_calibrated_control_requires_two_cameras(self):
        with redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(['run', '--calibrated']), 1)
        self.assertIn('two cameras', output.getvalue())

    def test_camera_open_failure_releases_resources(self):
        with patch('cv2.VideoCapture') as capture:
            capture.return_value.isOpened.return_value = False
            with self.assertRaises(ValueError):
                Cameras(0)
            capture.return_value.release.assert_called_once()

    def test_macos_camera_failure_explains_first_permission_prompt(self):
        with patch('magicpointer.cameras.platform.system', return_value='Darwin'), \
                patch('cv2.VideoCapture') as capture:
            capture.return_value.isOpened.return_value = False
            with self.assertRaises(ValueError) as failure:
                Cameras(0)
            message = str(failure.exception)
            self.assertIn('choose Allow and rerun', message)
            self.assertIn('Privacy & Security > Camera', message)
            self.assertIn('VS Code, Terminal, or iTerm', message)
            self.assertIn('Quit and reopen', message)
            capture.return_value.release.assert_called_once()

    def test_second_camera_failure_releases_both(self):
        from unittest.mock import MagicMock
        import numpy as np
        one, two = MagicMock(), MagicMock()
        one.isOpened.return_value = True
        one.get.return_value = 30.
        one.read.return_value = (True, np.zeros((1080, 1920, 3), dtype=np.uint8))
        two.isOpened.return_value = False
        with patch('cv2.VideoCapture', side_effect=[one, two]):
            with self.assertRaises(ValueError):
                Cameras(0, 1)
        one.release.assert_called_once()
        two.release.assert_called_once()

    def test_targets_preserve_physical_dimensions(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            self.assertEqual(main(['targets', '--output', directory]), 0)
            self.assertIn('width="300.0mm"', (Path(directory)/'checkerboard.svg').read_text())
            self.assertTrue((Path(directory)/'marker-0.svg').is_file())
            self.assertTrue((Path(directory)/'marker-1.svg').is_file())

    @unittest.skipUnless(platform.system() == 'Windows', 'Native Windows ABI check')
    def test_windows_sendinput_structure_abi_without_sending_events(self):
        import ctypes
        from magicpointer.desktop import Desktop
        desktop = Desktop()
        self.assertEqual(ctypes.sizeof(desktop.Input), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


if __name__ == '__main__':
    unittest.main()
