"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection, Point } from "geojson";
import type {
  DataDrivenPropertyValueSpecification,
  FilterSpecification,
  MapGeoJSONFeature,
  MapMouseEvent,
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

// Vector tiles from /api/regions/tiles/{z}/{x}/{y}.mvt have two layers: countries and their
// first-level regions (oblasts).
const SOURCE = "regions";
const COUNTRIES_LAYER = "countries";
const REGIONS_LAYER = "regions";
// From this zoom on, regions (and their dialect words) replace their country.
const REGIONS_MIN_ZOOM = 5;

export type SelectedRegion = { code: string; name: string; parentCode: string | null };

type RegionProps = {
  code: string;
  name_en: string;
  name_uk: string | null;
  parent_code?: string | null;
};

// Minimum free space between two visible word labels, in pixels.
const LABEL_GAP = 2;

// Fill opacity that brightens the feature under the cursor.
const hoverOpacity = (base: number): DataDrivenPropertyValueSpecification<number> => [
  "case",
  ["boolean", ["feature-state", "hover"], false],
  0.3,
  base,
];

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
  onSelectRegion: (region: SelectedRegion) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const markerClassRef = useRef<typeof Marker | null>(null);
  const onSelectRef = useRef(onSelectRegion);
  const locale = useLocale();
  const localeRef = useRef(locale);
  const [loaded, setLoaded] = useState(false);
  const [hovered, setHovered] = useState<RegionProps | null>(null);

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
        m.addSource(SOURCE, {
          type: "vector",
          tiles: [`${API_URL}/api/regions/tiles/{z}/{x}/{y}.mvt`],
          maxzoom: 10,
        });
        m.addLayer({
          id: "countries-fill",
          type: "fill",
          source: SOURCE,
          "source-layer": COUNTRIES_LAYER,
          paint: { "fill-color": "#94a3b8", "fill-opacity": hoverOpacity(0.05) },
        });
        m.addLayer({
          id: "countries-highlight",
          type: "fill",
          source: SOURCE,
          "source-layer": COUNTRIES_LAYER,
          filter: codeFilter([]),
          paint: { "fill-color": "#2563eb", "fill-opacity": 0.35 },
        });
        m.addLayer({
          id: "regions-fill",
          type: "fill",
          source: SOURCE,
          "source-layer": REGIONS_LAYER,
          minzoom: REGIONS_MIN_ZOOM,
          paint: { "fill-color": "#94a3b8", "fill-opacity": hoverOpacity(0) },
        });
        m.addLayer({
          id: "regions-highlight",
          type: "fill",
          source: SOURCE,
          "source-layer": REGIONS_LAYER,
          minzoom: REGIONS_MIN_ZOOM,
          filter: codeFilter([]),
          paint: { "fill-color": "#7c3aed", "fill-opacity": 0.3 },
        });
        m.addLayer({
          id: "countries-line",
          type: "line",
          source: SOURCE,
          "source-layer": COUNTRIES_LAYER,
          paint: { "line-color": "#1e3a8a", "line-width": 0.6, "line-opacity": 0.5 },
        });
        m.addLayer({
          id: "regions-line",
          type: "line",
          source: SOURCE,
          "source-layer": REGIONS_LAYER,
          minzoom: REGIONS_MIN_ZOOM,
          paint: { "line-color": "#1e3a8a", "line-width": 0.4, "line-opacity": 0.4 },
        });
        for (const [id, layer] of [
          ["countries-selected", COUNTRIES_LAYER],
          ["regions-selected", REGIONS_LAYER],
        ] as const) {
          m.addLayer({
            id,
            type: "line",
            source: SOURCE,
            "source-layer": layer,
            filter: codeFilter([]),
            paint: { "line-color": "#f59e0b", "line-width": 3 },
          });
        }

        // Regions are drawn above their country, so prefer them under the cursor.
        const featureAt = (e: MapMouseEvent): MapGeoJSONFeature | undefined => {
          const layers = ["regions-fill", "countries-fill"].filter((id) => m.getLayer(id));
          return m.queryRenderedFeatures(e.point, { layers })[0];
        };

        let hovered: MapGeoJSONFeature | undefined;
        const setHover = (feature: MapGeoJSONFeature | undefined) => {
          if (hovered?.id !== undefined) {
            m.setFeatureState(
              { source: SOURCE, sourceLayer: hovered.sourceLayer, id: hovered.id },
              { hover: false },
            );
          }
          hovered = feature;
          if (feature?.id !== undefined) {
            m.setFeatureState(
              { source: SOURCE, sourceLayer: feature.sourceLayer, id: feature.id },
              { hover: true },
            );
          }
          setHovered(feature ? (feature.properties as RegionProps) : null);
          m.getCanvas().style.cursor = feature ? "pointer" : "";
        };

        m.on("mousemove", (e) => {
          const feature = featureAt(e);
          if (feature?.id !== hovered?.id || feature?.sourceLayer !== hovered?.sourceLayer) {
            setHover(feature);
          }
        });
        m.on("mouseout", () => setHover(undefined));
        m.on("click", (e) => {
          const props = featureAt(e)?.properties as RegionProps | undefined;
          if (props) {
            onSelectRef.current({
              code: props.code,
              name: localized(localeRef.current, props.name_en, props.name_uk),
              parentCode: props.parent_code || null,
            });
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
    const selected = codeFilter(selectedCode ? [selectedCode] : []);
    m.setFilter("countries-highlight", codeFilter(highlightCodes));
    m.setFilter("regions-highlight", codeFilter(highlightCodes));
    m.setFilter("countries-selected", selected);
    m.setFilter("regions-selected", selected);
  }, [loaded, highlightCodes, selectedCode]);

  useEffect(() => {
    const m = mapRef.current;
    const MarkerClass = markerClassRef.current;
    if (!loaded || !m || !MarkerClass) return;

    const features = labels?.features ?? [];
    // Countries whose regions have their own labels: zooming in swaps the country label for them.
    const countriesWithRegions = new Set(
      features.filter((f) => f.properties.level === "adm1").map((f) => f.properties.parent_code),
    );

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = features.map((feature) => {
      const { code, text, level, dialect } = feature.properties;
      // HTML labels render every script (Hebrew, Georgian, CJK, ...) with the browser's fonts.
      const el = document.createElement("div");
      el.textContent = text;
      el.className = `max-w-40 truncate rounded px-1.5 py-0.5 text-xs font-semibold shadow cursor-pointer ${
        dialect ? "bg-violet-100 text-violet-950" : "bg-white/90 text-black"
      }`;
      el.title = text;
      el.dataset.code = code;
      el.dataset.level = level;
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        const { name_en, name_uk, parent_code } = feature.properties;
        onSelectRef.current({
          code,
          name: localized(localeRef.current, name_en, name_uk),
          parentCode: parent_code,
        });
      });
      const [lng, lat] = feature.geometry.coordinates;
      return new MarkerClass({ element: el }).setLngLat([lng, lat]).addTo(m);
    });

    // Labels arrive ordered by importance; hide any label that would overlap a more
    // important one. Overlaps only change with zoom, so re-check on zoom, not on pan.
    const declutter = () => {
      const zoomedIn = m.getZoom() >= REGIONS_MIN_ZOOM;
      const shown: DOMRect[] = [];
      for (const marker of markersRef.current) {
        const el = marker.getElement();
        const isRegion = el.dataset.level === "adm1";
        const replacedByRegions = !isRegion && countriesWithRegions.has(el.dataset.code ?? "");
        if (isRegion ? !zoomedIn : zoomedIn && replacedByRegions) {
          el.style.visibility = "hidden";
          continue;
        }
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
