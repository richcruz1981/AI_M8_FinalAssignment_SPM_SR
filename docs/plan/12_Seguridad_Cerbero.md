# 12 · Seguridad — Agente 5 "Cerbero"

Cerbero revisa **cada acción de los agentes** antes de que tenga efecto y deja un registro de auditoría encadenado por hashes. No usa IA: son reglas deterministas (`src/spm_sr/cerbero/rules.py`), para que el guardián no sea a su vez inyectable.

## Flujo

```
Telegram ─► [inbound] ─► Radamantis ─► Cronos ─► [data] ─► Thanatos ─► [llm_in] ─► IA ─► [llm_out] ─► Zeus ─► [outbound] ─► Telegram
                                                                                                            │
                                         security_audit_log (BD del proyecto) ◄── todas las puertas ───────┘
```

## Puertas

| Puerta | Agente | Qué revisa | Decisión ante riesgo |
|---|---|---|---|
| `inbound` | Radamantis | Chat autorizado, ≤300 caracteres, ≤12 peticiones/min, caracteres de control, prompt injection (PI-01…06), SQL/comandos/HTML (SQL-01, CMD-01, XSS-01, PATH-01) | BLOCK + respuesta genérica; 3 bloqueos en 10 min → **cuarentena 30 min** (el bot deja de responder a ese chat) |
| `data` | Cronos | Todo campo de texto leído de la BD: mismas reglas + secretos + longitud | Campo malicioso → `[removed by security]` y el registro se marca; si >20 % de los registros están contaminados → **HALT** (la corrida se detiene, E-SEC-01) |
| `llm_in` | Thanatos | Que ningún registro marcado viaje a la IA | La narrativa sale de la plantilla determinista |
| `llm_out` | Thanatos | Enlaces, HTML, secretos, instrucciones, longitud de la respuesta de la IA | BLOCK → plantilla (E-SEC-02); además sigue la verificación de cifras existente |
| `outbound` | Zeus | Secretos (token Telegram, API keys, URL de BD con clave, llave privada), destinatario autorizado, HTML no permitido, enlaces fuera de `hatchvps.com` | Secreto o destinatario ajeno → **HALT de Zeus** (no se envía nada más, E-SEC-03); HTML/enlace ajeno → se elimina y se audita |

Además el prompt de la IA declara que el JSON es dato no confiable y que no debe seguir instrucciones contenidas en él.

## Log de auditoría

| Campo | Contenido |
|---|---|
| `ts`, `source`, `session` | Hora UTC; proceso (`bot`, `sr-schedule`, `sr-manual`, `dashboard-export`); sesión |
| `agent`, `action`, `gate` | Quién hizo qué y qué puerta lo revisó |
| `decision`, `severity`, `reasons` | ALLOW / SANITIZE / BLOCK / QUARANTINE / HALT; códigos de regla |
| `subject` | Chat enmascarado (`chat ***1234`) o registro/campo |
| `content_sha256`, `excerpt` | Huella del contenido; extracto neutralizado solo en bloqueos (no se muestra en el dashboard) |
| `prev_hash`, `hash` | Cadena por sesión: cualquier edición posterior rompe la verificación |

- **Dónde vive:** tabla `security_audit_log` en la BD del proyecto (se crea si no existe; nunca se borra ni altera). La comparten el bot del servidor y las corridas de GitHub Actions.
- **Dónde se consulta:** dashboard de uso del bot (`/app/`), sección *Security audit log · Cerbero*: eventos de 24 h, bloqueos, saneamientos, detenciones, chats en cuarentena, integridad de la cadena y tabla filtrable.
- **Qué NO se guarda:** el texto completo de mensajes o datos, chat IDs completos, credenciales. Tampoco se escribe a archivo en el servidor (`AUDIT_FILE_LOG=0`) porque todo archivo bajo `/www` es público.

## Configuración (`config/settings.yaml` → `security`)

`max_message_len`, `rate_per_min`, `strikes_to_quarantine`, `quarantine_min`, `field_max_len`, `halt_ratio`.

## Pruebas

`tests/test_cerbero.py` y `tests/test_radamantis.py` simulan: prompt injection (inglés y español), XSS, SQL injection, comandos, ráfagas, caracteres de control, nombre de proyecto envenenado en la BD que no debe llegar a Telegram, envenenamiento masivo (HALT), respuesta de IA con enlace, fuga de token (HALT) y manipulación del log (cadena rota).

## Límites conocidos

- Las reglas son patrones: reducen el riesgo, no lo eliminan. Un ataque redactado de forma nueva puede pasar; por eso la IA nunca decide acciones y sus cifras se verifican contra los datos.
- La cuarentena vive en memoria del proceso del bot: se reinicia si el servidor reinicia `app.py`.
- El dashboard `/app/` es público: muestra decisiones y códigos, no contenido.
