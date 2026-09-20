"""Demo deterministico: abre uma pagina local no Chrome e salva uma evidencia."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image
import win32api
import win32con
import win32gui


def find_window(title: str, timeout: float = 10) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = []

        def collect(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
                matches.append(hwnd)

        win32gui.EnumWindows(collect, None)
        if matches:
            return matches[0]
        time.sleep(0.25)
    raise RuntimeError("A janela esperada do Chrome nao apareceu")


def position_window(hwnd: int) -> None:
    width, height = 1200, 800
    screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    left = max(0, (screen_width - width) // 2)
    top = max(0, (screen_height - height) // 2)
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, left, top, width, height, win32con.SWP_SHOWWINDOW)
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_NOTOPMOST, left, top, width, height, win32con.SWP_SHOWWINDOW
    )
    time.sleep(1)


def capture_page(chrome: Path, page: Path, profile: Path, destination: Path) -> tuple[int, int]:
    completed = subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--user-data-dir={profile}",
            "--window-size=1200,800",
            f"--screenshot={destination}",
            page.as_uri(),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0 or not destination.is_file():
        detail = completed.stderr.strip() or f"codigo {completed.returncode}"
        raise RuntimeError(f"Chrome nao gerou a evidencia: {detail}")
    with Image.open(destination) as image:
        width, height = image.size
        extrema = image.convert("RGB").getextrema()
    if (width, height) != (1200, 800) or all(channel[1] == 0 for channel in extrema):
        raise RuntimeError("Chrome gerou uma evidencia invalida")
    return width, height


def find_chrome() -> Path:
    candidates = [
        shutil.which("chrome"),
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("Google Chrome nao foi encontrado")


def desktop_path() -> Path:
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        return desktop
    onedrive = os.environ.get("OneDrive")
    if onedrive and (Path(onedrive) / "Desktop").is_dir():
        return Path(onedrive) / "Desktop"
    raise FileNotFoundError("Area de Trabalho nao foi encontrada")


def write_result(status: str, summary: str) -> None:
    destination = Path(os.environ["RCC_RESULT_PATH"])
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": os.environ["RCC_RUN_ID"],
                "status": status,
                "summary": summary,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, destination)


def main() -> int:
    run_id = os.environ["RCC_RUN_ID"]
    workspace = Path(tempfile.mkdtemp(prefix="rcc-browser-demo-"))
    profile = workspace / "chrome-profile"
    page = workspace / "portal-demo.html"
    evidence = desktop_path() / f"RCC-evidencia-{run_id[:8]}.png"
    window_title = f"RCC Demo {run_id[:8]}"
    browser = None
    try:
        page.write_text(
            """<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>
<title>__WINDOW_TITLE__</title><style>
body{font-family:Segoe UI,sans-serif;background:#f4f7fb;margin:0;color:#172033}
header{background:#1455a0;color:white;padding:28px 48px;font-size:28px;font-weight:700}
main{max-width:900px;margin:55px auto;background:white;padding:45px;border-radius:16px;
box-shadow:0 10px 30px #b8c4d455} .ok{color:#157347;font-weight:700}</style></head>
<body><header>Zanella Orchestrator</header><main><h1>Portal local de validacao</h1>
<p>O Chrome foi iniciado como processo filho do robo.</p>
<p class='ok'>Pagina carregada para captura de evidencia.</p></main></body></html>""".replace(
                "__WINDOW_TITLE__", window_title
            ),
            encoding="utf-8",
        )
        chrome = find_chrome()
        command = [
            str(chrome),
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--disable-default-apps",
            f"--app={page.as_uri()}",
        ]
        browser = subprocess.Popen(command)
        print(f"Chrome iniciado com PID {browser.pid}", flush=True)
        hwnd = find_window(window_title)
        position_window(hwnd)
        width, height = capture_page(chrome, page, workspace / "capture-profile", evidence)
        size = evidence.stat().st_size
        if size < 10_000:
            raise RuntimeError("A evidencia gerada e pequena demais")
        summary = f"Janela do Chrome capturada em {evidence} ({width}x{height}; {size} bytes)"
        print(summary, flush=True)
        write_result("success", summary)
        return 0
    except Exception as error:
        print(f"Falha na demonstracao: {error}", file=sys.stderr, flush=True)
        write_result("technical_error", str(error))
        return 1
    finally:
        if browser and browser.poll() is None:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
