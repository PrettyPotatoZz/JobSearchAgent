-- Regla de Apple Mail: guarda cada correo de alerta de empleo (LinkedIn/Indeed) como .eml
-- en la bandeja de JobSearchAgent. No lee ni envía nada más; no borra el correo.
-- Instalación: ver docs/ALERTAS.md

using terms from application "Mail"
	on perform mail action with messages theMessages for rule theRule
		set inboxPath to "__PROJECT_DIR__/data/inbox/"
		do shell script "mkdir -p " & quoted form of inboxPath
		tell application "Mail"
			repeat with m in theMessages
				try
					set src to source of m
					set stamp to do shell script "date +%Y%m%d_%H%M%S"
					set fname to inboxPath & "alerta_" & stamp & "_" & (random number from 1000 to 9999) & ".eml"
					set fh to open for access (POSIX file fname) with write permission
					write src to fh as «class utf8»
					close access fh
				on error errMsg
					try
						close access (POSIX file fname)
					end try
				end try
			end repeat
		end tell
	end perform mail action with messages
end using terms from
