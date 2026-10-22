"""Native primary-display input. Imported only for desktop control."""
import ctypes
import platform


class Desktop:
    def __init__(self):
        self.system = platform.system()
        if self.system == "Windows":
            from ctypes import wintypes
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            # Work in physical coordinates, including displays with >100% scaling.
            try:
                ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
            except (OSError, AttributeError):
                self.user32.SetProcessDPIAware()
            self.width, self.height = self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1)
            self.offset = (0, 0)

            class MouseInput(ctypes.Structure):
                _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                            ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                            ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

            class KeyboardInput(ctypes.Structure):
                _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                            ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                            ("dwExtraInfo", ctypes.c_size_t)]

            class HardwareInput(ctypes.Structure):
                _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

            class InputUnion(ctypes.Union):
                _fields_ = [("mi", MouseInput), ("ki", KeyboardInput), ("hi", HardwareInput)]

            class Input(ctypes.Structure):
                _anonymous_ = ("u",)
                _fields_ = [("type", wintypes.DWORD), ("u", InputUnion)]

            self.Input, self.MouseInput = Input, MouseInput
            self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int)
            self.user32.SendInput.restype = wintypes.UINT
        elif self.system == "Darwin":
            try:
                import Quartz
            except ImportError as error:
                raise ValueError("macOS control needs: pip install -e '.[macos]'") from error
            self.quartz = Quartz
            if not Quartz.CGPreflightPostEventAccess():
                raise ValueError("Enable Accessibility access for your terminal/Python in macOS System Settings, then restart")
            bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
            self.width, self.height = bounds.size.width, bounds.size.height
            self.offset = (bounds.origin.x, bounds.origin.y)
        else:
            raise ValueError("Desktop control supports Windows and optional macOS. Use --debug for camera preview.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Cannot determine primary display size")

    def move(self, point):
        x = self.offset[0] + round(point[0] * (self.width - 1))
        y = self.offset[1] + round(point[1] * (self.height - 1))
        if self.system == "Windows":
            if not self.user32.SetCursorPos(int(x), int(y)):
                raise OSError("Windows could not move the cursor")
        else:
            q = self.quartz
            q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateMouseEvent(None, q.kCGEventMouseMoved, (x, y), q.kCGMouseButtonLeft))

    def _send(self, flags, data=0):
        item = self.Input(type=0, mi=self.MouseInput(0, 0, data & 0xffffffff, flags, 0, 0))
        if self.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(item)) != 1:
            raise OSError("Windows rejected pointer input (check app privileges)")

    def click(self, button):
        if self.system == "Windows":
            down, up = (0x0002, 0x0004) if button == "left" else (0x0008, 0x0010)
            try:
                self._send(down)
            finally:
                self._send(up)
        else:
            q = self.quartz
            pos = q.CGEventGetLocation(q.CGEventCreate(None))
            down, up, code = ((q.kCGEventLeftMouseDown, q.kCGEventLeftMouseUp, q.kCGMouseButtonLeft)
                              if button == "left" else (q.kCGEventRightMouseDown, q.kCGEventRightMouseUp, q.kCGMouseButtonRight))
            try:
                q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateMouseEvent(None, down, pos, code))
            finally:
                q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateMouseEvent(None, up, pos, code))

    def scroll(self, lines):
        if self.system == "Windows":
            self._send(0x0800, int(lines) * 120)
        else:
            q = self.quartz
            q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateScrollWheelEvent(None, q.kCGScrollEventUnitLine, 1, int(lines)))
