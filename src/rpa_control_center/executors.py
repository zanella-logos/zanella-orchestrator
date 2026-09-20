"""Command builders for supported local process types."""

from pathlib import Path


EXECUTOR_TYPES = ("python", "powershell", "batch", "node", "java", "executable")


def build_command(executor_type: str, launcher: str, target: str, arguments: list[str]) -> list[str]:
    if executor_type == "python":
        return [launcher, "-u", target, *arguments]
    if executor_type == "powershell":
        return [
            launcher, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", target, *arguments,
        ]
    if executor_type == "batch":
        return [launcher, "/D", "/S", "/C", target, *arguments]
    if executor_type == "node":
        return [launcher, target, *arguments]
    if executor_type == "java":
        return [launcher, "-jar", target, *arguments]
    if executor_type == "executable":
        return [target, *arguments]
    raise ValueError(f"Unsupported executor type: {executor_type}")


def validate_command_paths(executor_type: str, launcher: str, target: str, cwd: str) -> str | None:
    if executor_type not in EXECUTOR_TYPES:
        return f"Unsupported executor type: {executor_type}"
    if not Path(cwd).is_dir():
        return f"Invalid working directory: {cwd}"
    if not Path(target).is_file():
        return f"Invalid target: {target}"
    if executor_type != "executable" and not Path(launcher).is_file():
        return f"Invalid launcher: {launcher}"
    return None
