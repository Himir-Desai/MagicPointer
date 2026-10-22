"""Startup stays usable even when vision libraries or camera devices are absent."""
import argparse
import math
import os
from pathlib import Path
import sys

from . import __version__


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def camera(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("camera index cannot be negative")
    return number


def hand_limit(value):
    number = int(value)
    if not 1 <= number <= 8:
        raise argparse.ArgumentTypeError("hands per camera must be between 1 and 8")
    return number


def pixels(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("capture dimension must be positive")
    return number


def confidence(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 1:
        raise argparse.ArgumentTypeError('confidence must be greater than 0 and at most 1')
    return number


def wilor_options(cmd):
    cmd.add_argument('--model-dir', type=Path, default=Path('models/comparison'))
    cmd.add_argument('--wilor-python', type=Path, default=Path('.venv-wilor/Scripts/python.exe' if os.name == 'nt' else '.venv-wilor/bin/python'))
    cmd.add_argument('--wilor-device', choices=('cpu', 'cuda'), default='cuda')
    cmd.add_argument('--worker-timeout', type=positive, default=600., help='WiLoR startup/inference timeout in seconds')


def capture_options(cmd):
    cmd.add_argument("--camera-backend", choices=("default", "msmf"), default="default",
                     help="default uses Media Foundation on Windows and the system backend elsewhere; msmf requires Windows")
    cmd.add_argument("--capture-width", type=pixels, default=1920, help="requested camera width in pixels (default: 1920)")
    cmd.add_argument("--capture-height", type=pixels, default=1080, help="requested camera height in pixels (default: 1080)")


def parser():
    root = argparse.ArgumentParser(description="MagicPointer: Windows-first stereo hand pointer")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command")
    for name in ("run", "calibrate"):
        cmd = commands.add_parser(name)
        capture_options(cmd)
        cmd.add_argument("--left", type=camera, default=0, help="primary camera index (default: 0)")
        cmd.add_argument("--right", type=camera, required=name == "calibrate", help="secondary camera index")
        cmd.add_argument("--fps", choices=("auto", "30", "60"), default="30" if name == "run" else "auto", help="requested capture rate; driver may negotiate a lower rate")
        cmd.add_argument("--calibration", type=Path, default=Path("calibration.json"))
        if name == "run":
            cmd.add_argument("--debug", action="store_true", help="one-/two-camera debug with automatic data recording; stereo preview works before calibration; no OS input")
            position = cmd.add_mutually_exclusive_group()
            position.add_argument("--uncalibrated", action="store_true", default=True, help="use approximate image-space control without calibration (default)")
            position.add_argument("--calibrated", dest="uncalibrated", action="store_false", help="use calibration.json and wall-marker verification for metric stereo control")
            cmd.add_argument("--output", type=Path, default=Path("diagnostics"), help="debug-session recording directory (default: diagnostics)")
            cmd.add_argument("--model", type=Path, default=Path("models/hand_landmarker.task"))
            cmd.add_argument("--workspace-width", type=positive, default=.40, help="local interaction plane width, metres (default: 0.40)")
            cmd.add_argument("--workspace-height", type=positive, default=.25, help="local interaction plane height, metres (default: 0.25)")
            cmd.add_argument("--mirror-x", action=argparse.BooleanOptionalAction, default=True)
            cmd.add_argument("--mute", action="store_true")
            cmd.add_argument("--max-hands", type=hand_limit, default=2, help="maximum hands detected per camera (1-8, default: 2)")
            cmd.add_argument('--hand-backend', choices=('mediapipe', 'wilor'), default='wilor',
                             help='hand recognizer (default: optimized WiLoR; MediaPipe remains optional)')
            cmd.add_argument('--left-click', choices=('thumb-chord', 'thumb-tap'), default='thumb-chord',
                             help='left-click method; thumb-tap is an experimental WiLoR tap on curled fingers')
            wilor_options(cmd)
            cmd.add_argument('--wilor-confidence', type=confidence, default=.50,
                             help='WiLoR detector threshold (default 0.50; try 0.45 for recall)')
            cmd.add_argument('--wilor-precision', choices=('auto', 'fp16', 'fp32'), default='auto',
                             help='WiLoR: auto uses FP16 on CUDA and FP32 on CPU')
        else:
            cmd.add_argument("--square-mm", type=positive, default=25., help="measured checkerboard square edge in mm")
            cmd.add_argument("--marker-size", type=positive, required=True, help="measured wall marker black square edge in metres")
            cmd.add_argument("--marker-spacing", type=positive, required=True, help="measured wall marker center-to-center distance in metres")
    cmd = commands.add_parser("targets", help="generate printable checkerboard + ArUco markers 0/1")
    cmd.add_argument("--output", type=Path, default=Path("targets"))
    cmd.add_argument("--square-mm", type=positive, default=25.)
    cmd.add_argument("--marker-mm", type=positive, default=80.,
                     help="black square edge in mm; default 80 fits both markers on one A4 sheet")
    cmd = commands.add_parser("download-model", help="download checksum-verified official hand model")
    cmd.add_argument("--output", type=Path, default=Path("models/hand_landmarker.task"))
    cmd = commands.add_parser("cameras", help="probe camera indices and report negotiated settings")
    capture_options(cmd)
    cmd.add_argument("--limit", type=camera, default=4)
    cmd.add_argument("--fps", choices=("auto", "30", "60"), default="auto")
    cmd = commands.add_parser("collect", help="guided one-camera gesture diagnostics; no desktop input or video recording")
    cmd.add_argument("--camera", type=camera, default=0)
    cmd.add_argument("--fps", choices=("auto", "30", "60"), default="30")
    cmd.add_argument("--model", type=Path, default=Path("models/hand_landmarker.task"))
    cmd.add_argument("--output", type=Path, default=Path("diagnostics"))
    cmd.add_argument("--seconds", type=positive, default=3., help="recording length for each labelled pose (default: 3 seconds)")
    cmd = commands.add_parser("tilt", help="one-camera finger-tilt experiment with simulated scrolling only")
    cmd.add_argument("--camera", type=camera, default=0)
    cmd.add_argument("--fps", choices=("auto", "30", "60"), default="30")
    cmd.add_argument("--model", type=Path, default=Path("models/hand_landmarker.task"))
    cmd.add_argument("--output", type=Path, default=Path("diagnostics"))
    cmd.add_argument("--dead-zone", type=positive, default=5., help="neutral dead zone in degrees (default: 5)")
    cmd = commands.add_parser("wrist-tilt", help="whole-hand tilt toward screen; simulated scrolling only")
    cmd.add_argument("--camera", type=camera, default=0)
    cmd.add_argument("--fps", choices=("auto", "30", "60"), default="30")
    cmd.add_argument("--model", type=Path, default=Path("models/hand_landmarker.task"))
    cmd.add_argument("--output", type=Path, default=Path("diagnostics"))
    cmd.add_argument("--dead-zone", type=positive, default=10., help="neutral half-width in degrees (default: +/-10)")
    cmd.add_argument("--full-speed-angle", type=positive, default=30., help="angle from neutral for full speed (default: 30 degrees)")
    cmd = commands.add_parser("compare-models", help="debug-only switchable MediaPipe/RTMPose/WiLoR comparison; no OS input")
    capture_options(cmd)
    cmd.add_argument('--left', type=camera, default=0)
    cmd.add_argument('--right', type=camera)
    cmd.add_argument('--fps', choices=('auto', '30', '60'), default='30')
    cmd.add_argument('--models', nargs='+', choices=('mediapipe', 'rtmpose', 'wilor'),
                     default=['mediapipe', 'rtmpose', 'wilor'])
    cmd.add_argument('--model', type=Path, default=Path('models/hand_landmarker.task'))
    wilor_options(cmd)
    cmd.add_argument('--max-hands', type=hand_limit, default=4)
    cmd.add_argument('--output', type=Path, default=Path('diagnostics'))
    cmd.add_argument('--prepare', action='store_true', help='download selected models and check blank-frame inference without opening cameras')
    return root


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    if args.command is None:
        root.print_help()
        return 0
    try:
        if args.command in ("run", "calibrate", "compare-models") and args.left == args.right:
            raise ValueError("Select different left and right camera indices")
        if args.command == "run":
            from .app import run
            return run(args)
        if args.command == 'compare-models':
            from .comparison_app import run
            return run(args)
        if args.command == "collect":
            from .diagnostics import run
            return run(args)
        if args.command in ("tilt", "wrist-tilt"):
            from .tilt_app import run
            return run(args)
        if args.command == "calibrate":
            from .calibration import run
            return run(args)
        if args.command == "targets":
            from .calibration import targets
            targets(args.output, args.square_mm, args.marker_mm)
            print(f"Targets saved in {args.output}. Print at 100%; measure the printed sizes.")
        elif args.command == "download-model":
            from .model import download
            print(f"Model saved to {download(args.output)}")
        elif args.command == "cameras":
            from .cameras import Cameras
            found = 0
            for index in range(args.limit):
                try:
                    with Cameras(index, fps=args.fps, backend=args.camera_backend,
                                 width=args.capture_width, height=args.capture_height) as devices:
                        print(devices.info[0])
                        found += 1
                except ValueError as error:
                    print(str(error))
            return 0 if found else 1
        return 0
    except KeyboardInterrupt:
        print("\nStopped")
        return 0
    except ImportError as error:
        print(f"Dependency unavailable: {error}. Install with: python -m pip install -e .", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"MagicPointer: {error}", file=sys.stderr)
        return 1
