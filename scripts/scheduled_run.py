#!/usr/bin/env python3
"""Lanzador programado de JobSearchAgent (lo ejecuta launchd cada día a las 19:00).

- Si han pasado menos de `interval_days` desde la última ejecución completada (o hay un aplazamiento), sale sin hacer nada.
- Si toca, pregunta con una ventana de macOS: «Ejecutar ahora» / «Mañana» / «Saltar esta vez».
  Sin respuesta en 1 hora, cuenta como «Mañana».
- Al terminar, muestra una notificación y una ventana con «Abrir informe».

Uso manual:  python3 scripts/scheduled_run.py            (comportamiento normal)
             python3 scripts/scheduled_run.py --force    (pregunta aunque no toque)
             python3 scripts/scheduled_run.py --status   (muestra el estado)
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "schedule_state.json"
INTERVAL_DAYS = 3
ASK_TIMEOUT_S = 3600
TITLE = "JobSearchAgent"


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def osa(script: str) -> str:
    r = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True)
    return (r.stdout or "").strip()


def ask(msg: str, buttons: list[str], default: str, timeout: int) -> str | None:
    btns = ", ".join(f'"{b}"' for b in buttons)
    out = osa(f'display dialog "{msg}" with title "{TITLE}" buttons {{{btns}}} default button "{default}" '
              f'with icon note giving up after {timeout}')
    if "gave up:true" in out or not out:
        return None
    return out.split("button returned:")[1].split(",")[0].strip()


def notify(msg: str) -> None:
    osa(f'display notification "{msg}" with title "{TITLE}" sound name "Glass"')


def latest_summary() -> tuple[Path | None, str]:
    runs = sorted((ROOT / "data" / "runs").glob("*/selection.json"), key=lambda p: p.stat().st_mtime)
    if not runs:
        return None, ""
    sel = json.loads(runs[-1].read_text(encoding="utf-8"))
    run_id = runs[-1].parent.name
    counts = {}
    for c in sel["selection"]:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    detail = " · ".join(f"{k} {v}" for k, v in counts.items()) or "sin ofertas válidas"
    return ROOT / "reports" / f"{run_id}.html", f"{len(sel['selection'])} ofertas nuevas ({detail})"


def main() -> int:
    st = load_state()
    today = date.today()
    if "--status" in sys.argv:
        print(json.dumps(st, ensure_ascii=False, indent=2) or "{}")
        return 0
    force = "--force" in sys.argv
    last = date.fromisoformat(st["last_completed"]) if st.get("last_completed") else None
    postponed = date.fromisoformat(st["postponed_until"]) if st.get("postponed_until") else None
    if not force:
        if last and (today - last).days < INTERVAL_DAYS:
            return 0
        if postponed and today < postponed:
            return 0

    since = f"La última fue el {last.strftime('%d/%m')}." if last else "Es la primera ejecución programada."
    choice = ask(f"Toca la búsqueda de ofertas. {since}\\n\\nTarda unos 20 minutos y usa cupo de tu suscripción "
                 f"de Claude (Opus). ¿La lanzo ahora?",
                 ["Saltar esta vez", "Mañana", "Ejecutar ahora"], "Ejecutar ahora", ASK_TIMEOUT_S)
    if choice in (None, "Mañana"):
        st["postponed_until"] = (today + timedelta(days=1)).isoformat()
        save_state(st)
        return 0
    if choice == "Saltar esta vez":
        st["last_completed"] = today.isoformat()  # vuelve a preguntar dentro de INTERVAL_DAYS
        st["last_result"] = "saltada por el usuario"
        st.pop("postponed_until", None)
        save_state(st)
        return 0

    notify("Búsqueda en marcha. Te aviso al terminar.")
    started = datetime.now()
    r = subprocess.run(["/bin/zsh", str(ROOT / "scripts" / "run_daily.sh")], cwd=ROOT)
    st.pop("postponed_until", None)
    if r.returncode != 0:
        st["last_result"] = f"error ({started:%Y-%m-%d %H:%M})"
        save_state(st)
        notify("La búsqueda ha fallado. Revisa la carpeta logs/.")
        ask("La búsqueda ha fallado. Volveré a preguntarte mañana.\\nDetalle en la carpeta logs/ del proyecto.",
            ["OK"], "OK", 600)
        st["postponed_until"] = (today + timedelta(days=1)).isoformat()
        save_state(st)
        return 1

    report, summary = latest_summary()
    st["last_completed"] = today.isoformat()
    st["last_result"] = summary
    save_state(st)
    notify(f"Informe listo: {summary}")
    if report and ask(f"Informe listo: {summary}.", ["Más tarde", "Abrir informe"], "Abrir informe", 3600) == "Abrir informe":
        subprocess.run(["/usr/bin/open", str(report)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
