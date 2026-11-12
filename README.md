# Fusion Esports — Stats de Pro Clubs

Web: https://duranandrese-tech.github.io/fusion/

- `fetch_ea.py` trae los datos del club desde la API de Clubes de EA (FC 27, PS5) y va guardando el historial de partidos en `data/`.
- `build_stats.py` calcula las estadísticas y genera `docs/stats.json`.
- `docs/index.html` es la web; lee `stats.json`.
- `.github/workflows/update.yml` corre todo cada 15 minutos. Para correrlo a mano: pestaña **Actions** → **Actualizar stats** → **Run workflow**.

Datos de EA Sports FC. No afiliado con EA Sports.
