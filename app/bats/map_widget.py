"""Map extent selection widget for BAT workflow pages.

This widget lets users define an analysis area for their BAT workflow by
interactively drawing a geometry on a map.
"""

from dataclasses import dataclass

from nicegui import ui


@dataclass(frozen=True, slots=True)
class MapGeometry:
    type: str
    wkt: str


def add_map_widget() -> None:
    """Adds the "Select Analysis Area" user input widget (i.e. map)."""

    with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.label("Select Analysis Area").classes(
                "text-xl font-semibold text-gray-800"
            )
            ui.label("*").classes("required-asterisk text-xl")
        ui.label("Draw a rectangle or polygon on the map (Europe only)").classes(
            "text-sm text-gray-500 mb-4"
        )

        ui.html('<div id="map"></div>', sanitize=False).classes("w-full")

        ui.button(
            "Clear Selection",
            on_click=lambda: ui.run_javascript(
                "if(window.drawnItems) { window.drawnItems.clearLayers(); window.geometryType = null; window.geometryWkt = null; var wktEl = document.getElementById('geometry-wkt'); if (wktEl) wktEl.textContent = 'WKT: None - Draw on map ->'; }"
            ),
        ).classes("mt-4 bmd-btn-secondary bmd-btn").props("icon=delete outline")


def create_wkt_label() -> None:
    """Render the WKT status label the map updates as the user draws."""

    # id=geometry-wkt is what the map JavaScript targets.
    ui.label("WKT: None - Draw on map ->").classes(
        "text-sm text-gray-500 p-3 bg-gray-50 rounded-lg"
    ).props("id=geometry-wkt")


def init_map() -> None:
    """Initialize the Leaflet map in the browser.

    Must be called after `await client.connected()` so the `#map` element
    exists in the DOM.
    """
    ui.run_javascript(MAP_INIT_JS, timeout=5.0)


async def read_map_geometry() -> MapGeometry | None:
    """Read the area drawn on the map by the user.

    Returns None if the user has not drawn a valid area.
    """
    geometry_type = await ui.run_javascript(
        "return (window.geometryType ? window.geometryType : null);",
        timeout=5.0,
    )
    geometry_wkt = await ui.run_javascript(
        "return (window.geometryWkt ? window.geometryWkt : null);",
        timeout=5.0,
    )
    if not geometry_type or geometry_type == "null":
        return None
    if not geometry_wkt or geometry_wkt == "null":
        return None

    return MapGeometry(type=geometry_type, wkt=geometry_wkt)


# JavaScript that (re)initializes the Leaflet map and its draw controls. It is
# run once the page is connected.
# Drawing an area updates the browser globals `window.geometryType`,
# `window.geometryWkt`, and the `#geometry-wkt` label, which
# `read_map_geometry` later reads back.
MAP_INIT_JS = """
    (() => {
        const tryInit = (retries) => {
            const mapEl = document.getElementById('map');
            if (!mapEl || !window.L || !window.L.Control || !window.L.Control.Draw) {
                if (retries > 0) return setTimeout(() => tryInit(retries - 1), 100);
                return;
            }
            // Clean up stale map instances when navigating away/back to this page.
            if (window._bmdMap) {
                try {
                    window._bmdMap.off();
                    window._bmdMap.remove();
                } catch (err) {}
                window._bmdMap = null;
            }
            if (mapEl._leaflet_id) {
                try {
                    mapEl._leaflet_id = null;
                } catch (err) {}
            }

            window.geometryType = null;
            window.geometryWkt = null;

            const map = L.map('map').setView([50.0, 10.0], 4);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);

            const europeBounds = L.latLngBounds(L.latLng(34.0, -25.0), L.latLng(72.0, 45.0));
            map.setMaxBounds(europeBounds);
            map.setMinZoom(3);

            window.drawnItems = new L.FeatureGroup();
            map.addLayer(window.drawnItems);

            const drawControl = new L.Control.Draw({
                position: 'topright',
                draw: {
                    polygon: {
                        allowIntersection: false,
                        showArea: true,
                        shapeOptions: { color: '#2ECC71', fillColor: '#2ECC71', fillOpacity: 0.3 }
                    },
                    rectangle: {
                        shapeOptions: { color: '#17A2B8', fillColor: '#17A2B8', fillOpacity: 0.3 }
                    },
                    circle: false,
                    circlemarker: false,
                    marker: false,
                    polyline: false
                },
                edit: { featureGroup: window.drawnItems }
            });
            map.addControl(drawControl);

            map.on(L.Draw.Event.CREATED, function(event) {
                window.drawnItems.clearLayers();
                const layer = event.layer;
                window.drawnItems.addLayer(layer);

                const coords = layer.getLatLngs()[0].map(function(ll) {
                    return [ll.lat, ll.lng];
                });

                window.geometryType = event.layerType;
                const wktCoords = coords.map(function(c) {
                    return c[1].toFixed(6) + " " + c[0].toFixed(6);
                });
                if (wktCoords.length && wktCoords[0] !== wktCoords[wktCoords.length - 1]) {
                    wktCoords.push(wktCoords[0]);
                }
                window.geometryWkt = "POLYGON ((" + wktCoords.join(", ") + "))";
                const wktEl = document.getElementById('geometry-wkt');
                if (wktEl) wktEl.textContent = "WKT: " + window.geometryWkt;
                console.log('Geometry saved:', window.geometryData);
            });

            map.on(L.Draw.Event.DELETED, function() {
                window.geometryType = null;
                window.geometryWkt = null;
                const wktEl = document.getElementById('geometry-wkt');
                if (wktEl) wktEl.textContent = "WKT: None - Draw on map ->";
            });

            window._bmdMap = map;
            setTimeout(() => map.invalidateSize(), 50);
        };

        setTimeout(() => tryInit(50), 0);
        return true;
    })();
"""
