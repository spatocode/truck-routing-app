# Spotter

Weather-aware truck routing. A driver enters origin, destination, departure time, and load weight. Spotter generates three corridors, samples forecast weather every 10 / 25 / 50 miles at the truck's ETA, scores each checkpoint with the assigned wind / rain / snow and load rules, then recommends the safest option.

## Stack

- **Frontend:** React, TypeScript, Vite, MapLibre GL
- **Backend:** Django, Django REST Framework
- **Routing:** OpenRouteService `driving-hgv` when `ORS_API_KEY` is set, otherwise OSRM driving routes plus offset via-points so three corridors are still returned
- **Geocoding:** Photon (OpenStreetMap)
- **Weather:** Open-Meteo hourly forecast (wind mph, rain in/hr, snowfall converted to in/hr)

No routing engine is built in-house. The product is the sampling, risk model, recommendation, map, and corridor heatmap.

## Risk model

Weather at a checkpoint is classified independently for wind, rain, and snow. The checkpoint takes the worst of those three, then load rules can raise it further.

| Condition | Low | Moderate | High | Severe | No travel |
| --- | --- | --- | --- | --- | --- |
| Wind | <25 mph | 25–34 | 35–44 | 45–54 | ≥55 mph |
| Rain | <0.10 in/hr | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow | <0.5 in/hr | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

Load rules:

- ≥55 mph wind: no travel for any load
- 45–54 mph and load > 30,000 lb: no travel
- 35–44 mph and load > 40,000 lb: severe

Recommendation order:

1. Fewest no-travel miles (treat as worse than severe)
2. Fewest severe miles
3. Fewest high miles
4. Lowest mile-weighted average risk
5. Shortest driving time

Checkpoints are colored on the selected route. The whole corridor also gets a 0–48 hour forecast heatmap that can be scrubbed independently of ETA sampling.

## Local setup

Requires Python 3.12+ and Node 20+.

```bash
cp .env.example .env

python3.14 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt

cd frontend && npm install && cd ..

# terminal 1
cd backend && source .venv/bin/activate && python manage.py runserver

# terminal 2
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to Django.

Optional: set `ORS_API_KEY` in `.env` for truck-profile routing and built-in alternatives. A free key is enough: [openrouteservice.org](https://openrouteservice.org/dev/#/signup).

```bash
cd backend && source .venv/bin/activate && pytest
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

App: [http://localhost:8080](http://localhost:8080). API: [http://localhost:8000/api/health](http://localhost:8000/api/health).

## API

`GET /api/geocode?q=chicago`

`POST /api/plan`

```json
{
  "origin": "Chicago, IL",
  "destination": "Dallas, TX",
  "origin_lat": 41.8781,
  "origin_lon": -87.6298,
  "destination_lat": 32.7767,
  "destination_lon": -96.797,
  "departure": "2026-10-22T14:00:00-05:00",
  "load_lb": 32000,
  "sample_miles": 25
}
```

Coordinates are optional. If omitted, the backend geocodes the labels.

## Deploy notes

The assessment asks for a hosted app. A simple split:

- Backend on Render / Railway / Fly using `backend/Dockerfile` (timeout ≥ 120s; a plan request fetches routes and weather. Open-Meteo is batched, then retried per checkpoint if the host rejects multi-location requests.)
- Frontend on Cloudflare Pages / Netlify / Render static, with `VITE_API_URL` pointing at the API origin and that origin listed in `CORS_ALLOWED_ORIGINS`

Or run `docker compose` on a single VM and put TLS in front of port 8080. Nginx in the web image already proxies `/api` to the API service.

## Loom walkthrough (5–10 min)

1. Form: Chicago → Dallas, now, 32,000 lb, 25-mile samples. Submit.
2. Three corridors appear. Recommended badge and the reason string.
3. Click each route: map emphasis, checkpoint dots, popup with ETA, wind/rain/snow, and load rule text.
4. Change load to 45,000 lb and re-plan to show the 40,000 lb severe upgrade.
5. Scrub the 0–48h heatmap and toggle it off/on.
6. Switch sample interval to 10 miles and show denser checkpoints.
7. Briefly open `planner/risk.py` and `planner/recommend.py`.

## Project layout

```
backend/planner/risk.py         thresholds and load rules
backend/planner/recommend.py   ranking
backend/planner/plan.py        ETA sampling + response payload
backend/planner/services/      geocoding, routing, weather
frontend/src/MapView.tsx       routes, checkpoints, heatmap
```
