"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { MapGeoJSONFeature, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { useLocale } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { API_URL } from "@/lib/api";

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

type CountryProps = { code: string; name_en: string; name_uk: string | null };

export default function WorldMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const locale = useLocale();
  const [hovered, setHovered] = useState<CountryProps | null>(null);

  useEffect(() => {
    let map: MapLibreMap | undefined;
    let cancelled = false;

    // maplibre-gl touches `window` on import, so load it only in the browser.
    import("maplibre-gl").then(({ Map, NavigationControl }) => {
      if (cancelled || !containerRef.current) return;
      const m = new Map({
        container: containerRef.current,
        style: OSM_STYLE,
        center: [20, 48],
        zoom: 3,
      });
      map = m;
      m.addControl(new NavigationControl(), "top-right");

      m.on("load", () => {
        m.addSource("countries", {
          type: "geojson",
          data: `${API_URL}/api/regions/countries.geojson`,
        });
        m.addLayer({
          id: "countries-fill",
          type: "fill",
          source: "countries",
          paint: {
            "fill-color": "#3b82f6",
            "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.35, 0.08],
          },
        });
        m.addLayer({
          id: "countries-line",
          type: "line",
          source: "countries",
          paint: { "line-color": "#1e3a8a", "line-width": 0.6, "line-opacity": 0.6 },
        });

        let hoveredId: string | number | undefined;
        const setHover = (feature: MapGeoJSONFeature | undefined) => {
          if (hoveredId !== undefined) {
            m.setFeatureState({ source: "countries", id: hoveredId }, { hover: false });
          }
          hoveredId = feature?.id;
          if (hoveredId !== undefined) {
            m.setFeatureState({ source: "countries", id: hoveredId }, { hover: true });
          }
          setHovered(feature ? (feature.properties as CountryProps) : null);
        };

        m.on("mousemove", "countries-fill", (e) => setHover(e.features?.[0]));
        m.on("mouseleave", "countries-fill", () => setHover(undefined));
      });
    });

    return () => {
      cancelled = true;
      map?.remove();
    };
  }, []);

  const hoveredName =
    hovered && (locale === "uk" ? (hovered.name_uk ?? hovered.name_en) : hovered.name_en);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="absolute inset-0" />
      {hoveredName && (
        <div className="pointer-events-none absolute left-3 top-3 rounded-md bg-white/90 px-3 py-1.5 text-sm text-black shadow">
          {hoveredName}
        </div>
      )}
    </div>
  );
}
