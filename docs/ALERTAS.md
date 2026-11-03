# Alertas de LinkedIn e Indeed → JobSearchAgent

LinkedIn e Indeed bloquean el acceso automatizado. En su lugar, creas alertas en tu cuenta (lo hacen ellos y te las
envían por correo) y una regla de Apple Mail guarda esos correos en `data/inbox/`. La siguiente ejecución los lee,
abre cada oferta si su página pública lo permite, filtra, puntúa y archiva los correos en `data/inbox/processed/`.
Ninguna cuenta se conecta a Claude.

## 1. Alertas de LinkedIn (frecuencia: diaria · enviar por correo)
En LinkedIn → Empleos → busca → aplica filtros → «Activar alerta». Filtros en todas: **Fecha de publicación: últimas 24 h**,
**Nivel: Prácticas NO · Junior/Associate · Intermedio**, **Tipo: Jornada completa**.

| # | Palabras clave | Ubicación |
|---|---|---|
| 1 | `"AI Engineer" OR "Machine Learning Engineer" OR MLOps OR "GenAI"` | Lausanne |
| 2 | (igual que 1) | Munich |
| 3 | (igual que 1) | Vienna |
| 4 | (igual que 1) | Zurich |
| 5 | (igual que 1) | Madrid |
| 6 | `"AI Engineer" OR "Automation Engineer" OR "Machine Learning"` | Valencia |
| 7 | (igual que 6) | A Coruña |
| 8 | `"Network Engineer" OR "IoT" OR "Embedded" OR "5G" OR "Hardware Engineer" OR "RF Engineer"` | Munich |
| 9 | (igual que 8) | Switzerland (cubre Lausanne y Zurich) |
| 10 | (igual que 8) | Vienna |
| 11 | (igual que 8) | Madrid |
| 12 | `"z/OS" OR CICS OR "IBM MQ" OR Mainframe` | Europe (filtro: Remoto/Híbrido) |
| 13 | `"Supply Chain" OR "Transport Planner" OR "Logistics Engineer" OR Outbound` | Madrid |
| 14 | (igual que 13) | Munich |

## 2. Alertas de Indeed (es / de / ch / at)
En cada Indeed del país: busca → «Recibir empleos nuevos por email». Fecha: últimos 1 día.

| # | Sitio | Qué | Dónde |
|---|---|---|---|
| 15 | es.indeed.com | `AI Engineer OR Machine Learning` | Madrid |
| 16 | es.indeed.com | `mainframe OR CICS OR "IBM MQ"` | España |
| 17 | de.indeed.com | `Machine Learning Engineer` | München |
| 18 | ch.indeed.com | `Machine Learning Engineer` | Zürich / Lausanne |
| 19 | at.indeed.com | `Machine Learning Engineer` | Wien |

## 3. Regla de Apple Mail (una sola vez)
Requisito: que la cuenta donde recibes las alertas esté en Apple Mail y que Mail esté abierto cuando lleguen
(los correos que lleguen con Mail cerrado se procesan al abrirlo).

1. Copia el script a la carpeta de scripts de Mail (desde la carpeta del proyecto; sustituye la ruta):
   ```sh
   mkdir -p ~/Library/Application\ Scripts/com.apple.mail
   sed "s#__PROJECT_DIR__#$PWD#g" scripts/mail/GuardarAlertaEmpleo.applescript \
      > ~/Library/Application\ Scripts/com.apple.mail/GuardarAlertaEmpleo.applescript
   ```
2. Mail → Ajustes → Reglas → Añadir regla:
   - Descripción: `JobSearchAgent alertas`
   - **Si se cumple cualquiera** de: `De` contiene `jobalerts-noreply@linkedin.com` · `De` contiene `indeed.com`
     (comprueba el remitente real en la primera alerta que recibas de cada plataforma y ajústalo si es distinto)
   - Acción: **Ejecutar AppleScript** → `GuardarAlertaEmpleo`
3. Al guardar, Mail pregunta si aplicar la regla a los mensajes existentes: responde **No aplicar** (o «Aplicar» si
   quieres procesar las alertas que ya tengas).

Para comprobarlo: cuando llegue una alerta, debe aparecer un `alerta_*.eml` en `data/inbox/`.

## 4. Enlaces a mano (opcional)
Pega URLs de ofertas, una por línea, en `data/inbox/links.txt`. La próxima ejecución las evalúa.

## Desactivar
Borra la regla en Mail y el archivo `~/Library/Application Scripts/com.apple.mail/GuardarAlertaEmpleo.applescript`.
