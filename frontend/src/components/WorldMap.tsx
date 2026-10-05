"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection, Point } from "geojson";
import type {
  FilterSpecification,
  MapGeoJSONFeature,
  Map as MapLibreMap,
  Marker,
  StyleSpecification,
} from "maplibre-gl";
import { useLocale } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { API_URL, type LabelProps, localized } from "@/lib/api";

const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

// Served from public/, see scripts/copy-maplibre-worker.mjs
const WORKER_URL = "/maplibre/maplibre-gl-worker.mjs";

// Layer name inside the vector tiles served by /api/regions/countries/{z}/{x}/{y}.mvt
const COUNTRIES_LAYER = "countries";

type CountryProps = { code: string; name_en: string; name_uk: string | null };

// Minimum free space between two visible word labels, in pixels.
const LABEL_GAP = 2;

const codeFilter = (codes: string[]): FilterSpecification => [
  "in",
  ["get", "code"],
  ["literal", codes],
];

export default function WorldMap({
  highlightCodes,
  labels,
  selectedCode,
  onSelectRegion,
}: {
  highlightCodes: string[];
  labels: FeatureCollection<Point, LabelProps> | null;
  selectedCode: string | null;
  onSelectRegion: (code: string, name: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const markerClassRef = useRef<typeof Marker | null>(null);
  const onSelectRef = useRef(onSelectRegion);
  const locale = useLocale();
  const localeRef = useRef(locale);
  const [loaded, setLoaded] = useState(false);
  const [hovered, setHovered] = useState<CountryProps | null>(null);

  useEffect(() => {
    onSelectRef.current = onSelectRegion;
    localeRef.current = locale;
  });

  useEffect(() => {
    let cancelled = false;

    // maplibre-gl touches `window` on import, so load it only in the browser.
    import("maplibre-gl").then(({ Map, Marker, NavigationControl, setWorkerUrl }) => {
      if (cancelled || !containerRef.current) return;
      setWorkerUrl(WORKER_URL);
      markerClassRef.current = Marker;
      const m = new Map({
        container: containerRef.current,
        style: OSM_STYLE,
        center: [20, 48],
        zoom: 3,
      });
      mapRef.current = m;
      m.addControl(new NavigationControl(), "top-right");

      m.on("load", () => {
        m.addSource("countries", {
          type: "vector",
          tiles: [`${API_URL}/api/regions/countries/{z}/{x}/{y}.mvt`],
          maxzoom: 10,
        });
        m.addLayer({
          id: "countries-fill",
          type: "fill",
          source: "countries",
          "source-layer": COUNTRIES_LAYER,
          paint: {
            "fill-color": "#94a3b8",
            "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.3, 0.05],
          },
        });
        m.addLayer({
          id: "countries-highlight",
          type: "fill",
          source: "countries",
          "source-layer": COUNTRIES_LAYER,
          filter: codeFilter([]),
          paint: { "fill-color": "#2563eb", "fill-opacity": 0.35 },
        });
        m.addLayer({
          id: "countries-line",
          type: "line",
          source: "countries",
          "source-layer": COUNTRIES_LAYER,
          paint: { "line-color": "#1e3a8a", "line-width": 0.6, "line-opacity": 0.5 },
        });
        m.addLayer({
          id: "countries-selected",
          type: "line",
          source: "countries",
          "source-layer": COUNTRIES_LAYER,
          filter: codeFilter([]),
          paint: { "line-color": "#f59e0b", "line-width": 3 },
        });

        let hoveredId: string | number | undefined;
        const setHover = (feature: MapGeoJSONFeature | undefined) => {
          if (hoveredId !== undefined) {
            m.setFeatureState({ source: "countries", sourceLayer: COUNTRIES_LAYER, id: hoveredId }, { hover: false });
          }
          hoveredId = feature?.id;
          if (hoveredId !== undefined) {
            m.setFeatureState({ source: "countries", sourceLayer: COUNTRIES_LAYER, id: hoveredId }, { hover: true });
          }
          setHovered(feature ? (feature.properties as CountryProps) : null);
          m.getCanvas().style.cursor = feature ? "pointer" : "";
        };

        m.on("mousemove", "countries-fill", (e) => setHover(e.features?.[0]));
        m.on("mouseleave", "countries-fill", () => setHover(undefined));
        m.on("click", "countries-fill", (e) => {
          const props = e.features?.[0]?.properties as CountryProps | undefined;
          if (props) {
            onSelectRef.current(
              props.code,
              localized(localeRef.current, props.name_en, props.name_uk),
            );
          }
        });
        setLoaded(true);
      });
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const m = mapRef.current;
    if (!loaded || !m) return;
    m.setFilter("countries-highlight", codeFilter(highlightCodes));
    m.setFilter("countries-selected", codeFilter(selectedCode ? [selectedCode] : []));
  }, [loaded, highlightCodes, selectedCode]);

  useEffect(() => {
    const m = mapRef.current;
    const MarkerClass = markerClassRef.current;
    if (!loaded || !m || !MarkerClass) return;

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = (labels?.features ?? []).map((feature) => {
      // HTML labels render every script (Hebrew, Georgian, CJK, ...) with the browser's fonts.
      const el = document.createElement("div");
      el.textContent = feature.properties.text;
      el.className =
        "max-w-40 truncate rounded bg-white/90 px-1.5 py-0.5 text-xs font-semibold text-black shadow cursor-pointer";
      el.title = feature.properties.text;
      el.dataset.code = feature.properties.code;
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        const { code, name_en, name_uk } = feature.properties;
        onSelectRef.current(code, localized(localeRef.current, name_en, name_uk));
      });
      const [lng, lat] = feature.geometry.coordinates;
      return new MarkerClass({ element: el }).setLngLat([lng, lat]).addTo(m);
    });

    // Labels arrive ordered by importance; hide any label that would overlap a more
    // important one. Overlaps only change with zoom, so re-check on zoom, not on pan.
    const declutter = () => {
      const shown: DOMRect[] = [];
      for (const marker of markersRef.current) {
        const el = marker.getElement();
        el.style.visibility = "visible";
        const rect = el.getBoundingClientRect();
        const overlaps = shown.some(
          (r) =>
            rect.left < r.right + LABEL_GAP &&
            rect.right + LABEL_GAP > r.left &&
            rect.top < r.bottom + LABEL_GAP &&
            rect.bottom + LABEL_GAP > r.top,
        );
        if (overlaps) el.style.visibility = "hidden";
        else shown.push(rect);
      }
    };
    declutter();
    m.on("zoomend", declutter);
    return () => {
      m.off("zoomend", declutter);
    };
  }, [loaded, labels]);

  const hoveredName = hovered && localized(locale, hovered.name_en, hovered.name_uk);

  return (
    <div className="relative h-full w-full">
      {/* Inline style: maplibre adds .maplibregl-map { position: relative } to this element,
          which would override an `absolute` class and collapse the map to zero height. */}
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      {hoveredName && (
        <div className="pointer-events-none absolute left-3 top-3 rounded-md bg-white/90 px-3 py-1.5 text-sm text-black shadow">
          {hoveredName}
        </div>
      )}
    </div>
  );
}
