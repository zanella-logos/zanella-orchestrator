"""Windows primitives for one local installation and owned process trees."""

import os
import msvcrt
import subprocess
import uuid

import win32api
import win32event
import win32job
import win32process
import win32con


class InstallationLock:
    """Cross-session mutex. All entry points must use the same installation ID."""

    def __init__(self, installation_id: str):
        self.handle = win32event.CreateMutex(None, False, "Global\\RpaControlCenter-" + installation_id)
        self.owned = False

    def __enter__(self):
        result = win32event.WaitForSingleObject(self.handle, 0)
        if result not in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED):
            self.handle.Close()
            raise RuntimeError("Another engine owns this installation")
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
