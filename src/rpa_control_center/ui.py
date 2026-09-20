"""Flet desktop interface over the same services used by the CLI."""

import asyncio
from datetime import datetime
from pathlib import Path
import shutil
import sys

import flet as ft

from .database import application_data_dir, database_url, upgrade_database
from .engine import run_engine, run_engine_direct
from .executors import EXECUTOR_TYPES, validate_command_paths
from .maintenance import (
    backup_sqlite, export_robots, import_robots, purge_old_runs, restore_sqlite,
)
from .scheduler import (
    TASK_NAME, WEEKDAYS, add_schedule, install_windows_task, list_schedules,
    open_windows_task_scheduler, remove_schedule, remove_windows_task,
    set_schedule_active, weekday_mask, weekdays_from_mask, windows_task_installed,
)
from .service import (
    add_robot, cancel, enqueue, list_robots, list_runs, remove_robot, remove_run,
    set_robot_active, update_robot, clear_all_robots, clear_all_runs
)
from .store import make_engine


PROJECT_ROOT = Path.cwd().resolve()
BRAND_ICON = Path(__file__).resolve().parents[2] / "assets" / "icon.png"
LOG_LIMIT = 50_000
PRIMARY = "#2563EB"
ACCENT = "#06B6D4"
SUCCESS = "#10B981"
ERROR = "#E11D48"
WARNING = "#F59E0B"
DEEP_SLATE = "#0F172A"


def logs_root() -> Path:
    return application_data_dir() / "logs"

STATE_COLORS = {
    "queued": ("#E2E8F0", "#334155"),
    "starting": ("#DBEAFE", "#1D4ED8"),
    "running": ("#CFFAFE", "#0E7490"),
    "cancelling": ("#FEF3C7", "#92400E"),
    "completed": ("#D1FAE5", "#047857"),
    "failed": ("#FFE4E6", "#BE123C"),
    "timed_out": ("#FFE4E6", "#BE123C"),
    "cancelled": ("#CBD5E1", "#334155"),
    "interrupted": ("#FFE4E6", "#BE123C"),
    "success": ("#D1FAE5", "#047857"),
    "business_error": ("#FFEDD5", "#C2410C"),
    "partial": ("#FEF3C7", "#92400E"),
    "technical_error": ("#FFE4E6", "#BE123C"),
    "invalid_report": ("#FFE4E6", "#BE123C"),
    "not_reported": ("#CBD5E1", "#334155"),
}


def status_badge(value: str) -> ft.Container:
    background, foreground = STATE_COLORS.get(value, (ft.Colors.GREY_200, ft.Colors.GREY_900))
    return ft.Container(
        content=ft.Text(value, color=foreground, weight=ft.FontWeight.BOLD, size=12),
        bgcolor=background,
        padding=6,
        border_radius=10,
    )


def parse_arguments(value: str) -> list[str]:
    """One argument per line avoids shell quoting and preserves spaces."""
    return [line for line in (item.strip() for item in value.splitlines()) if line]


def default_launcher(executor_type: str) -> str:
    candidates = {
        "python": shutil.which("python"),
        "powershell": shutil.which("powershell") or "powershell.exe",
        "batch": shutil.which("cmd") or "cmd.exe",
        "node": shutil.which("node") or "node.exe",
        "java": shutil.which("java") or "java.exe",
    }
    val = candidates.get(executor_type) or sys.executable
    return str(Path(val).resolve())


def format_time(timestamp: float | None) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M:%S") if timestamp else "—"


def read_log(path: str | None) -> str:
    if not path or not Path(path).exists():
        return "Log ainda não disponível."
    content = Path(path).read_text(encoding="utf-8", errors="replace")
    return content[-LOG_LIMIT:] or "Log vazio."


class ControlCenterUI:
    def __init__(self, page: ft.Page, engine):
        self.page = page
        self.engine = engine
        self.status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, color=SUCCESS, size=16)
        self.status = ft.Text("Sistema pronto", color=ft.Colors.ON_SURFACE, size=12)
        self.status_indicator = ft.Container(
            content=ft.Row(controls=[self.status_icon, self.status], spacing=6),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=16,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        )
        self.progress = ft.ProgressRing(width=18, height=18, visible=False, color=ACCENT)
        self.run_button = ft.Button("Executar fila", icon=ft.Icons.PLAY_ARROW, on_click=self.execute_queue)
        self.theme_button = ft.IconButton(
            icon=ft.Icons.LIGHT_MODE,
            tooltip="Usar tema claro",
            icon_color=ACCENT,
            on_click=self.toggle_theme,
        )
        self.robots_table = ft.DataTable(
            columns=[], heading_row_color=ft.Colors.PRIMARY_CONTAINER, column_spacing=16,
            data_row_min_height=48, data_row_max_height=56,
        )
        self.runs_table = ft.DataTable(
            columns=[], heading_row_color=ft.Colors.PRIMARY_CONTAINER, column_spacing=20,
            data_row_min_height=48, data_row_max_height=56,
        )
        self.log_title = ft.Text("Selecione uma execução para ver os logs", weight=ft.FontWeight.BOLD)
        self.log_content = ft.Text("", selectable=True, font_family="JetBrains Mono", no_wrap=True)
        self.selected_run_id: str | None = None
        self.editing_robot_id: str | None = None

        self.name = ft.TextField(label="Nome", autofocus=True, expand=True)
        self.executor_type = ft.Dropdown(
            label="Tipo",
            value="python",
            options=[ft.DropdownOption(key=item, text=item) for item in EXECUTOR_TYPES],
            on_select=self.change_executor,
            width=180,
        )
        self.target = ft.TextField(label="Arquivo principal (script, exe, jar)", expand=True)
        self.launcher = ft.TextField(label="Runtime ou launcher", value=default_launcher("python"), expand=True)
        self.cwd = ft.TextField(label="Pasta de trabalho", value=str(PROJECT_ROOT), expand=True)
        self.arguments = ft.TextField(
            label="Argumentos — um por linha", multiline=True, min_lines=2, max_lines=5
        )
        self.timeout = ft.TextField(label="Timeout em segundos", value="3600", width=180)
        self.save_button = ft.Button("Cadastrar", icon=ft.Icons.ADD, on_click=self.save_robot)
        self.cancel_edit_button = ft.Button(
            "Cancelar edição", icon=ft.Icons.CLOSE, visible=False, on_click=self.cancel_edit
        )

        # Controles de Busca e Paginação
        self.history_page = 1
        self.history_limit = 25
        self.history_total = 0

        self.robot_search = ft.TextField(
            label="Buscar automação...",
            prefix_icon=ft.Icons.SEARCH,
            height=40,
            expand=True,
            on_change=self.on_filter_change,
        )

        self.run_search = ft.TextField(
            label="Buscar no histórico...",
            prefix_icon=ft.Icons.SEARCH,
            height=40,
            expand=True,
            on_change=self.on_filter_change,
        )
        self.run_state_filter = ft.Dropdown(
            label="Estado",
            options=[
                ft.DropdownOption(key="", text="Todos"),
                ft.DropdownOption(key="queued", text="Na Fila"),
                ft.DropdownOption(key="starting", text="Iniciando"),
                ft.DropdownOption(key="running", text="Rodando"),
                ft.DropdownOption(key="cancelling", text="Cancelando"),
                ft.DropdownOption(key="completed", text="Concluído"),
                ft.DropdownOption(key="failed", text="Falha"),
                ft.DropdownOption(key="cancelled", text="Cancelado"),
                ft.DropdownOption(key="timed_out", text="Timeout"),
            ],
            value="",
            height=40,
            width=130,
            on_select=self.on_filter_change,
        )
        self.run_business_filter = ft.Dropdown(
            label="Negócio",
            options=[
                ft.DropdownOption(key="", text="Todos"),
                ft.DropdownOption(key="success", text="Sucesso"),
                ft.DropdownOption(key="business_error", text="Erro de Negócio"),
                ft.DropdownOption(key="not_reported", text="Não Reportado"),
            ],
            value="",
            height=40,
            width=150,
            on_select=self.on_filter_change,
        )
        self.btn_clear_filters = ft.IconButton(
            icon=ft.Icons.FILTER_ALT_OFF,
            tooltip="Limpar Filtros",
            on_click=self.clear_filters,
        )

        self.btn_prev_page = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip="Página Anterior",
            on_click=self.prev_page,
        )
        self.btn_next_page = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip="Próxima Página",
            on_click=self.next_page,
        )
        self.text_page_info = ft.Text("Pág 1/1")
        self.retention_days = ft.TextField(label="Reter histórico por dias", value="60", width=210)
        self.schedule_robot = ft.Dropdown(label="Automação", options=[], width=280)
        self.schedule_frequency = ft.Dropdown(
            label="Frequência", value="daily", width=150,
            options=[
                ft.DropdownOption(key="daily", text="Diário"),
                ft.DropdownOption(key="weekly", text="Semanal"),
                ft.DropdownOption(key="custom", text="Personalizado"),
            ],
            on_select=self.change_schedule_frequency,
        )
        self.schedule_weekday = ft.Dropdown(
            label="Dia da semana", value="0", width=180, disabled=True,
            options=[ft.DropdownOption(key=str(index), text=name) for index, name in enumerate(WEEKDAYS)],
        )
        self.schedule_custom_days = ft.Row(
            controls=[
                ft.Checkbox(label=name[:3], value=False, data=index)
                for index, name in enumerate(WEEKDAYS)
            ],
            visible=False,
            spacing=8,
            wrap=True,
        )
        self.schedule_time = ft.TextField(label="Horário (HH:MM)", value="08:00", width=160)
        self.schedules_table = ft.DataTable(
            columns=[], heading_row_color=ft.Colors.PRIMARY_CONTAINER, column_spacing=20,
            data_row_min_height=48, data_row_max_height=56,
        )
        task_installed = windows_task_installed()
        self.task_status = ft.Text(self.windows_task_status(task_installed))
        self.install_task_button = ft.Button(
            "Instalar gatilho global", icon=ft.Icons.SCHEDULE,
            disabled=task_installed,
            tooltip="Necessário somente uma vez para todos os agendamentos",
            on_click=self.install_windows_task_click,
        )
        self.remove_task_button = ft.Button(
            "Remover gatilho global", icon=ft.Icons.DELETE_OUTLINE,
            disabled=not task_installed,
            on_click=self.confirm_remove_windows_task,
        )
        self.edit_task_button = ft.Button(
            "Abrir Agendador", icon=ft.Icons.EDIT_CALENDAR,
            disabled=not task_installed,
            tooltip=f"Abre o Agendador do Windows. Tarefa: {TASK_NAME}",
            on_click=self.open_windows_task_scheduler_click,
        )

    def build(self) -> ft.Control:
        header = ft.Row(
            controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Image(
                                    src=BRAND_ICON.read_bytes(),
                                    width=50,
                                    height=50,
                                    fit=ft.BoxFit.CONTAIN,
                                    semantics_label="Logo do Zanella Orchestrator",
                                    error_content=ft.Icon(ft.Icons.BROKEN_IMAGE, color=ERROR),
                                ),
                                width=66,
                                height=66,
                                bgcolor=ft.Colors.WHITE,
                                border_radius=14,
                                padding=8,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("Zanella Orchestrator", size=30, weight=ft.FontWeight.BOLD),
                                    ft.Text("Community Edition", size=12, color=ft.Colors.BLUE_GREY_500),
                                    ft.Text("Orquestrador local de automações e processos Windows"),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=14,
                        expand=True,
                    ),
                self.progress,
                self.status_indicator,
                self.theme_button,
                ft.Button("Atualizar", icon=ft.Icons.REFRESH, on_click=self.refresh_click),
                self.run_button,
            ]
        )
        registration = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Cadastrar automação", size=20, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Row(controls=[self.name, self.executor_type]),
                                    ft.Row(
                                        controls=[
                                            self.target,
                                            ft.IconButton(
                                                icon=ft.Icons.FOLDER_OPEN,
                                                tooltip="Selecionar arquivo principal",
                                                on_click=self._file_picker_for(self.target, fallback_field=self.cwd, auto_update_cwd=True),
                                            ),
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Row(
                                        controls=[
                                            self.launcher,
                                            ft.IconButton(
                                                icon=ft.Icons.FOLDER_OPEN,
                                                tooltip="Selecionar executável",
                                                on_click=self._file_picker_for(self.launcher, fallback_field=self.cwd),
                                            ),
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                expand=True,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            self.cwd,
                                            ft.IconButton(
                                                icon=ft.Icons.FOLDER_OPEN,
                                                tooltip="Selecionar pasta",
                                                on_click=self._file_picker_for(self.cwd, pick_directory=True),
                                            ),
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    self.arguments,
                                    ft.Row(controls=[
                                        self.timeout,
                                        self.cancel_edit_button,
                                        self.save_button,
                                    ]),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                expand=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                ]
            ),
            padding=20,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
        )
        robots_card = ft.Container(
            content=ft.Column(controls=[
                ft.Row(
                    controls=[
                        ft.Text("Automações cadastradas", size=20, weight=ft.FontWeight.BOLD),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_SWEEP,
                            tooltip="Remover todos os robôs",
                            icon_color=ft.Colors.RED_700,
                            on_click=self.confirm_clear_robots,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.robot_search,
                ft.Container(
                    content=ft.Row(
                        controls=[ft.Column(
                            controls=[self.robots_table],
                            scroll=ft.ScrollMode.ALWAYS,
                        )],
                        scroll=ft.ScrollMode.ALWAYS,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    height=400,
                ),
            ]),
            padding=18,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
            col={ft.ResponsiveRowBreakpoint.SM: 12, ft.ResponsiveRowBreakpoint.XL: 4},
        )
        history_card = ft.Container(
            content=ft.Column(controls=[
                ft.Row(
                    controls=[
                        ft.Text("Histórico", size=20, weight=ft.FontWeight.BOLD),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_SWEEP,
                            tooltip="Limpar histórico",
                            icon_color=ft.Colors.RED_700,
                            on_click=self.confirm_clear_history,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(
                    controls=[
                        self.run_search,
                        self.run_state_filter,
                        self.run_business_filter,
                        self.btn_clear_filters,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[ft.Row(
                            controls=[self.runs_table], scroll=ft.ScrollMode.ALWAYS,
                        )],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    height=350,
                ),
                ft.Row(
                    controls=[
                        self.btn_prev_page,
                        self.text_page_info,
                        self.btn_next_page,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ]),
            padding=18,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
            col={ft.ResponsiveRowBreakpoint.SM: 12, ft.ResponsiveRowBreakpoint.XL: 5},
        )
        logs_card = ft.Container(
            content=ft.Column(controls=[
                ft.Row(
                    controls=[
                        self.log_title,
                        ft.TextButton(
                            "Abrir pasta de logs",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self.open_logs_folder,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[ft.Row(
                            controls=[self.log_content], scroll=ft.ScrollMode.ALWAYS,
                        )],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    padding=12,
                    border_radius=8,
                    height=440,
                ),
            ]),
            padding=18,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
            col={ft.ResponsiveRowBreakpoint.SM: 12, ft.ResponsiveRowBreakpoint.XL: 3},
        )
        sqlite_only = self.engine.dialect.name != "sqlite"
        maintenance_card = ft.Container(
            content=ft.Column(controls=[
                ft.Text("Manutenção e portabilidade", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Limpe históricos antigos, transporte cadastros e proteja o banco SQLite local."
                ),
                ft.Row(
                    controls=[
                        self.retention_days,
                        ft.Button("Limpar antigos", icon=ft.Icons.AUTO_DELETE, on_click=self.confirm_purge_old_runs),
                        ft.Button("Exportar cadastros", icon=ft.Icons.FILE_UPLOAD, on_click=self.export_robots_click),
                        ft.Button("Importar cadastros", icon=ft.Icons.FILE_DOWNLOAD, on_click=self.import_robots_click),
                        ft.Button(
                            "Backup SQLite", icon=ft.Icons.BACKUP, disabled=sqlite_only,
                            tooltip="Disponível apenas quando o banco ativo é SQLite",
                            on_click=self.backup_sqlite_click,
                        ),
                        ft.Button(
                            "Restaurar SQLite", icon=ft.Icons.RESTORE, disabled=sqlite_only,
                            tooltip="Disponível apenas quando o banco ativo é SQLite",
                            on_click=self.restore_sqlite_click,
                        ),
                    ],
                    wrap=True,
                ),
            ]),
            padding=18,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
        )
        schedules_card = ft.Container(
            content=ft.Column(controls=[
                ft.Row(
                    controls=[
                        ft.Column(controls=[
                            ft.Text("Agendamentos", size=20, weight=ft.FontWeight.BOLD),
                            self.task_status,
                        ], expand=True),
                        self.install_task_button,
                        self.edit_task_button,
                        self.remove_task_button,
                    ],
                ),
                ft.Row(
                    controls=[
                        self.schedule_robot,
                        self.schedule_frequency,
                        self.schedule_weekday,
                        self.schedule_time,
                        ft.Button("Agendar", icon=ft.Icons.ADD_ALARM, on_click=self.save_schedule),
                    ],
                    wrap=True,
                ),
                self.schedule_custom_days,
                ft.Container(
                    content=ft.Row(controls=[self.schedules_table], scroll=ft.ScrollMode.ALWAYS),
                    height=280,
                ),
            ]),
            padding=18,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
        )
        return ft.Column(
            controls=[
                header,
                registration,
                ft.ResponsiveRow(
                    controls=[robots_card, history_card, logs_card],
                    spacing=16,
                    run_spacing=16,
                ),
                schedules_card,
                maintenance_card,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _file_picker_for(
        self, field: ft.TextField, pick_directory: bool = False,
        fallback_field: ft.TextField = None, auto_update_cwd: bool = False
    ):
        """Return a click handler that opens a native OS file/folder picker."""
        async def handler(_=None) -> None:
            raw = (field.value or "").strip()
            if not raw and fallback_field:
                raw = (fallback_field.value or "").strip()

            if raw:
                p = Path(raw)
                initial = str(p if p.is_dir() else p.parent)
            else:
                initial = str(PROJECT_ROOT)

            def pick_native():
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                if pick_directory:
                    res = filedialog.askdirectory(parent=root, initialdir=initial, title="Selecionar Pasta")
                else:
                    res = filedialog.askopenfilename(parent=root, initialdir=initial, title="Selecionar Arquivo")
                root.destroy()
                return res

            path = await asyncio.to_thread(pick_native)
            if path:
                # tkinter returns forward slashes, let's normalize to Path standard
                field.value = str(Path(path))

                # Se esse campo é o arquivo principal, atualizamos a pasta de trabalho automaticamente
                if auto_update_cwd and self.cwd:
                    current_cwd = (self.cwd.value or "").strip()
                    # Só substitui se estiver vazio ou com o diretório padrão do orquestrador
                    if not current_cwd or current_cwd == str(PROJECT_ROOT):
                        self.cwd.value = str(Path(path).parent)

                self.page.update()
        return handler

    def toggle_theme(self, _=None) -> None:
        use_light = self.page.theme_mode == ft.ThemeMode.DARK
        self.page.theme_mode = ft.ThemeMode.LIGHT if use_light else ft.ThemeMode.DARK
        self.theme_button.icon = ft.Icons.DARK_MODE if use_light else ft.Icons.LIGHT_MODE
        self.theme_button.tooltip = "Usar tema escuro" if use_light else "Usar tema claro"
        self.page.update()

    def set_status(self, message: str, error: bool = False) -> None:
        self.status.value = message
        self.status.color = ERROR if error else ft.Colors.ON_SURFACE
        self.status_icon.name = ft.Icons.ERROR if error else ft.Icons.INFO
        self.status_icon.color = ERROR if error else ACCENT

    def change_executor(self, _=None) -> None:
        selected = self.executor_type.value or "python"
        self.launcher.disabled = selected == "executable"
        self.launcher.value = "O próprio alvo será executado" if selected == "executable" else default_launcher(selected)
        self.page.update()

    @staticmethod
    def windows_task_status(installed: bool) -> str:
        if installed:
            return "Gatilho global instalado. Verifica todos os agendamentos a cada 5 minutos."
        return "Gatilho global não instalado. Instale uma única vez para ativar os horários."

    def update_windows_task_controls(self, installed: bool) -> None:
        self.task_status.value = self.windows_task_status(installed)
        self.install_task_button.disabled = installed
        self.edit_task_button.disabled = not installed
        self.remove_task_button.disabled = not installed

    def change_schedule_frequency(self, _=None) -> None:
        self.schedule_weekday.disabled = self.schedule_frequency.value != "weekly"
        self.schedule_weekday.visible = self.schedule_frequency.value != "custom"
        self.schedule_custom_days.visible = self.schedule_frequency.value == "custom"
        self.page.update()

    async def on_filter_change(self, _=None):
        self.history_page = 1
        self.refresh()

    async def clear_filters(self, _=None):
        self.robot_search.value = ""
        self.run_search.value = ""
        self.run_state_filter.value = ""
        self.run_business_filter.value = ""
        self.history_page = 1
        self.refresh()

    async def prev_page(self, _=None):
        if self.history_page > 1:
            self.history_page -= 1
            self.refresh()

    async def next_page(self, _=None):
        max_page = max(1, (self.history_total + self.history_limit - 1) // self.history_limit)
        if self.history_page < max_page:
            self.history_page += 1
            self.refresh()

    def refresh(self, update_page: bool = True) -> None:
        robot_term = (self.robot_search.value or "").strip()
        run_term = (self.run_search.value or "").strip()
        state_val = self.run_state_filter.value or None
        bus_val = self.run_business_filter.value or None

        offset = (self.history_page - 1) * self.history_limit

        robots = list_robots(self.engine, search=robot_term if robot_term else None)
        all_robots = list_robots(self.engine)
        current_robot = self.schedule_robot.value
        self.schedule_robot.options = [
            ft.DropdownOption(key=robot.id, text=robot.name)
            for robot in all_robots if robot.active
        ]
        valid_robot_ids = {robot.id for robot in all_robots if robot.active}
        if current_robot in valid_robot_ids:
            self.schedule_robot.value = current_robot
        elif valid_robot_ids:
            self.schedule_robot.value = next(robot.id for robot in all_robots if robot.active)
        else:
            self.schedule_robot.value = None
        runs, total = list_runs(
            self.engine,
            limit=self.history_limit,
            offset=offset,
            state=state_val,
            business_result=bus_val,
            search=run_term if run_term else None
        )
        self.history_total = total
        max_page = max(1, (total + self.history_limit - 1) // self.history_limit)
        if self.history_page > max_page:
            self.history_page = max_page
            runs, _ = list_runs(
                self.engine,
                limit=self.history_limit,
                offset=(self.history_page - 1) * self.history_limit,
                state=state_val,
                business_result=bus_val,
                search=run_term if run_term else None,
            )

        # Encontrar as execuções ativas
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from .models import Run
        with Session(self.engine) as session:
            active_list = session.scalars(
                select(Run).where(Run.state.in_({"queued", "starting", "running", "cancelling"}))
            )
            active_runs = {run.robot_id: run for run in active_list}

        self.robots_table.columns = [
            ft.DataColumn(label=ft.Text("Nome")),
            ft.DataColumn(label=ft.Text("Tipo")),
            ft.DataColumn(label=ft.Text("Arquivo")),
            ft.DataColumn(label=ft.Text("Status")),
            ft.DataColumn(label=ft.Text("Ação")),
        ]
        self.robots_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(robot.name, weight=ft.FontWeight.BOLD)),
                ft.DataCell(robot.executor_type),
                ft.DataCell(Path(robot.script).name),
                ft.DataCell("Ativa" if robot.active else "Desativada"),
                ft.DataCell(ft.Row(controls=[
                    ft.Button(
                        "Enfileirar", disabled=not robot.active,
                        on_click=self.enqueue_handler(robot.id, robot.name),
                    ),
                    self.robot_run_control(robot, active_runs.get(robot.id)),
                    ft.IconButton(
                        icon=ft.Icons.EDIT, tooltip="Editar",
                        on_click=self.edit_handler(robot),
                    ),
                    ft.Button(
                        "Desativar" if robot.active else "Ativar",
                        on_click=self.toggle_robot_handler(robot.id, robot.name, not robot.active),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, tooltip="Remover",
                        icon_color=ft.Colors.RED_700,
                        on_click=self.confirm_remove_robot(robot.id, robot.name),
                    ),
                ], spacing=2)),
            ], color=ft.Colors.SURFACE_CONTAINER_HIGH if not robot.active else None)
            for robot in robots
        ]

        schedules = list_schedules(self.engine)
        self.schedules_table.columns = [
            ft.DataColumn(label=ft.Text("Automação")),
            ft.DataColumn(label=ft.Text("Recorrência")),
            ft.DataColumn(label=ft.Text("Próximo disparo")),
            ft.DataColumn(label=ft.Text("Último disparo")),
            ft.DataColumn(label=ft.Text("Status")),
            ft.DataColumn(label=ft.Text("Ações")),
        ]
        self.schedules_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(robot_name, weight=ft.FontWeight.BOLD)),
                ft.DataCell(ft.Text(self.schedule_description(schedule))),
                ft.DataCell(ft.Text(format_time(schedule.next_run_at))),
                ft.DataCell(ft.Text(format_time(schedule.last_run_at))),
                ft.DataCell(ft.Text("Ativo" if schedule.active else "Pausado")),
                ft.DataCell(ft.Row(controls=[
                    ft.Button(
                        "Pausar" if schedule.active else "Ativar",
                        on_click=self.toggle_schedule_handler(schedule.id, not schedule.active),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, tooltip="Remover agendamento",
                        icon_color=ft.Colors.RED_700,
                        on_click=self.remove_schedule_handler(schedule.id),
                    ),
                ])),
            ])
            for schedule, robot_name in schedules
        ]

        self.runs_table.columns = [
            ft.DataColumn(label=ft.Text("Início")),
            ft.DataColumn(label=ft.Text("Automação")),
            ft.DataColumn(label=ft.Text("Estado")),
            ft.DataColumn(label=ft.Text("Negócio")),
            ft.DataColumn(label=ft.Text("Saída")),
            ft.DataColumn(label=ft.Text("Ações")),
        ]
        self.runs_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(format_time(run.started_at or run.created_at))),
                ft.DataCell(ft.Text(run.configuration.get("name", "Desconhecido"), weight=ft.FontWeight.W_500)),
                ft.DataCell(status_badge(run.state)),
                ft.DataCell(status_badge(run.business_result)),
                ft.DataCell(ft.Text("—" if run.exit_code is None else str(run.exit_code))),
                ft.DataCell(self.run_actions(run)),
            ])
            for run in runs
        ]
        if self.selected_run_id:
            selected = next((run for run in runs if run.id == self.selected_run_id), None)
            if selected:
                self.update_log(selected)

        # Atualiza botões de paginação
        self.btn_prev_page.disabled = self.history_page <= 1
        self.btn_next_page.disabled = self.history_page >= max_page
        self.text_page_info.value = f"Pág {self.history_page}/{max_page}"

        if update_page:
            self.page.update()

    async def confirm_clear_robots(self, _=None) -> None:
        def on_confirm(_=None):
            self.page.pop_dialog()
            try:
                removed_runs, failures = clear_all_robots(self.engine, logs_root())
                msg = f"Todas as automações e histórico removidos."
                if failures:
                    msg += f" (Aviso: {failures} pasta(s) de log ocupada(s))"
                self.set_status(msg)
                self.selected_run_id = None
                self.log_content.value = "Nenhuma execução selecionada."
                self.log_title.value = "Selecione uma execução para ver os logs"
                self.refresh()
            except ValueError as e:
                self.set_status(str(e), error=True)
                self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Remover todas automações?"),
            content=ft.Text("Isso removerá TODOS os robôs e TODO o histórico. Tem certeza?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("Limpar Tudo", on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    async def confirm_clear_history(self, _=None) -> None:
        def on_confirm(_=None):
            self.page.pop_dialog()
            try:
                removed_runs, failures = clear_all_runs(self.engine, logs_root())
                msg = f"Histórico limpo. {removed_runs} registro(s) removidos."
                if failures:
                    msg += f" (Aviso: {failures} pasta(s) de log ocupada(s))"
                self.set_status(msg)
                self.selected_run_id = None
                self.log_content.value = "Nenhuma execução selecionada."
                self.log_title.value = "Selecione uma execução para ver os logs"
                self.refresh()
            except ValueError as e:
                self.set_status(str(e), error=True)
                self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Limpar todo o histórico?"),
            content=ft.Text("Isso apagará permanentemente o histórico e os logs de todas as automações. Continuar?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("Limpar Histórico", on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    def open_logs_folder(self, _=None) -> None:
        import os
        try:
            # Create if it doesn't exist just in case
            logs_root().mkdir(parents=True, exist_ok=True)
            os.startfile(str(logs_root()))
            self.set_status("Pasta de logs aberta no Windows Explorer.")
            self.page.update()
        except Exception as e:
            self.set_status(f"Erro ao abrir pasta: {e}", error=True)
            self.page.update()

    async def _pick_open_file(self, title: str, filetypes) -> Path | None:
        def pick_native():
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            result = filedialog.askopenfilename(parent=root, title=title, filetypes=filetypes)
            root.destroy()
            return result
        selected = await asyncio.to_thread(pick_native)
        return Path(selected) if selected else None

    async def _pick_save_file(self, title: str, filename: str, extension: str, filetypes) -> Path | None:
        def pick_native():
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            result = filedialog.asksaveasfilename(
                parent=root, title=title, initialfile=filename,
                defaultextension=extension, filetypes=filetypes,
            )
            root.destroy()
            return result
        selected = await asyncio.to_thread(pick_native)
        return Path(selected) if selected else None

    async def confirm_purge_old_runs(self, _=None) -> None:
        try:
            days = int(self.retention_days.value)
            if days <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.set_status("Informe uma retenção em dias maior que zero.", error=True)
            self.page.update()
            return

        def on_confirm(_=None):
            self.page.pop_dialog()
            try:
                removed, failures = purge_old_runs(self.engine, logs_root(), days)
                message = f"Retenção aplicada: {removed} execução(ões) removida(s)."
                if failures:
                    message += f" {failures} pasta(s) de log não puderam ser removidas."
                self.set_status(message, error=bool(failures))
                self.selected_run_id = None
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Aplicar retenção?"),
            content=ft.Text(f"Execuções finalizadas há mais de {days} dias e seus logs serão removidos."),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("Limpar antigos", on_click=on_confirm),
            ],
        ))

    async def save_schedule(self, _=None) -> None:
        try:
            if not self.schedule_robot.value:
                raise ValueError("Selecione uma automação.")
            frequency = self.schedule_frequency.value or "daily"
            if frequency == "weekly":
                weekday = int(self.schedule_weekday.value)
            elif frequency == "custom":
                weekday = weekday_mask([
                    control.data for control in self.schedule_custom_days.controls if control.value
                ])
            else:
                weekday = None
            schedule_id = add_schedule(
                self.engine, self.schedule_robot.value, frequency,
                (self.schedule_time.value or "").strip(), weekday,
            )
            self.set_status(f"Agendamento criado: {schedule_id}")
            self.refresh()
        except Exception as error:
            self.set_status(str(error), error=True)
            self.page.update()

    @staticmethod
    def schedule_description(schedule) -> str:
        if schedule.frequency == "daily":
            recurrence = "Diário"
        elif schedule.frequency == "weekly":
            recurrence = WEEKDAYS[schedule.weekday]
        else:
            recurrence = ", ".join(WEEKDAYS[day][:3] for day in weekdays_from_mask(schedule.weekday))
        return f"{recurrence} às {schedule.time_of_day}"

    def toggle_schedule_handler(self, schedule_id: str, active: bool):
        async def handler(_=None) -> None:
            try:
                set_schedule_active(self.engine, schedule_id, active)
                self.set_status("Agendamento ativado." if active else "Agendamento pausado.")
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()
        return handler

    def remove_schedule_handler(self, schedule_id: str):
        async def handler(_=None) -> None:
            try:
                remove_schedule(self.engine, schedule_id)
                self.set_status("Agendamento removido.")
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()
        return handler

    async def install_windows_task_click(self, _=None) -> None:
        try:
            await asyncio.to_thread(install_windows_task, PROJECT_ROOT)
            self.update_windows_task_controls(True)
            self.set_status("Gatilho global instalado. Todos os agendamentos usarão esta única tarefa.")
        except Exception as error:
            self.set_status(str(error), error=True)
        self.page.update()

    async def confirm_remove_windows_task(self, _=None) -> None:
        async def on_confirm(_=None) -> None:
            self.page.pop_dialog()
            try:
                await asyncio.to_thread(remove_windows_task)
                self.update_windows_task_controls(False)
                self.set_status("Gatilho global removido. Agendamentos permanecem salvos, mas não dispararão.")
            except Exception as error:
                self.set_status(str(error), error=True)
            self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Remover gatilho global?"),
            content=ft.Text(
                "A única tarefa do RCC será removida do Agendador do Windows. "
                "Os agendamentos continuarão salvos, mas não executarão automaticamente."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("Remover gatilho", on_click=on_confirm),
            ],
        ))

    async def open_windows_task_scheduler_click(self, _=None) -> None:
        try:
            await asyncio.to_thread(open_windows_task_scheduler)
            self.set_status(
                f'Agendador do Windows aberto. Selecione a tarefa "{TASK_NAME}" para editar.'
            )
        except Exception as error:
            self.set_status(str(error), error=True)
        self.page.update()

    async def export_robots_click(self, _=None) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = await self._pick_save_file(
            "Exportar cadastros", f"rcc-cadastros-{stamp}.json", ".json",
            [("Backup JSON", "*.json")],
        )
        if path:
            try:
                count = export_robots(self.engine, path)
                self.set_status(f"{count} automação(ões) exportada(s) para {path}.")
            except Exception as error:
                self.set_status(str(error), error=True)
            self.page.update()

    async def import_robots_click(self, _=None) -> None:
        path = await self._pick_open_file("Importar cadastros", [("Backup JSON", "*.json")])
        if not path:
            return

        def on_confirm(_=None):
            self.page.pop_dialog()
            try:
                created, updated = import_robots(self.engine, path)
                self.set_status(f"Importação concluída: {created} criada(s), {updated} atualizada(s).")
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Importar cadastros?"),
            content=ft.Text("Automações com o mesmo nome serão atualizadas. O histórico não será alterado."),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("Importar", on_click=on_confirm),
            ],
        ))

    async def backup_sqlite_click(self, _=None) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = await self._pick_save_file(
            "Backup do banco SQLite", f"rcc-banco-{stamp}.db", ".db",
            [("Banco SQLite", "*.db")],
        )
        if path:
            try:
                backup_sqlite(self.engine, path)
                self.set_status(f"Backup SQLite salvo em {path}.")
            except Exception as error:
                self.set_status(str(error), error=True)
            self.page.update()

    async def restore_sqlite_click(self, _=None) -> None:
        path = await self._pick_open_file("Restaurar banco SQLite", [("Banco SQLite", "*.db")])
        if not path:
            return

        def on_confirm(_=None):
            self.page.pop_dialog()
            try:
                restore_sqlite(self.engine, path)
                self.selected_run_id = None
                self.set_status("Banco SQLite restaurado com sucesso.")
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Restaurar banco SQLite?"),
            content=ft.Text("O banco atual será substituído pelo backup selecionado."),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("Restaurar", on_click=on_confirm),
            ],
        ))

    async def refresh_click(self, _=None) -> None:
        self.refresh()
        self.set_status("Dados atualizados")
        self.page.update()

    def reset_form(self) -> None:
        self.editing_robot_id = None
        self.name.value = ""
        self.target.value = ""
        self.arguments.value = ""
        self.timeout.value = "3600"
        self.executor_type.value = "python"
        self.launcher.disabled = False
        self.launcher.value = default_launcher("python")
        self.save_button.content = "Cadastrar"
        self.save_button.icon = ft.Icons.ADD
        self.cancel_edit_button.visible = False

    async def cancel_edit(self, _=None) -> None:
        self.reset_form()
        self.set_status("Edição cancelada")
        self.page.update()

    async def save_robot(self, _=None) -> None:
        try:
            executor_type = self.executor_type.value or "python"
            target = str(Path(self.target.value.strip()).resolve())
            launcher = target if executor_type == "executable" else str(Path(self.launcher.value.strip()).resolve())
            cwd = str(Path(self.cwd.value.strip()).resolve())
            if not self.name.value.strip():
                raise ValueError("Informe o nome")
            if error := validate_command_paths(executor_type, launcher, target, cwd):
                raise ValueError(error)
            timeout = float(self.timeout.value)
            if timeout <= 0:
                raise ValueError("Timeout deve ser positivo")
            values = (
                self.name.value.strip(), target, launcher, cwd,
                parse_arguments(self.arguments.value), timeout, executor_type,
            )
            if self.editing_robot_id:
                update_robot(self.engine, self.editing_robot_id, *values)
                self.set_status(f"Automação atualizada: {self.name.value.strip()}")
            else:
                robot_id = add_robot(self.engine, *values)
                self.set_status(f"Automação cadastrada: {robot_id}")
            self.reset_form()
            self.refresh()
        except Exception as error:
            self.set_status(str(error), error=True)
            self.page.update()

    def edit_handler(self, robot):
        snapshot = {
            "id": robot.id,
            "name": robot.name,
            "executor_type": robot.executor_type,
            "script": robot.script,
            "interpreter": robot.interpreter,
            "cwd": robot.cwd,
            "arguments": list(robot.arguments),
            "timeout": robot.timeout,
        }

        async def handler(_=None) -> None:
            self.editing_robot_id = snapshot["id"]
            self.name.value = snapshot["name"]
            self.executor_type.value = snapshot["executor_type"]
            self.target.value = snapshot["script"]
            self.launcher.value = snapshot["interpreter"]
            self.launcher.disabled = snapshot["executor_type"] == "executable"
            self.cwd.value = snapshot["cwd"]
            self.arguments.value = "\n".join(map(str, snapshot["arguments"]))
            self.timeout.value = str(snapshot["timeout"])
            self.save_button.content = "Salvar alterações"
            self.save_button.icon = ft.Icons.SAVE
            self.cancel_edit_button.visible = True
            self.set_status(f"Editando: {snapshot['name']}")
            self.page.update()
        return handler

    def toggle_robot_handler(self, robot_id: str, robot_name: str, active: bool):
        async def handler(_=None) -> None:
            try:
                set_robot_active(self.engine, robot_id, active)
                action = "ativada" if active else "desativada"
                self.set_status(f"Automação {action}: {robot_name}")
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()
        return handler

    def enqueue_handler(self, robot_id: str, robot_name: str):
        async def handler(_=None) -> None:
            try:
                run_id = enqueue(self.engine, robot_id)
                self.set_status(f"{robot_name} enfileirado: {run_id}")
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()
        return handler

    def execute_now_handler(self, robot_id: str, robot_name: str):
        async def handler(_=None) -> None:
            try:
                run_id = enqueue(self.engine, robot_id)
                if self.run_button.disabled:
                    self.set_status(f"{robot_name} entrou no fim da fila: {run_id}")
                    self.refresh()
                else:
                    self.set_status(f"Executando {robot_name}: {run_id}")
                    self.refresh()
                    await self.execute_single(run_id)
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()
        return handler

    def robot_run_control(self, robot, active_run) -> ft.IconButton:
        if active_run:
            return ft.IconButton(
                icon=ft.Icons.STOP,
                tooltip="Parar esta execução",
                icon_color=ft.Colors.RED_700,
                disabled=active_run.state == "cancelling",
                on_click=self.cancel_handler(active_run.id),
            )
        return ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            tooltip="Executar agora",
            disabled=not robot.active,
            on_click=self.execute_now_handler(robot.id, robot.name),
        )

    def run_actions(self, run) -> ft.Row:
        controls = [ft.Button("Logs", on_click=self.logs_handler(run))]
        if run.state in {"queued", "starting", "running", "cancelling"}:
            controls.append(ft.Button(
                "Cancelar fila" if run.state == "queued" else "Parar",
                icon=ft.Icons.STOP,
                disabled=run.state == "cancelling",
                color=ft.Colors.RED_700,
                on_click=self.cancel_handler(run.id),
            ))
        else:
            controls.append(ft.Button(
                "Remover", icon=ft.Icons.DELETE_OUTLINE, color=ft.Colors.RED_700,
                on_click=self.confirm_remove_run(run.id),
            ))
        return ft.Row(controls=controls)

    def confirm_remove_robot(self, robot_id: str, robot_name: str):
        async def remove(_=None) -> None:
            self.page.pop_dialog()
            try:
                runs, failures = remove_robot(self.engine, robot_id, logs_root())
                if self.selected_run_id:
                    self.selected_run_id = None
                    self.log_title.value = "Selecione uma execução para ver os logs"
                    self.log_content.value = ""
                message = f"Automação removida: {robot_name}; {runs} execução(ões) removida(s)"
                if failures:
                    message += f"; {failures} pasta(s) de log não puderam ser removidas"
                self.set_status(message, error=bool(failures))
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()

        async def handler(_=None) -> None:
            dialog = ft.AlertDialog(
                modal=True,
                title="Remover automação?",
                content=ft.Text(
                    f"{robot_name}, todo o histórico dessa automação e seus logs serão excluídos."
                ),
                actions=[
                    ft.Button("Voltar", on_click=lambda _: self.page.pop_dialog()),
                    ft.Button("Remover", color=ft.Colors.RED_700, on_click=remove),
                ],
            )
            self.page.show_dialog(dialog)
        return handler

    def confirm_remove_run(self, run_id: str):
        async def remove(_=None) -> None:
            self.page.pop_dialog()
            try:
                logs_removed = remove_run(self.engine, run_id, logs_root())
                if self.selected_run_id == run_id:
                    self.selected_run_id = None
                    self.log_title.value = "Selecione uma execução para ver os logs"
                    self.log_content.value = ""
                self.set_status(
                    f"Execução removida: {run_id}" if logs_removed else
                    f"Execução removida; a pasta de logs não pôde ser excluída: {run_id}",
                    error=not logs_removed,
                )
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()

        async def handler(_=None) -> None:
            dialog = ft.AlertDialog(
                modal=True,
                title="Remover esta execução?",
                content=ft.Text("Somente esta entrada do histórico e seus logs serão excluídos."),
                actions=[
                    ft.Button("Voltar", on_click=lambda _: self.page.pop_dialog()),
                    ft.Button("Remover", color=ft.Colors.RED_700, on_click=remove),
                ],
            )
            self.page.show_dialog(dialog)
        return handler

    def cancel_handler(self, run_id: str):
        async def handler(_=None) -> None:
            try:
                state = cancel(self.engine, run_id)
                self.set_status(f"Cancelamento solicitado: {state}")
                self.refresh()
            except Exception as error:
                self.set_status(str(error), error=True)
                self.page.update()
        return handler

    def logs_handler(self, run):
        async def handler(_=None) -> None:
            self.selected_run_id = run.id
            self.update_log(run)
            self.page.update()
        return handler

    def update_log(self, run) -> None:
        stdout = read_log(run.stdout_path)
        stderr = read_log(run.stderr_path)
        self.log_title.value = f"Logs — {run.id}"
        self.log_content.value = f"STDOUT\n{stdout}\n\nSTDERR\n{stderr}"

    async def execute_single(self, run_id: str) -> None:
        """Execute exactly one specific run, bypassing FIFO queue order.

        Used by the per-robot Play button.  Other queued items stay untouched.
        """
        self.run_button.disabled = True
        self.progress.visible = True
        self.page.update()
        try:
            worker = asyncio.create_task(
                asyncio.to_thread(run_engine_direct, self.engine, run_id, logs_root())
            )
            while not worker.done():
                await asyncio.sleep(0.5)
                self.refresh()
            state = await worker
            if state == "skipped":
                self.set_status("Execução não pôde ser iniciada (já cancelada ou em execução)")
        except Exception as error:
            self.set_status(str(error), error=True)
        finally:
            self.run_button.disabled = False
            self.progress.visible = False
            self.refresh()

    async def execute_queue(self, _=None) -> None:
        self.run_button.disabled = True
        self.progress.visible = True
        self.set_status("Motor processando a fila...")
        self.page.update()
        try:
            worker = asyncio.create_task(asyncio.to_thread(run_engine, self.engine, logs_root()))
            while not worker.done():
                await asyncio.sleep(0.5)
                self.refresh()
            processed = await worker
            self.set_status(f"Fila concluída: {processed} execução(ões)")
        except Exception as error:
            self.set_status(str(error), error=True)
        finally:
            self.run_button.disabled = False
            self.progress.visible = False
            self.refresh()


async def main(page: ft.Page) -> None:
    page.title = "Zanella Orchestrator"
    page.fonts = {
        "Inter": "fonts/Inter-Variable.ttf",
        "JetBrains Mono": "fonts/JetBrainsMono-Regular.ttf",
    }
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        font_family="Inter",
        use_material3=True,
        color_scheme=ft.ColorScheme(
            primary=PRIMARY,
            on_primary="#FFFFFF",
            secondary=ACCENT,
            surface="#F8FAFC",
            on_surface=DEEP_SLATE,
            surface_container_low="#FFFFFF",
            surface_container_high="#F1F5F9",
            outline_variant="#CBD5E1",
            error=ERROR,
        ),
    )
    page.dark_theme = ft.Theme(
        font_family="Inter",
        use_material3=True,
        color_scheme=ft.ColorScheme(
            primary="#3B82F6",
            on_primary="#FFFFFF",
            secondary="#22D3EE",
            surface=DEEP_SLATE,
            on_surface="#F8FAFC",
            surface_container_low="#111C31",
            surface_container_high="#1E293B",
            outline_variant="#334155",
            error="#FB7185",
        ),
    )
    page.bgcolor = ft.Colors.SURFACE
    page.padding = 24
    page.window.width = 1180
    page.window.height = 820
    page.window.maximized = True
    url = database_url()
    upgrade_database(url)
    engine = make_engine(url)
    app = ControlCenterUI(page, engine)
    app.refresh(update_page=False)
    page.add(app.build())


def run() -> None:
    ft.run(main)

if __name__ == "__main__":
    run()
