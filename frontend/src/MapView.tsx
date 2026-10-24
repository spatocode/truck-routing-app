import { useEffect, useRef } from "react";
import maplibregl, { type GeoJSONSource, type Map } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { RISK_COLORS, RISK_LABELS, formatClock } from "./risk";
import type { PlanResponse } from "./types";

interface Props {
  plan: PlanResponse | null;
  selectedId: string | null;
  hourIndex: number;
  showHeatmap: boolean;
  onSelectRoute: (id: string) => void;
}

const STYLE = "https://tiles.openfreemap.org/styles/dark";

function riskFeatureCollection(plan: PlanResponse, selectedId: string | null) {
  const features = plan.routes.flatMap((route) =>
    route.segments
      .filter((segment) => segment.coordinates.length >= 2)
      .map((segment) => ({
        type: "Feature" as const,
        properties: {
          routeId: route.id,
          selected: route.id === selectedId ? 1 : 0,
          recommended: route.id === plan.recommended_route_id ? 1 : 0,
          color: RISK_COLORS[segment.risk],
        },
        geometry: { type: "LineString" as const, coordinates: segment.coordinates },
      })),
  );
  return { type: "FeatureCollection" as const, features };
}

function checkpointCollection(plan: PlanResponse, selectedId: string | null) {
  const route = plan.routes.find((item) => item.id === selectedId) ?? plan.routes[0];
  return {
    type: "FeatureCollection" as const,
    features: route.checkpoints.map((checkpoint) => ({
      type: "Feature" as const,
      properties: {
        color: RISK_COLORS[checkpoint.risk.level],
        mile: checkpoint.mile,
        eta: formatClock(checkpoint.eta),
        level: RISK_LABELS[checkpoint.risk.level],
        wind: checkpoint.wind_mph,
        rain: checkpoint.rain_in_hr,
        snow: checkpoint.snow_in_hr,
        temp: checkpoint.temp_f ?? "n/a",
        factors: checkpoint.risk.factors.join(" · "),
      },
      geometry: { type: "Point" as const, coordinates: [checkpoint.lon, checkpoint.lat] },
    })),
  };
}

function heatmapCollection(plan: PlanResponse, hourIndex: number) {
  return {
    type: "FeatureCollection" as const,
    features: plan.heatmap.points.map((point) => {
      const score = point.scores[Math.min(hourIndex, point.scores.length - 1)] ?? 1;
      return {
        type: "Feature" as const,
        properties: { score },
        geometry: { type: "Point" as const, coordinates: [point.lon, point.lat] },
      };
    }),
  };
}

function endsCollection(plan: PlanResponse) {
  return {
    type: "FeatureCollection" as const,
    features: [
      {
        type: "Feature" as const,
        properties: { kind: "origin", label: plan.origin.label },
        geometry: { type: "Point" as const, coordinates: [plan.origin.lon, plan.origin.lat] },
      },
      {
        type: "Feature" as const,
        properties: { kind: "destination", label: plan.destination.label },
        geometry: { type: "Point" as const, coordinates: [plan.destination.lon, plan.destination.lat] },
      },
    ],
  };
}

function fitPlan(map: Map, plan: PlanResponse) {
  const bounds = new maplibregl.LngLatBounds();
  for (const route of plan.routes) {
    for (const pair of route.geometry.coordinates) {
      bounds.extend(pair as [number, number]);
    }
  }
  if (bounds.isEmpty()) return;
  const canvas = map.getCanvas();
  if (canvas.clientWidth < 40 || canvas.clientHeight < 40) return;
  map.resize();
  map.fitBounds(bounds, { padding: 64, duration: 700, maxZoom: 7, essential: true });
}

export default function MapView({ plan, selectedId, hourIndex, showHeatmap, onSelectRoute }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const ready = useRef(false);
  const onSelectRef = useRef(onSelectRoute);
  const stateRef = useRef({ plan, selectedId, hourIndex, showHeatmap });
  onSelectRef.current = onSelectRoute;
  stateRef.current = { plan, selectedId, hourIndex, showHeatmap };

  function paint(map: Map) {
    const current = stateRef.current;
    if (!current.plan) return;
    const selectedId = current.selectedId ?? current.plan.recommended_route_id;
    (map.getSource("routes") as GeoJSONSource | undefined)?.setData(
      riskFeatureCollection(current.plan, selectedId),
    );
    (map.getSource("checkpoints") as GeoJSONSource | undefined)?.setData(
      checkpointCollection(current.plan, selectedId),
    );
    (map.getSource("ends") as GeoJSONSource | undefined)?.setData(endsCollection(current.plan));
    (map.getSource("heatmap") as GeoJSONSource | undefined)?.setData(
      current.showHeatmap ? heatmapCollection(current.plan, current.hourIndex) : empty(),
    );
    const segmentCount = current.plan.routes.reduce(
      (sum, route) => sum + route.segments.filter((segment) => segment.coordinates.length >= 2).length,
      0,
    );
    map.getContainer().setAttribute(
      "aria-label",
      `Route map zoom ${map.getZoom().toFixed(1)} with ${segmentCount} segments`,
    );
    for (const marker of markersRef.current) marker.remove();
    markersRef.current = [
      new maplibregl.Marker({ color: "#f0b429" }).setLngLat([current.plan.origin.lon, current.plan.origin.lat]).addTo(map),
      new maplibregl.Marker({ color: "#e7eef7" }).setLngLat([current.plan.destination.lon, current.plan.destination.lat]).addTo(map),
    ];
  }

  useEffect(() => {
    if (!root.current) return;
    const map = new maplibregl.Map({
      container: root.current,
      style: STYLE,
      center: [-96.5, 39.5],
      zoom: 4,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(root.current);

    const popup = new maplibregl.Popup({ closeButton: false, offset: 12 });

    const onReady = () => {
      if (map.getSource("routes")) {
        ready.current = true;
        paint(map);
        return;
      }

      map.addSource("heatmap", { type: "geojson", data: empty() });
      map.addSource("routes", { type: "geojson", data: empty() });
      map.addSource("checkpoints", { type: "geojson", data: empty() });
      map.addSource("ends", { type: "geojson", data: empty() });

      map.addLayer({
        id: "heatmap-layer",
        type: "heatmap",
        source: "heatmap",
        paint: {
          "heatmap-weight": ["interpolate", ["linear"], ["get", "score"], 1, 0.2, 5, 1],
          "heatmap-intensity": 1.15,
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 4, 22, 8, 48],
          "heatmap-opacity": 0.78,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(0,0,0,0)",
            0.2,
            RISK_COLORS.low,
            0.4,
            RISK_COLORS.moderate,
            0.65,
            RISK_COLORS.high,
            0.85,
            RISK_COLORS.severe,
            1,
            RISK_COLORS.no_travel,
          ],
        },
      });

      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#05080d",
          "line-width": ["case", ["==", ["get", "selected"], 1], 10, 7],
          "line-opacity": 0.85,
        },
      });

      map.addLayer({
        id: "route-line",
        type: "line",
        source: "routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["get", "color"],
          "line-width": ["case", ["==", ["get", "selected"], 1], 6, 3.5],
          "line-opacity": ["case", ["==", ["get", "selected"], 1], 1, 0.55],
        },
      });

      map.addLayer({
        id: "checkpoints",
        type: "circle",
        source: "checkpoints",
        paint: {
          "circle-radius": 6,
          "circle-color": ["get", "color"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#071018",
        },
      });

      map.addLayer({
        id: "ends",
        type: "circle",
        source: "ends",
        paint: {
          "circle-radius": 8,
          "circle-color": ["match", ["get", "kind"], "origin", "#f0b429", "#e7eef7"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#071018",
        },
      });

      map.on("mousemove", "checkpoints", (event) => {
        const feature = event.features?.[0];
        if (!feature) return;
        map.getCanvas().style.cursor = "pointer";
        const props = feature.properties ?? {};
        popup
          .setLngLat(event.lngLat)
          .setHTML(
            `<div class="popup">
              <h3>Mile ${props.mile} · ${props.level}</h3>
              <p>${props.eta}</p>
              <p>Wind ${props.wind} mph · Rain ${props.rain} in/hr · Snow ${props.snow} in/hr</p>
              <p>${props.temp === "n/a" ? "" : `${props.temp}°F · `}${props.factors}</p>
            </div>`,
          )
          .addTo(map);
      });
      map.on("mouseleave", "checkpoints", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
      map.on("click", "route-line", (event) => {
        const routeId = event.features?.[0]?.properties?.routeId;
        if (typeof routeId === "string") onSelectRef.current(routeId);
      });

      ready.current = true;
      paint(map);
      if (stateRef.current.plan) fitPlan(map, stateRef.current.plan);
      map.resize();
    };

    if (map.loaded()) onReady();
    map.on("load", onReady);
    map.on("style.load", onReady);

    return () => {
      ready.current = false;
      observer.disconnect();
      for (const marker of markersRef.current) marker.remove();
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready.current) return;
    paint(map);
  }, [plan, selectedId, hourIndex, showHeatmap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !plan) return;
    let attempts = 0;
    const tryFit = () => {
      attempts += 1;
      const live = mapRef.current;
      if (live?.getSource("routes")) {
        paint(live);
        fitPlan(live, plan);
        return;
      }
      if (attempts < 80) window.setTimeout(tryFit, 100);
    };
    tryFit();
  }, [plan]);

  return <div className="map" ref={root} />;
}

function empty() {
  return { type: "FeatureCollection" as const, features: [] };
}
