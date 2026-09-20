from PIL import Image

from demo import browser_evidence_robot as demo


def test_position_window_uses_win32api_metrics(tmp_path, monkeypatch):
    positions = []
    monkeypatch.setattr(demo.win32api, "GetSystemMetrics", lambda metric: 2560 if metric == 0 else 1440)
    monkeypatch.setattr(demo.win32gui, "ShowWindow", lambda *_: None)
    monkeypatch.setattr(demo.win32gui, "SetWindowPos", lambda *args: positions.append(args))
    monkeypatch.setattr(demo.time, "sleep", lambda _: None)
    demo.position_window(123)
    assert positions[0][2:6] == (680, 320, 1200, 800)


def test_capture_page_uses_chrome_native_screenshot(tmp_path, monkeypatch):
    destination = tmp_path / "evidence.png"
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        Image.new("RGB", (1200, 800), "white").save(destination)
        return type("Completed", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(demo.subprocess, "run", run)
    size = demo.capture_page(
        tmp_path / "chrome.exe", tmp_path / "page.html", tmp_path / "profile", destination
    )
    assert size == (1200, 800)
    assert "--headless=new" in calls[0][0]
    assert f"--screenshot={destination}" in calls[0][0]
