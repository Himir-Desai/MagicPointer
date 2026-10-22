"""Short synthesized activation/deactivation and click sounds; no camera-loop blocking."""
import io
import math
import platform
from pathlib import Path
import queue
import struct
import subprocess
import tempfile
import threading
import wave


def tone(activate):
    samples = bytearray()
    rate = 22050
    frequencies, duration = {
        True: ((660, 880), .075), False: ((440, 330), .075),
        'left': ((1100,), .045), 'right': ((750, 1000), .035),
    }[activate]
    for frequency in frequencies:
        n = int(rate * duration)
        for i in range(n):
            envelope = math.sin(math.pi*i/n) ** 2
            samples.extend(struct.pack('<h', int(4500 * envelope * math.sin(2*math.pi*frequency*i/rate))))
    output = io.BytesIO()
    with wave.open(output, 'wb') as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(rate)
        sound.writeframes(samples)
    return output.getvalue()


class Chimes:
    def __init__(self, muted=False):
        self.muted = muted
        self.messages = queue.Queue(maxsize=4)
        self.sounds = {key: tone(key) for key in (True, False, "left", "right")}
        self.worker = threading.Thread(target=self._play, daemon=True)
        self.worker.start()

    def play(self, activate):
        if not self.muted:
            try:
                self.messages.put_nowait(activate)
            except queue.Full:
                pass

    def _play(self):
        while True:
            activate = self.messages.get()
            if activate is None:
                return
            try:
                if platform.system() == "Windows":
                    import winsound
                    winsound.PlaySound(self.sounds[activate], winsound.SND_MEMORY)
                elif platform.system() == "Darwin":
                    with tempfile.TemporaryDirectory(prefix="magicpointer-chime-") as directory:
                        path = Path(directory) / "chime.wav"
                        path.write_bytes(self.sounds[activate])
                        subprocess.run(["/usr/bin/afplay", str(path)], check=False, timeout=2,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass  # Missing audio never disables pointer control.

    def close(self):
        # Drop queued sounds on exit; allow the short current sound to finish.
        while True:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                break
        self.messages.put_nowait(None)
        self.worker.join(timeout=2.5)
