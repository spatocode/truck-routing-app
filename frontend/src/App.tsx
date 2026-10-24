import { FormEvent, useMemo, useState } from "react";
import MapView from "./MapView";
import PlaceField from "./PlaceField";
import { planTrip } from "./api";
import { RISK_COLORS, RISK_LABELS, RISK_ORDER, defaultDepartureValue, formatClock, formatDuration } from "./risk";
import type { Place, PlanResponse } from "./types";

export default function App() {
  const [origin, setOrigin] = useState("Chicago, IL");
  const [destination, setDestination] = useState("Dallas, TX");
  const [originPlace, setOriginPlace] = useState<Place | undefined>();
  const [destinationPlace, setDestinationPlace] = useState<Place | undefined>();
  const [departure, setDeparture] = useState(defaultDepartureValue);
  const [loadLb, setLoadLb] = useState("32000");
  const [sampleMiles, setSampleMiles] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hourIndex, setHourIndex] = useState(0);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [editing, setEditing] = useState(true);

  const selected = plan?.routes.find((route) => route.id === selectedId) ?? null;
  const hourLabel = useMemo(() => {
    if (!plan?.heatmap.hours.length) return "Forecast";
    return formatClock(plan.heatmap.hours[hourIndex] ?? plan.heatmap.hours[0]);
  }, [plan, hourIndex]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const local = new Date(departure);
      const result = await planTrip({
        origin,
        destination,
        origin_lat: originPlace?.lat,
        origin_lon: originPlace?.lon,
        destination_lat: destinationPlace?.lat,
        destination_lon: destinationPlace?.lon,
        departure: local.toISOString(),
        load_lb: Number(loadLb) || 0,
        sample_miles: sampleMiles,
      });
      setPlan(result);
      setSelectedId(result.recommended_route_id);
      setEditing(false);
      const departureMs = local.getTime();
      const hours = result.heatmap.hours;
      const nearest = hours.reduce((best, stamp, index) => {
        const delta = Math.abs(new Date(stamp).getTime() - departureMs);
        const bestDelta = Math.abs(new Date(hours[best]).getTime() - departureMs);
        return delta < bestDelta ? index : best;
      }, 0);
      setHourIndex(hours.length ? nearest : 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not plan this trip.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">S</div>
          <div>
            <h1>Spotter</h1>
            <p>Weather-aware truck routing</p>
          </div>
        </div>

        {plan && !editing && (
          <button className="ghost" type="button" onClick={() => setEditing(true)}>
            Edit trip · {plan.origin.label.split(",")[0]} → {plan.destination.label.split(",")[0]}
          </button>
        )}
        <form className={`card form ${plan && !editing ? "is-hidden" : ""}`} onSubmit={onSubmit}>
          <PlaceField
            label="Origin"
            value={origin}
            onChange={(value, place) => {
              setOrigin(value);
              setOriginPlace(place);
            }}
          />
          <PlaceField
            label="Destination"
            value={destination}
            onChange={(value, place) => {
              setDestination(value);
              setDestinationPlace(place);
            }}
          />
          <div className="row">
            <label>
              Departure
              <input type="datetime-local" value={departure} onChange={(event) => setDeparture(event.target.value)} required />
            </label>
            <label>
              Load (lb)
              <input
                type="number"
                min="0"
                step="500"
                value={loadLb}
                onChange={(event) => setLoadLb(event.target.value)}
                required
              />
            </label>
          </div>
          <label>
            Weather sample interval
            <div className="intervals">
              {[10, 25, 50].map((miles) => (
                <button
                  key={miles}
                  type="button"
                  className={sampleMiles === miles ? "selected" : ""}
                  onClick={() => setSampleMiles(miles)}
                >
                  {miles} mi
                </button>
              ))}
            </div>
          </label>
          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Sampling weather along corridors…" : "Plan safest route"}
          </button>
          {error && <div className="error">{error}</div>}
        </form>

        {plan && (
          <>
            <div className="card">
              <div className="reason">{plan.recommendation_reason}</div>
            </div>
            <div className="routes">
              {plan.routes.map((route) => (
                <button
                  key={route.id}
                  className={`route ${route.id === selectedId ? "selected" : ""}`}
                  onClick={() => setSelectedId(route.id)}
                  type="button"
                >
                  <div className="route-head">
                    <strong>{route.summary.split(" · ")[0]}</strong>
                    {route.id === plan.recommended_route_id && <span className="badge">Recommended</span>}
                  </div>
                  <div className="metrics">
                    <span>
                      Distance <b>{route.distance_miles.toFixed(0)} mi</b>
                    </span>
                    <span>
                      Drive time <b>{formatDuration(route.duration_seconds)}</b>
                    </span>
                    <span>
                      Severe <b>{route.stats.severe_miles.toFixed(0)} mi</b>
                    </span>
                    <span>
                      High <b>{route.stats.high_miles.toFixed(0)} mi</b>
                    </span>
                    <span>
                      Avg risk <b>{route.stats.avg_risk.toFixed(2)}</b>
                    </span>
                    <span>
                      No travel <b>{route.stats.no_travel_miles.toFixed(0)} mi</b>
                    </span>
                  </div>
                </button>
              ))}
            </div>
            {selected && (
              <div className="card">
                <strong>Selected corridor</strong>
                <div className="metrics">
                  <span>
                    Checkpoints <b>{selected.checkpoints.length}</b>
                  </span>
                  <span>
                    Sampled every <b>{plan.sample_miles} mi</b>
                  </span>
                </div>
              </div>
            )}
          </>
        )}
      </aside>

      <main className="map-wrap">
        <MapView
          plan={plan}
          selectedId={selectedId}
          hourIndex={hourIndex}
          showHeatmap={showHeatmap}
          onSelectRoute={setSelectedId}
        />
        {!plan && !loading && <div className="empty">Enter a trip to compare three weather-aware corridors</div>}
        {loading && <div className="empty">Generating routes and sampling forecast at each checkpoint</div>}
        <div className="hud">
          <div className="legend">
            {RISK_ORDER.map((level) => (
              <span className="risk-chip" key={level}>
                <span className="swatch" style={{ background: RISK_COLORS[level] }} />
                {RISK_LABELS[level]}
              </span>
            ))}
          </div>
          {plan && (
            <div className="slider-card">
              <div className="slider-head">
                <strong>Corridor forecast</strong>
                <button className={`ghost ${showHeatmap ? "active" : ""}`} type="button" onClick={() => setShowHeatmap((value) => !value)}>
                  {showHeatmap ? "Heatmap on" : "Heatmap off"}
                </button>
                <span>{hourLabel}</span>
              </div>
              <input
                type="range"
                min={0}
                max={Math.max(0, plan.heatmap.hours.length - 1)}
                value={hourIndex}
                onChange={(event) => setHourIndex(Number(event.target.value))}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
