"""Cenarios controlados para validar estados do motor pela interface."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time


def report(status: str, summary: str) -> None:
    destination = Path(os.environ["RCC_RESULT_PATH"])
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"version": 1, "run_id": os.environ["RCC_RUN_ID"], "status": status, "summary": summary},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, destination)


mode = sys.argv[1] if len(sys.argv) > 1 else "success"
print(f"Cenario iniciado: {mode}", flush=True)

if mode == "success":
    for step in range(1, 6):
        print(f"Etapa {step}/5 concluida", flush=True)
        time.sleep(0.5)
    report("success", "Fluxo demonstrativo concluido")
elif mode == "business_error":
    report("business_error", "Pedido ficticio recusado pela regra de negocio")
elif mode == "technical_error":
    print("Falha tecnica ficticia", file=sys.stderr, flush=True)
    raise SystemExit(7)
elif mode == "hang":
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
    print("Processo filho iniciado; aguardando timeout ou cancelamento", flush=True)
    time.sleep(3600)
else:
    print(f"Cenario desconhecido: {mode}", file=sys.stderr, flush=True)
    raise SystemExit(2)
