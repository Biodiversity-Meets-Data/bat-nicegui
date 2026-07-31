"""Map 'Analysis Area' selection widget for BAT workflow pages.

This widget lets users define an analysis area for their BAT workflow by
interactively drawing a geometry on a map.

Note: the map itself is a client-side Leaflet component, i.e. component that
only resides in the browser. When the user draws or clears a shape, the browser
pushes the resulting geometry to the server via a NiceGUI event, so the drawn
area is available server-side.
"""

from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui
from nicegui.events import GenericEventArguments

from ui_widgets import card_header


@dataclass(frozen=True, slots=True)
class MapGeometry:
    type: str
    wkt: str


class MapWidget:
    """Interactive analysis-area map, self-contained per page/client.

    Must be instantiated once per page, inside the page handler. The map
    widget instance registers an event handler that notifies the map widget's
    parent through the `on_change` callback whenever the drawn area changes.

    Adding a map widget to a page requires 3 steps:

    1. Instantiate a new map widget. The map widget instance registers an
       event handler that notifies the map widget's parent through the
       `on_change` callback whenever the drawn area changes.
    2. Run the map widget's `build_widget()` method at the location where
       it should be placed.
    3. Run the map widget's `initialize_map_widget()` method once the
       the client (browser) has connected. This will populate the widget with
       the actual map Leaflet component.
    """

    # Client -> server event, i.e. a sort of callback that the browser's JS
    # code sends when the user draws a new geometry on the map widget.
    _EVENT = "map_geometry_change"

    def __init__(self, on_change: Callable[[MapGeometry | None], None]) -> None:
        self._geometry: MapGeometry | None = None
        self._on_change = on_change
        ui.on(self._EVENT, self._on_geometry_change)

    @property
    def geometry(self) -> MapGeometry | None:
        """The area currently drawn on the map, or None if none is drawn."""
        return self._geometry

    def _on_geometry_change(self, event: GenericEventArguments) -> None:
        """Store the geometry pushed by the browser and notify the host."""
        data = event.args
        self._geometry = (
            MapGeometry(type=data["type"], wkt=data["wkt"]) if data else None
        )
        self._on_change(self._geometry)

    # ------------------- Build and Initialize Widget ----------------------- #

    def build_widget(self) -> None:
        """Build the map widget (map + clear button)."""

        with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
            # Add widget labels.
            card_header("Select Analysis Area")
            ui.label("Draw a rectangle or polygon on the map (Europe only)").classes(
                "text-sm text-gray-500 mb-4"
            )

            # Add the map content "mount point". The map is later added into
            # this HTML container.
            ui.html('<div id="map"></div>', sanitize=False).classes("w-full")

            # Add a button to clear the drawing on the map.
            ui.button("Clear Selection", on_click=self._clear_drawing).classes(
                "mt-4 bmd-btn-secondary bmd-btn"
            ).props("icon=delete outline")

    def _clear_drawing(self) -> None:
        """Clear the drawn shape."""
        ui.run_javascript(
            "if (window.drawnItems) window.drawnItems.clearLayers();"
            f" emitEvent('{self._EVENT}', null);"
        )

    def initialize_map_widget(self) -> None:
        """Initialize the map widget in the browser.

        Note: this must be called after 'client.connected()' so that the
        '#map' element exists in the browser DOM.
        """
        ui.run_javascript(
            MAP_INIT_JS.replace("__GEOMETRY_EVENT__", self._EVENT), timeout=5.0
        )


# JavaScript that (re)initializes the Leaflet map and its draw controls. It is
# run once the page is connected. Drawing or deleting an area emits the
# `__GEOMETRY_EVENT__` event back to the server.
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
                const wktCoords = coords.map(function(c) {
                    return c[1].toFixed(6) + " " + c[0].toFixed(6);
                });
                if (wktCoords.length && wktCoords[0] !== wktCoords[wktCoords.length - 1]) {
                    wktCoords.push(wktCoords[0]);
                }
                const wkt = "POLYGON ((" + wktCoords.join(", ") + "))";
                emitEvent('__GEOMETRY_EVENT__', { type: event.layerType, wkt: wkt });
            });

            map.on(L.Draw.Event.DELETED, function() {
                emitEvent('__GEOMETRY_EVENT__', null);
            });

            window._bmdMap = map;
            setTimeout(() => map.invalidateSize(), 50);
        };

        setTimeout(() => tryInit(50), 0);
        return true;
    })();
"""
