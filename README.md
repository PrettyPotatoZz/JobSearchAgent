# JobSearchAgent

Busca a diario ofertas nuevas por categorías y cuotas configurables en LinkedIn, Indeed y webs de empleo de empresas
verificadas, y genera un informe HTML en español.

## Uso
Primera vez: crea tus archivos locales a partir de las plantillas y rellénalos con tus datos (git los ignora).
```sh
for f in config/profile.md config/preferences.json config/sources.json config/companies_verified.json \
         config/cost_of_living.json prompts/daily_search.md docs/ALERTAS.md; do
  cp "${f%.*}.example.${f##*.}" "$f"
done
```

```sh
scripts/run_daily.sh          # búsqueda + informe + historial
open reports/latest.html
```
Tarda varios minutos (la búsqueda la hace Claude Code en modo headless con tu suscripción; no usa claves ni APIs de pago).

## Cómo funciona
1. `jobsearch.py seen-keys` → `data/runs/<fecha>/seen.json` con las ofertas ya mostradas o descartadas.
2. `jobsearch.py fetch` → `feeds.json` (ofertas con fecha de Workday/Recruitee de empresas verificadas, ver
   `config/sources.json`) e `inbox.json` (correos de alertas de LinkedIn/Indeed en `data/inbox/`, ver `docs/ALERTAS.example.md`).
3. `claude -p --model opus` con `prompts/daily_search.md` → `data/runs/<fecha>/candidates.json`. El log registra la
   duración y el coste equivalente de API (con suscripción no se factura aparte). `JOBSEARCH_MODEL=sonnet` para gastar menos cupo (rinde peor que Opus).
   Permisos: solo WebSearch, WebFetch, lectura y escritura en la carpeta de la ejecución y en
   `config/companies_verified.json` / `config/cost_of_living.json`. Bash y subagentes desactivados.
4. `jobsearch.py build` → calcula la puntuación con una tabla fija (tecnología 40 + funciones 25 + nivel 15 + ciudad 10
   + modalidad 10), revalida según `config/preferences.json` (antigüedad, ciudad, contrato, idiomas, salario mínimo por país, años de experiencia, puntuación),
   deduplica contra `data/history.json` (URL normalizada, ID de oferta, puesto+empresa+ciudad), aplica cuotas y
   rellena huecos solo con ofertas de áreas prioritarias con puntuación suficiente. Escribe `reports/<fecha>.html` y `latest.html`.
5. `jobsearch.py record` → añade mostradas y descartadas al historial (no se reevalúan) y archiva los correos procesados.

Si una oferta no publica salario, el informe muestra «No publicado» y, aparte, una **estimación** marcada como tal con
su fuente; si no hay fuente fiable, «Sin estimación fiable». Las estimaciones nunca descartan ofertas.

Si se ejecuta dos veces el mismo día, la segunda usa `data/runs/<fecha>_HHMM` y no repite ofertas.

## Configuración
Todos estos archivos son locales y no se versionan; cada uno tiene su plantilla `*.example.*`.
- `config/profile.md` — perfil. `config/preferences.json` — cuotas, ciudades, umbrales, zona horaria.
- `config/sources.json` — webs corporativas y palabras clave. `prompts/daily_search.md` — instrucciones de búsqueda. `docs/ALERTAS.md` — alertas de correo.
- `config/companies_verified.json` — empresas verificadas con fuente oficial (se revisan cada 90 días).
- `config/cost_of_living.json` — índices de coste de vida con fuente y fecha.
- Para empezar de cero el historial: `echo '{"entries": []}' > data/history.json`.

## Límites
LinkedIn e Indeed no ofrecen acceso automatizado abierto: solo se usan páginas públicas indexadas. Si una página pide
login o bloquea, se registra y se omite. Puede que algunos días no se llegue al total buscado; el informe lo indica.

## Programación (cada 3 días, preguntando antes)
`launchd/com.jobsearch.agent.plist` (plantilla; `__PROJECT_DIR__` se sustituye al instalar) despierta cada día a las 19:00 a `scripts/scheduled_run.py`, que:
- no hace nada si han pasado menos de 3 días desde la última ejecución completada (`data/schedule_state.json`);
- si toca, pregunta con una ventana de macOS: **Ejecutar ahora / Mañana / Saltar esta vez** (sin respuesta en 1 h = Mañana);
- al terminar, muestra una notificación y una ventana con **Abrir informe**; si falla, avisa y vuelve a preguntar al día siguiente.

Si el Mac está dormido a las 19:00, se ejecuta al despertar; si está apagado, pregunta al día siguiente.

Activar:
```sh
sed "s#__PROJECT_DIR__#$PWD#g" launchd/com.jobsearch.agent.plist > ~/Library/LaunchAgents/com.jobsearch.agent.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobsearch.agent.plist
```
Probar la pregunta ya (sin esperar 3 días): `python3 scripts/scheduled_run.py --force` · Estado: `--status`.

Desactivar:
```sh
launchctl bootout gui/$(id -u)/com.jobsearch.agent && rm ~/Library/LaunchAgents/com.jobsearch.agent.plist
```
