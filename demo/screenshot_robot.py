"""Robô demonstrativo: abre uma janela, captura, valida e apaga a imagem."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import flet as ft
from PIL import ImageGrab


WINDOW_LEFT = 180
WINDOW_TOP = 140
WINDOW_WIDTH = 640
WINDOW_HEIGHT = 320
exit_code = 0


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


async def main(page: ft.Page) -> None:
    global exit_code
    screenshot = Path(tempfile.gettempdir()) / f"rcc-demo-{os.environ['RCC_RUN_ID']}.png"

    page.title = "Zanella Orchestrator — Robô fictício"
    page.bgcolor = "#172033"
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.left = WINDOW_LEFT
    page.window.top = WINDOW_TOP
    page.window.always_on_top = True
    page.add(
        ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Robô fictício em execução", size=28, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text(
                        "Capturando esta janela e removendo a imagem em seguida.",
                        size=15,
                        color="#b9c7e6",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
    )

    try:
        await page.window.wait_until_ready_to_show()
        await page.window.to_front()
        await asyncio.sleep(1)
        bbox = (
            WINDOW_LEFT,
            WINDOW_TOP,
            WINDOW_LEFT + WINDOW_WIDTH,
            WINDOW_TOP + WINDOW_HEIGHT,
        )
        ImageGrab.grab(bbox=bbox).save(screenshot)
        size = screenshot.stat().st_size
        digest = hashlib.sha256(screenshot.read_bytes()).hexdigest()[:12]
        print(f"Screenshot criado: {size} bytes; SHA-256 {digest}", flush=True)
        if size < 1000:
            raise RuntimeError("Screenshot gerado é pequeno demais para ser válido")
        write_result("success", f"Janela capturada e removida; {size} bytes; hash {digest}")
    except Exception as error:
        exit_code = 1
        print(f"Falha no robô fictício: {error}", file=sys.stderr, flush=True)
        write_result("technical_error", str(error))
    finally:
        screenshot.unlink(missing_ok=True)
        print(f"Limpeza confirmada: {not screenshot.exists()}", flush=True)
        await page.window.destroy()


if __name__ == "__main__":
    ft.run(main)
    raise SystemExit(exit_code)
