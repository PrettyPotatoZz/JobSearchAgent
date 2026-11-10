# Alertas de LinkedIn e Indeed → JobSearchAgent

> Plantilla. Copia este archivo a `docs/ALERTAS.md` (ignorado por git) y anota ahí tus alertas reales.

LinkedIn e Indeed bloquean el acceso automatizado. En su lugar, creas alertas en tu cuenta (lo hacen ellos y te las
envían por correo) y una regla de Apple Mail guarda esos correos en `data/inbox/`. La siguiente ejecución los lee,
abre cada oferta si su página pública lo permite, filtra, puntúa y archiva los correos en `data/inbox/processed/`.
Ninguna cuenta se conecta a Claude.

## 1. Alertas de LinkedIn (frecuencia: diaria · enviar por correo)
En LinkedIn → Empleos → busca → aplica filtros → «Activar alerta». Crea una alerta por combinación de palabras clave y ubicación.

| # | Palabras clave | Ubicación |
|---|---|---|
| 1 | `"Puesto A" OR "Puesto B"` | Ciudad 1 |
| 2 | (igual que 1) | Ciudad 2 |

## 2. Alertas de Indeed
En el Indeed de cada país: busca → «Recibir empleos nuevos por email». Fecha: últimos 1 día.

| # | Sitio | Qué | Dónde |
|---|---|---|---|
| 3 | indeed.com | `"Puesto A"` | Ciudad 1 |

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
