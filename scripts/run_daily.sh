#!/bin/zsh
# Ejecución diaria de JobSearchAgent (manual por ahora).
# Uso: scripts/run_daily.sh            (modelo por defecto: opus; JOBSEARCH_MODEL=sonnet para gastar menos cupo)
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT"
export PATH="$HOME/.local/bin:/Library/Frameworks/Python.framework/Versions/3.13/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

# Los archivos personales no se versionan: si falta alguno, indicar de dónde sale.
for f in config/profile.md config/preferences.json config/sources.json config/companies_verified.json \
         config/cost_of_living.json prompts/daily_search.md; do
  if [[ ! -f "$f" ]]; then
    echo "Falta $f. Créalo a partir de su plantilla .example (ver README)." >&2
    exit 1
  fi
done
export TZ="$(python3 -c 'import json; print(json.load(open("config/preferences.json")).get("timezone", "UTC"))')"

MODEL="${JOBSEARCH_MODEL:-opus}"

RUN_DATE="$(date +%F)"
MIN_DATE="$(date -v-14d +%F)"
RUN_ID="$RUN_DATE"
# Si ya hubo una ejecución completa hoy, usar una carpeta nueva para no sobrescribir el informe.
if [[ -f "data/runs/$RUN_ID/selection.json" ]]; then
  RUN_ID="${RUN_DATE}_$(date +%H%M)"
fi
RUN_DIR="data/runs/$RUN_ID"
LOG="logs/$RUN_ID.log"
mkdir -p "$RUN_DIR" logs reports data/inbox

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

log "Inicio ($RUN_ID, modelo $MODEL). Ventana de publicación: $MIN_DATE .. $RUN_DATE"
python3 scripts/jobsearch.py seen-keys > "$RUN_DIR/seen.json"
log "Consultando webs corporativas y bandeja de alertas…"
python3 scripts/jobsearch.py fetch --date "$RUN_DATE" --run "$RUN_ID" 2>&1 | tee -a "$LOG"

PROMPT="$(sed -e "s|{{RUN_DATE}}|$RUN_DATE|g" -e "s|{{MIN_DATE}}|$MIN_DATE|g" -e "s|{{RUN_DIR}}|$RUN_DIR|g" prompts/daily_search.md)"

# Permisos mínimos: búsqueda web, lectura y escritura solo en la carpeta de la ejecución
# y en los dos archivos de configuración que el agente puede refrescar. Sin Bash ni subagentes.
log "Lanzando evaluación y búsqueda con Claude Code (headless)…"
claude -p "$PROMPT" --model "$MODEL" --output-format json \
  --allowedTools "WebSearch" "WebFetch" "Read" "Glob" "Grep" \
     "Edit(./$RUN_DIR/**)" \
     "Edit(./config/companies_verified.json)" \
     "Edit(./config/cost_of_living.json)" \
  --disallowedTools "Bash" "Agent" \
  > "$RUN_DIR/claude_result.json" 2>> "$LOG" || { log "ERROR: la búsqueda de Claude falló (ver log)"; exit 1; }

python3 - "$RUN_DIR/claude_result.json" <<'PY' 2>&1 | tee -a "$LOG"
import json, sys
try:
    r = json.load(open(sys.argv[1]))
    print(f"Claude: {r.get('result', '')[:400]}")
    print(f"Duración {r.get('duration_ms', 0)/60000:.1f} min · turnos {r.get('num_turns')} · "
          f"coste equivalente API ≈ {r.get('total_cost_usd', 0):.2f} USD (con suscripción no se factura aparte)")
except Exception as e:
    print(f"No se pudo leer el resultado de Claude: {e}")
PY

if [[ ! -s "$RUN_DIR/candidates.json" ]]; then
  log "ERROR: no se generó $RUN_DIR/candidates.json"; exit 1
fi

python3 scripts/jobsearch.py build --date "$RUN_DATE" --run "$RUN_ID" 2>&1 | tee -a "$LOG"
python3 scripts/jobsearch.py record --date "$RUN_DATE" --run "$RUN_ID" 2>&1 | tee -a "$LOG"
log "Fin. Informe: $PROJECT/reports/$RUN_ID.html"
