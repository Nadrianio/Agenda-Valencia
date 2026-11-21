# Underground València · agenda que se actualiza sola

Cada día a las 05:00 UTC un script lee las agendas de varias salas, genera `events.json` y la web lo muestra. Todo gratis.

## Puesta en marcha (unos 10 minutos)

1. Crea una cuenta en https://github.com y un repositorio **público** nuevo (por ejemplo `agenda-valencia`).
2. Sube todo el contenido de esta carpeta (incluida la carpeta oculta `.github`). En la web de GitHub: *Add file → Upload files*.
3. En el repositorio: *Settings → Pages → Build and deployment → Deploy from a branch → main / (root) → Save*.
4. En la pestaña *Actions*, abre **Actualizar agenda** y pulsa *Run workflow* para probarlo ya. Mira el registro: dice cuántos eventos leyó de cada sala.
5. Tu web queda en `https://TU-USUARIO.github.io/agenda-valencia/`. Se actualiza sola cada día.

## Qué hay

- `index.html`: la web (lee `events.json`).
- `events.json`: los eventos. Lo escribe el script; no lo edites a mano.
- `scraper/scrape.py`: el lector de salas (solo Python estándar, sin instalar nada).
- `.github/workflows/update.yml`: la tarea diaria.
- `manual/extra.json`: eventos que añades tú a mano. Ejemplo:
  `[{"d":"2026-12-05","h":"21:00","t":"Nombre","c":"Música","v":"Sala","p":"10 €","u":"https://…"}]`
  (`c` puede ser Música, Teatro, Cine, Arte u Otros).

## Si algo falla

- Una sala devuelve 0 eventos en el registro: su web habrá cambiado de formato y hay que ajustar su lector en `scrape.py`. Mientras tanto se conservan sus eventos anteriores y el resto sigue funcionando.
- Los lectores se escribieron sin poder probarlos contra las webs reales, así que es normal que el primer día alguno necesite un retoque.
- Para añadir una sala, añade una línea en `SOURCES`. Las páginas con datos `schema.org/Event` funcionan con `"kind": "ldjson"`.
- Comprueba las condiciones de uso de cada web y no hagas más de una lectura al día.
