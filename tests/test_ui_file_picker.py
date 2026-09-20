import asyncio
from pathlib import Path
from types import SimpleNamespace

from rpa_control_center.ui import ControlCenterUI


class FakePage:
    def __init__(self):
        self.updated = 0

    def update(self):
        self.updated += 1


class FakeFilePicker:
    def __init__(self, *, files=None, directory=None, saved=None, error=None):
        self.files = files or []
        self.directory = directory
        self.saved = saved
        self.error = error

    async def pick_files(self, **_kwargs):
        if self.error:
            raise self.error
        return self.files

    async def get_directory_path(self, **_kwargs):
        if self.error:
            raise self.error
        return self.directory

    async def save_file(self, **_kwargs):
        if self.error:
            raise self.error
        return self.saved


def make_ui(picker):
    ui = ControlCenterUI.__new__(ControlCenterUI)
    ui.page = FakePage()
    ui.file_picker = picker
    ui.cwd = SimpleNamespace(value="")
    ui.set_status = lambda message, error=False: setattr(ui, "last_status", (message, error))
    return ui


def test_registration_file_picker_uses_flet_service(tmp_path):
    selected = tmp_path / "robot.py"
    ui = make_ui(FakeFilePicker(files=[SimpleNamespace(path=str(selected))]))
    field = SimpleNamespace(value="")

    asyncio.run(ui._file_picker_for(field, auto_update_cwd=True)())

    assert field.value == str(selected)
    assert ui.cwd.value == str(tmp_path)
    assert ui.page.updated == 1


def test_registration_directory_picker_uses_flet_service(tmp_path):
    ui = make_ui(FakeFilePicker(directory=str(tmp_path)))
    field = SimpleNamespace(value="")

    asyncio.run(ui._file_picker_for(field, pick_directory=True)())

    assert field.value == str(tmp_path)


def test_maintenance_open_and_save_pickers(tmp_path):
    source = tmp_path / "robots.json"
    destination_without_suffix = tmp_path / "backup"
    ui = make_ui(
        FakeFilePicker(
            files=[SimpleNamespace(path=str(source))],
            saved=str(destination_without_suffix),
        )
    )

    opened = asyncio.run(ui._pick_open_file("Importar", [("JSON", "*.json")]))
    saved = asyncio.run(ui._pick_save_file("Exportar", "robots.json", ".json", [("JSON", "*.json")]))

    assert opened == source
    assert saved == destination_without_suffix.with_suffix(".json")


def test_picker_error_stays_inside_ui():
    ui = make_ui(FakeFilePicker(error=RuntimeError("dialog failure")))
    field = SimpleNamespace(value="")

    asyncio.run(ui._file_picker_for(field)())

    assert ui.last_status == ("Erro ao abrir seletor: dialog failure", True)
    assert ui.page.updated == 1
