"""WiLoR subprocess: raw BGR bytes in RAM, JSON landmarks out; no image files."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
import time

# Executed by absolute script path in a separate venv, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def reply(value):
    from magicpointer.debug_log import json_value
    print('MAGICPOINTER_JSON ' + json.dumps(json_value(value), allow_nan=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--device', choices=('cpu', 'cuda'), required=True)
    parser.add_argument('--limit', type=int, required=True)
    parser.add_argument('--optimized', action='store_true')
    parser.add_argument('--confidence', type=float, default=.50)
    parser.add_argument('--precision', choices=('auto', 'fp16', 'fp32'), default='auto')
    args = parser.parse_args()
    # Dependencies are installed explicitly by the guide, never by an upstream
    # auto-installer running an unqualified pip in a different environment.
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    model = None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import numpy as np
            from magicpointer.comparison_models import WiLoRModel
            if args.optimized:
                from magicpointer.wilor_batch import BatchedWiLoR
                model = BatchedWiLoR(args.directory, args.device, args.limit, args.confidence, args.precision)
            else:
                model = WiLoRModel(args.directory, args.device, args.limit)
        reply({'ready': True, 'info': model.info})
        while True:
            header = sys.stdin.buffer.readline()
            if not header:
                break
            request = json.loads(header)
            if args.optimized:
                specifications = request['frames']
                if not 1 <= len(specifications) <= 2:
                    raise ValueError('WiLoR debug expects one or two frames')
                images = [read_image(specification, np) for specification in specifications]
                started = time.perf_counter()
                with contextlib.redirect_stdout(sys.stderr):
                    result = model.detect_batch(images, [frame['timestamp'] for frame in specifications], request['owners'])
                result['inference_ms'] = (time.perf_counter()-started)*1000
                reply(result)
                continue
            image = read_image(request, np).copy()  # Keep the comparison baseline's original writable input.
            started = time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                hands = model.detect(image, request['timestamp'], request['view'])
            reply({'hands': hands, 'inference_ms': (time.perf_counter()-started)*1000})
    except Exception as error:
        reply({'error': f'{type(error).__name__}: {error}'})
        return 1
    finally:
        if model:
            model.close()
    return 0


def read_image(request, np):
    shape = request['shape']
    size = int(np.prod(shape))
    if len(shape) != 3 or shape[2] != 3 or size <= 0 or size > 128*1024*1024:
        raise ValueError('Invalid worker frame shape')
    data = sys.stdin.buffer.read(size)
    if len(data) != size:
        raise ValueError('Incomplete worker frame')
    return np.frombuffer(data, dtype=np.uint8).reshape(shape)


if __name__ == '__main__':
    raise SystemExit(main())
