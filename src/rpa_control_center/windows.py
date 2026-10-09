"""Windows primitives for one local installation and owned process trees."""

import os
import ctypes
from ctypes import wintypes
import json
import msvcrt
import subprocess
import time
import threading
import uuid

import win32api
import win32event
import win32job
import win32process
import win32con
import win32gui


class OwnedWindowActivation:
    """Bounded startup activation of job-owned windows on a separate thread."""

    def __init__(self, process, trace_path=None):
        self.process = process
        self.trace_path = trace_path
        self.stopped = threading.Event()
        self.deadline = time.monotonic() + 120
        self.attempts = {}
        self.thread = threading.Thread(target=self._watch, daemon=True)

    def start(self):
        try:
            self.thread.start()
        except RuntimeError:
            self._record({"activation_error": "ThreadStartFailed"})

    def close(self):
        self.stopped.set()

    def _record(self, values):
        if self.trace_path is not None:
            try:
                with self.trace_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"time": time.time(), **values}) + "\n")
            except OSError:
                pass

    def _watch(self):
        while not self.stopped.wait(0.5) and time.monotonic() < self.deadline:
            try:
                pids = set(win32job.QueryInformationJobObject(
                    self.process.job, win32job.JobObjectBasicProcessIdList
                ))
                candidates = []

                def collect(hwnd, _):
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        if pid not in pids or not win32gui.IsWindowVisible(hwnd):
                            return
                        if not win32gui.IsWindowEnabled(hwnd):
                            return
                        extended = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                        if extended & (win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW):
                            return
                        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                        if right <= left or bottom <= top:
                            return
                        candidates.append((hwnd, pid))
                    except win32gui.error:
                        pass  # Windows can close while being enumerated.

                win32gui.EnumWindows(collect, None)
                for hwnd, pid in candidates:
                    key = (hwnd, pid)
                    count = self.attempts.get(key, 0)
                    if count >= 3 or self.stopped.is_set():
                        continue
                    self.attempts[key] = count + 1
                    if self._activate(hwnd, pid):
                        self.attempts[key] = 3
            except Exception as error:
                self._record({"activation_error": type(error).__name__})

    def _activate(self, hwnd, pid):
        attached = []
        try:
            # Recheck ownership before touching a window from the snapshot.
            pids = win32job.QueryInformationJobObject(
                self.process.job, win32job.JobObjectBasicProcessIdList
            )
            target_thread, actual_pid = win32process.GetWindowThreadProcessId(hwnd)
            if actual_pid != pid or pid not in pids or self.stopped.is_set():
                return False
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindowAsync.restype = wintypes.BOOL
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
            user32.AllowSetForegroundWindow.restype = wintypes.BOOL
            if win32gui.IsIconic(hwnd):
                user32.ShowWindowAsync(hwnd, win32con.SW_RESTORE)
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            current = win32api.GetCurrentThreadId()
            win32gui.PeekMessage(None, 0, 0, win32con.PM_NOREMOVE)
            foreground = win32gui.GetForegroundWindow()
            foreground_thread = (
                win32process.GetWindowThreadProcessId(foreground)[0] if foreground else 0
            )
            try:
                for other in dict.fromkeys((foreground_thread, target_thread)):
                    if other and other != current:
                        win32process.AttachThreadInput(current, other, True)
                        attached.append(other)
                win32gui.SetWindowPos(
                    hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_ASYNCWINDOWPOS,
                )
                requested = bool(user32.SetForegroundWindow(hwnd))
                granted = bool(user32.AllowSetForegroundWindow(pid))
                focused = win32gui.GetForegroundWindow() == hwnd
                self._record({
                    "activation_hwnd": hwnd, "activation_pid": pid,
                    "requested": requested, "focus_confirmed": focused,
                    "foreground_permission_granted": granted,
                })
                return focused
            finally:
                for other in reversed(attached):
                    try:
                        win32process.AttachThreadInput(current, other, False)
                    except win32process.error:
                        pass
        except Exception as error:
            self._record({"activation_hwnd": hwnd, "activation_error": type(error).__name__})
            return False


class DesktopTrace:
    """Opt-in window state capture; never changes focus or robot behavior."""

    def __init__(self, process, path):
        self.process = process
        self.path = path
        self.next_sample = 0.0
        self.previous = None

    def sample(self, *, force=False):
        now = time.monotonic()
        if not force and now < self.next_sample:
            return
        self.next_sample = now + 1.0
        try:
            pids = set(win32job.QueryInformationJobObject(
                self.process.job, win32job.JobObjectBasicProcessIdList
            ))
            windows = []

            def collect(hwnd, _):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid in pids:
                        windows.append({
                            "hwnd": hwnd, "pid": pid,
                            "class": win32gui.GetClassName(hwnd),
                            "visible": bool(win32gui.IsWindowVisible(hwnd)),
                            "minimized": bool(win32gui.IsIconic(hwnd)),
                            "maximized": win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED,
                        })
                except win32gui.error:
                    pass  # A window can disappear during enumeration.

            win32gui.EnumWindows(collect, None)
            foreground = win32gui.GetForegroundWindow()
            foreground_pid = (
                win32process.GetWindowThreadProcessId(foreground)[1]
                if foreground else None
            )
            startup = win32process.GetStartupInfo()
            state = {
                "worker_pid": os.getpid(), "root_pid": self.process.pid,
                "scheduler": os.environ.get("RCC_SCHEDULER_MODE") == "1",
                "worker_startup_flags": startup.dwFlags,
                "worker_show_window": startup.wShowWindow,
                "foreground_hwnd": foreground, "foreground_pid": foreground_pid,
                "foreground_owned": foreground_pid in pids,
                "owned_pids": sorted(pids),
                "windows": sorted(windows, key=lambda window: window["hwnd"]),
            }
            if force or state != self.previous:
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"time": time.time(), **state}) + "\n")
                self.previous = state
        except Exception as error:
            # Even a missing runtime API must not interrupt the robot.
            try:
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({
                        "time": time.time(), "diagnostic_error": type(error).__name__,
                    }) + "\n")
            except OSError:
                pass


class InstallationBusy(RuntimeError):
    """Another worker already owns the installation mutex."""


class InstallationLock:
    """Cross-session mutex. All entry points must use the same installation ID."""

    def __init__(self, installation_id: str):
        self.handle = win32event.CreateMutex(None, False, "Global\\RpaControlCenter-" + installation_id)
        self.owned = False

    def __enter__(self):
        result = win32event.WaitForSingleObject(self.handle, 0)
        if result not in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED):
            self.handle.Close()
            raise InstallationBusy("Another engine owns this installation")
        self.owned = True
        return self

    def __exit__(self, *_):
        if self.owned:
            win32event.ReleaseMutex(self.handle)
        self.handle.Close()


class ProcessTree:
    """Create suspended, assign to job, then resume: children cannot race assignment."""

    def __init__(
        self,
        command: list[str],
        cwd: str,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        environment: dict[str, str] | None = None,
    ):
        self.job = win32job.CreateJobObject(None, "RpaRun-" + str(uuid.uuid4()))
        self.process = None
        self.streams = []
        try:
            limits = win32job.QueryInformationJobObject(self.job, win32job.JobObjectExtendedLimitInformation)
            limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            win32job.SetInformationJobObject(self.job, win32job.JobObjectExtendedLimitInformation, limits)
            startup = win32process.STARTUPINFO()
            inherit_handles = False
            if stdout_path or stderr_path:
                stdout = open(stdout_path or os.devnull, "ab", buffering=0)
                stderr = open(stderr_path or os.devnull, "ab", buffering=0)
                stdin = open(os.devnull, "rb", buffering=0)
                self.streams.extend((stdout, stderr, stdin))
                for stream in self.streams:
                    os.set_handle_inheritable(msvcrt.get_osfhandle(stream.fileno()), True)
                startup.dwFlags |= win32con.STARTF_USESTDHANDLES
                startup.hStdOutput = msvcrt.get_osfhandle(stdout.fileno())
                startup.hStdError = msvcrt.get_osfhandle(stderr.fileno())
                startup.hStdInput = msvcrt.get_osfhandle(stdin.fileno())
                inherit_handles = True
            process, thread, self.pid, _ = win32process.CreateProcess(
                command[0], subprocess.list2cmdline(command), None, None, inherit_handles,
                win32process.CREATE_SUSPENDED | win32process.CREATE_NO_WINDOW,
                environment, cwd, startup,
            )
            self.process = process
            try:
                win32job.AssignProcessToJobObject(self.job, process)
                win32process.ResumeThread(thread)
            except BaseException:
                win32api.TerminateProcess(process, 1)
                raise
            finally:
                thread.Close()
        except BaseException:
            self.close()
            raise

    def stop(self):
        win32job.TerminateJobObject(self.job, 1)

    def active_count(self):
        return win32job.QueryInformationJobObject(self.job, win32job.JobObjectBasicAccountingInformation)["ActiveProcesses"]

    def wait(self, timeout_seconds: float) -> bool:
        milliseconds = max(0, int(timeout_seconds * 1000))
        return win32event.WaitForSingleObject(self.process, milliseconds) == win32event.WAIT_OBJECT_0

    def exit_code(self) -> int:
        return win32process.GetExitCodeProcess(self.process)

    def close(self):
        if self.process is not None:
            self.process.Close()
            self.process = None
        for stream in self.streams:
            stream.close()
        self.streams.clear()
        if self.job is not None:
            self.job.Close()
            self.job = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
