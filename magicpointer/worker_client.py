"""Bounded subprocess lifecycle for the optional, isolated WiLoR environment."""
import json
from pathlib import Path
import queue
import subprocess
import threading


class WiLoRWorker:
    def __init__(self, args, views, *, optimized=False):
        self.timeout = args.worker_timeout
        self.responses = queue.Queue()
        command = [str(args.wilor_python), '-u', str(Path(__file__).with_name('model_worker.py')),
             '--directory', str(Path(args.model_dir) / 'wilor'),
             '--device', args.wilor_device, '--limit', str(args.max_hands)]
        if optimized:
            command += ['--optimized', '--confidence', str(args.wilor_confidence), '--precision', args.wilor_precision]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        def read():
            try:
                for line in self.process.stdout:
                    if line.startswith(b'MAGICPOINTER_JSON '):
                        self.responses.put(json.loads(line[len(b'MAGICPOINTER_JSON '):]))
            finally:
                self.responses.put({'error': 'WiLoR worker exited; see terminal output and setup guide'})
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            self.info = self.receive()['info']
        except BaseException:
            self.close()
            raise

    def receive(self):
        try:
            response = self.responses.get(timeout=self.timeout)
        except queue.Empty as error:
            raise ValueError('WiLoR timed out; check its environment/downloads or increase --worker-timeout') from error
        if 'error' in response:
            raise ValueError(response['error'])
        return response

    def detect(self, image, timestamp, view):
        import numpy as np
        data = np.ascontiguousarray(image, dtype=np.uint8)
        request = {'shape': data.shape, 'timestamp': timestamp, 'view': view}
        self.process.stdin.write(json.dumps(request).encode() + b'\n')
        self.process.stdin.write(data.tobytes())
        self.process.stdin.flush()
        response = self.receive()
        self.last_inference_ms = response['inference_ms']
        return response['hands']

    def close(self):
        if self.process.poll() is None:
            # Closing stdin asks the worker to exit; kill handles stuck CUDA/downloads.
            try:
                self.process.stdin.close()
                self.process.wait(timeout=2)
            except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            if stream and not stream.closed:
                stream.close()
        self.reader.join(timeout=2)

    def detect_batch(self, frames, owners):
        import numpy as np
        arrays = [np.ascontiguousarray(frame.image, dtype=np.uint8) for frame in frames]
        request = {'frames': [{'shape': array.shape, 'timestamp': frame.grabbed_at}
                              for frame, array in zip(frames, arrays)], 'owners': owners}
        self.process.stdin.write(json.dumps(request).encode()+b'\n')
        for array in arrays:
            self.process.stdin.write(memoryview(array).cast('B'))
        self.process.stdin.flush()
        return self.receive()
