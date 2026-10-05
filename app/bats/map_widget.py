"""Configurable map-based analysis-area selection for BAT workflow pages."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any, cast
from uuid import uuid4

from nicegui import ui
from nicegui.events import GenericEventArguments
from shapely.geometry import mapping  # type: ignore[import-untyped]
from shapely.wkt import loads  # type: ignore[import-untyped]

from bats.map_data import MapDataError, MapFeature, get_map_data_store
from bats.natura_metadata import (
    NaturaMetadataError,
    fetch_natura_site_metadata,
    natura_metadata_rows,
)
from ui_widgets import card_header


class MapSelectionMode(StrEnum):
    """Ways a user can select an analysis area."""

    DRAW = "draw"
    COUNTRY = "country"
    NATURA2000 = "natura2000"

    @property
    def label(self) -> str:
        """Human-readable mode label."""
        return {
            MapSelectionMode.DRAW: "Draw area",
            MapSelectionMode.COUNTRY: "Select country",
            MapSelectionMode.NATURA2000: "Select Natura2000 site",
        }[self]


@dataclass(frozen=True, slots=True)
class MapGeometry:
    type: str
    wkt: str


def wkt_to_geojson(geometry_wkt: str) -> dict[str, Any]:
    """Convert a workflow WKT geometry into a Leaflet-compatible object."""
    geometry = loads(geometry_wkt)
    return cast(dict[str, Any], mapping(geometry))


def add_readonly_aoi_map(geometry_wkt: str | None) -> None:
    """Add a fixed-size, non-editable map preview for a workflow AOI."""
    if not geometry_wkt:
        ui.label("No area of interest available.").classes("text-sm text-gray-500")
        return

    try:
        geojson = wkt_to_geojson(geometry_wkt)
    except (TypeError, ValueError):
        ui.label("Area of interest unavailable.").classes("text-sm text-gray-500")
        return

    map_id = f"bmd-aoi-map-{uuid4().hex}"
    ui.html(
        f'<div id="{map_id}" style="height: 190px; width: 100%;"></div>',
        sanitize=False,
    ).classes("w-full overflow-hidden rounded")

    def initialize() -> None:
        ui.run_javascript(
            READONLY_AOI_MAP_INIT_JS.replace("__MAP_ID__", json.dumps(map_id)).replace(
                "__GEOJSON__", json.dumps(geojson)
            ),
            timeout=5.0,
        )

    ui.timer(0.1, initialize, once=True)


class MapWidget:
    """Interactive analysis-area map with configurable selection methods."""

    def __init__(
        self,
        on_change: Callable[[MapGeometry | None], None],
        selection_modes: frozenset[MapSelectionMode] | None = None,
    ) -> None:
        self._geometry: MapGeometry | None = None
        self._on_change = on_change
        self._selection_modes = (
            frozenset(MapSelectionMode) if selection_modes is None else selection_modes
        )
        self._event = f"map_geometry_change_{uuid4().hex}"
        self._map_id = f"bmd-map-{uuid4().hex}"
        self._data_store = get_map_data_store()
        self._mode_selector: ui.radio | None = None
        self._country_select: ui.select | None = None
        self._natura_select: ui.select | None = None
        self._metadata_button: ui.button | None = None
        self._country_container: Any = None
        self._natura_container: Any = None
        self._metadata_dialog: ui.dialog | None = None
        self._metadata_content: ui.column | None = None
        self._metadata_title: ui.label | None = None
        self._metadata_site_code: str | None = None
        self._metadata_request_id = 0
        ui.on(self._event, self._on_geometry_change)

    @property
    def geometry(self) -> MapGeometry | None:
        """The currently selected analysis area, or ``None``."""
        return self._geometry

    def _on_geometry_change(self, event: GenericEventArguments) -> None:
        """Store geometry pushed by the browser and notify the host page."""
        data = event.args
        if not data:
            self._geometry = None
        else:
            self._geometry = MapGeometry(
                type=str(data.get("type", "polygon")), wkt=str(data["wkt"])
            )
            self._clear_feature_selects()
        self._on_change(self._geometry)

    def build_widget(self) -> None:
        """Build the selection controls and map mount point."""
        with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
            card_header("Select Analysis Area")
            ui.label(
                "Choose a method, then select or draw an area (Europe only)"
            ).classes("text-sm text-gray-500 mb-4")

            if len(self._selection_modes) > 1:
                options = {mode.value: mode.label for mode in self._ordered_modes()}
                self._mode_selector = (
                    ui.radio(options=options, value=next(iter(options)))
                    .props("inline")
                    .classes("mb-4")
                )
                self._mode_selector.on_value_change(self._on_mode_change)

            with ui.column().classes("w-full gap-2 mb-4") as country_container:
                if MapSelectionMode.COUNTRY in self._selection_modes:
                    self._country_select = (
                        ui.select(options=self._load_country_options(), label="Country")
                        .props("outlined use-input input-debounce=200 clearable")
                        .classes("w-full")
                    )
                    self._country_select.on_value_change(self._on_country_selected)

            with ui.column().classes("w-full gap-2 mb-4") as natura_container:
                if MapSelectionMode.NATURA2000 in self._selection_modes:
                    with ui.row().classes("w-full items-end gap-2"):
                        self._natura_select = (
                            ui.select(
                                options=self._load_natura_options(),
                                label="Natura2000 site",
                            )
                            .props("outlined use-input input-debounce=300 clearable")
                            .classes("flex-1 min-w-0")
                        )
                        self._metadata_button = ui.button(
                            icon="info", on_click=self._open_selected_natura_metadata
                        ).props('flat round aria-label="Show site metadata"')
                        self._metadata_button.tooltip(
                            "Select a Natura2000 site to view its metadata"
                        )
                        self._metadata_button.disable()
                    self._natura_select.on_value_change(self._on_natura_selected)

            self._country_container = country_container
            self._natura_container = natura_container
            self._build_natura_metadata_dialog()
            if self._mode_selector is not None:
                self._set_mode_visibility()
            else:
                country_container.set_visibility(
                    MapSelectionMode.COUNTRY in self._selection_modes
                )
                natura_container.set_visibility(
                    MapSelectionMode.NATURA2000 in self._selection_modes
                )

            ui.html(
                f'<div id="{self._map_id}" '
                'style="height: 500px; min-height: 400px; width: 100%;"></div>',
                sanitize=False,
            ).classes("w-full")
            ui.button("Clear Selection", on_click=self._clear_drawing).classes(
                "mt-4 bmd-btn-secondary bmd-btn"
            ).props("icon=delete outline")

    def _ordered_modes(self) -> tuple[MapSelectionMode, ...]:
        """Return enabled modes in a stable, user-facing order."""
        return tuple(mode for mode in MapSelectionMode if mode in self._selection_modes)

    def _load_country_options(self) -> dict[str, str]:
        try:
            return self._data_store.country_options()
        except MapDataError as exc:
            ui.notify(str(exc), type="negative")
            return {}

    def _load_natura_options(self) -> dict[str, str]:
        try:
            return self._data_store.natura_options()
        except MapDataError as exc:
            ui.notify(str(exc), type="negative")
            return {}

    def _on_mode_change(self, _: Any) -> None:
        """Show only the controls for the active selection mode."""
        self._set_mode_visibility()
        if self._mode_selector is not None:
            ui.run_javascript(
                f"window.bmdSetMapInteraction({json.dumps(self._map_id)}, "
                f"{json.dumps(self._mode_selector.value == MapSelectionMode.DRAW.value)});"
            )

    def _set_mode_visibility(self) -> None:
        if self._mode_selector is None:
            return
        selected = self._mode_selector.value
        self._country_container.set_visibility(
            selected == MapSelectionMode.COUNTRY.value
        )
        self._natura_container.set_visibility(
            selected == MapSelectionMode.NATURA2000.value
        )

    def _on_country_selected(self, event: Any) -> None:
        """Apply the selected country geometry to the map."""
        identifier = event.value
        if not identifier:
            return
        try:
            self._apply_feature(self._data_store.country(str(identifier)))
        except MapDataError as exc:
            ui.notify(str(exc), type="negative")

    async def _on_natura_selected(self, event: Any) -> None:
        """Fetch and apply the selected Natura2000 site geometry."""
        identifier = event.value
        if self._metadata_button is not None:
            self._metadata_button.set_enabled(bool(identifier))
        if not identifier:
            return
        try:
            feature = await asyncio.to_thread(
                self._data_store.natura_site, str(identifier)
            )
            self._apply_feature(feature)
        except MapDataError as exc:
            ui.notify(str(exc), type="negative")

    def _build_natura_metadata_dialog(self) -> None:
        """Create the shared dialog used to display one site's metadata."""
        with (
            ui.dialog() as dialog,
            ui.card().classes(
                "bmd-card w-full max-w-2xl max-h-[85vh] overflow-hidden p-5 sm:p-6"
            ),
        ):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                self._metadata_title = ui.label("Natura2000 site metadata").classes(
                    "text-xl font-semibold"
                )
                ui.button(icon="close", on_click=dialog.close).props(
                    'flat round dense aria-label="Close metadata"'
                )
            self._metadata_content = ui.column().classes(
                "w-full gap-3 overflow-y-auto pr-1"
            )
        self._metadata_dialog = dialog

    def _show_metadata_loading(self) -> None:
        """Render animated placeholders while the site metadata is loading."""
        if self._metadata_content is None:
            return
        self._metadata_content.clear()
        with self._metadata_content:
            for index in range(6):
                with ui.column().classes("w-full gap-2"):
                    ui.skeleton(
                        type="text", width="8rem", height="0.9rem", animation="wave"
                    )
                    ui.skeleton(
                        type="text",
                        width="100%" if index == 5 else "70%",
                        height="1.1rem" if index == 5 else "0.9rem",
                        animation="wave",
                    )

    async def _open_selected_natura_metadata(self) -> None:
        """Open the metadata dialog for the currently selected site."""
        if self._natura_select is None:
            return
        site_code = self._natura_select.value
        if not isinstance(site_code, str) or not site_code.strip():
            return
        self._metadata_site_code = site_code.strip()
        self._metadata_request_id += 1
        request_id = self._metadata_request_id
        if self._metadata_title is not None:
            self._metadata_title.text = f"Natura2000 site {self._metadata_site_code}"
        self._show_metadata_loading()
        if self._metadata_dialog is not None:
            self._metadata_dialog.open()
        await self._load_natura_metadata(self._metadata_site_code, request_id)

    async def _retry_natura_metadata(self) -> None:
        """Retry loading metadata for the site currently shown in the dialog."""
        if self._metadata_site_code is None:
            return
        self._metadata_request_id += 1
        request_id = self._metadata_request_id
        self._show_metadata_loading()
        await self._load_natura_metadata(self._metadata_site_code, request_id)

    async def _load_natura_metadata(self, site_code: str, request_id: int) -> None:
        """Fetch metadata and replace the loading or error view with its result."""
        try:
            metadata = await fetch_natura_site_metadata(site_code)
        except NaturaMetadataError:
            if request_id != self._metadata_request_id:
                return
            self._show_metadata_error()
            return

        if request_id != self._metadata_request_id:
            return
        self._show_metadata_values(metadata)

    def _show_metadata_error(self) -> None:
        """Render a retry action when metadata retrieval fails."""
        if self._metadata_content is None:
            return
        self._metadata_content.clear()
        with self._metadata_content:
            ui.label("Site metadata could not be loaded. Please try again.").classes(
                "text-sm text-red-700"
            )
            ui.button("Retry", on_click=self._retry_natura_metadata).classes(
                "bmd-btn bmd-btn-primary self-end"
            ).props("icon=refresh")

    def _show_metadata_values(self, metadata: dict[str, Any]) -> None:
        """Render site metadata as accessible label/value rows."""
        if self._metadata_content is None:
            return
        self._metadata_content.clear()
        with self._metadata_content:
            for label, value in natura_metadata_rows(metadata):
                with ui.column().classes("w-full gap-0.5"):
                    ui.label(label).classes("text-xs font-semibold text-gray-500")
                    ui.label(value).classes(
                        "text-sm text-gray-900 whitespace-pre-wrap break-words"
                    ).style("overflow-wrap: anywhere;")

    def _apply_feature(self, feature: MapFeature) -> None:
        self._geometry = MapGeometry(type=feature.geometry_type, wkt=feature.wkt)
        self._on_change(self._geometry)
        ui.run_javascript(
            f"window.bmdSetMapFeature({json.dumps(self._map_id)}, "
            f"{json.dumps(feature.geojson)});",
            timeout=5.0,
        )

    def _clear_feature_selects(self) -> None:
        if self._country_select is not None:
            self._country_select.set_value(None)
        if self._natura_select is not None:
            self._natura_select.set_value(None)
        if self._metadata_button is not None:
            self._metadata_button.disable()

    def _clear_drawing(self) -> None:
        """Clear the selected feature or drawn shape."""
        self._clear_feature_selects()
        ui.run_javascript(
            f"window.bmdClearMap({json.dumps(self._map_id)});"
            f" emitEvent('{self._event}', null);"
        )

    def initialize_map_widget(self) -> None:
        """Initialize Leaflet after the browser client has connected."""
        ui.run_javascript(
            MAP_INIT_JS.replace("__GEOMETRY_EVENT__", self._event)
            .replace("__MAP_ID__", json.dumps(self._map_id))
            .replace(
                "__DRAW_ENABLED__",
                json.dumps(MapSelectionMode.DRAW in self._selection_modes),
            )
            .replace(
                "__MAP_INTERACTIVE__",
                json.dumps(
                    MapSelectionMode.DRAW in self._selection_modes
                    and (
                        self._mode_selector is None
                        or self._mode_selector.value == MapSelectionMode.DRAW.value
                    )
                ),
            ),
            timeout=5.0,
        )


MAP_INIT_JS = """
    (() => {
        const mapId = __MAP_ID__;
        const tryInit = (retries) => {
            const mapEl = document.getElementById(mapId);
            if (!mapEl || !window.L || !window.L.map ||
                (__DRAW_ENABLED__ && (!window.L.Control || !window.L.Control.Draw))) {
                if (retries > 0) return setTimeout(() => tryInit(retries - 1), 100);
                return;
            }
            window._bmdMaps = window._bmdMaps || {};
            const previous = window._bmdMaps[mapId];
            if (previous) {
                try { previous.map.off(); previous.map.remove(); } catch (err) {}
            }

            const map = L.map(mapId).setView([50.0, 10.0], 4);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            const europeBounds = L.latLngBounds(L.latLng(34.0, -25.0), L.latLng(72.0, 45.0));
            map.setMaxBounds(europeBounds);
            map.setMinZoom(3);
            const drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);

            let drawControl = null;
            if (__DRAW_ENABLED__ && window.L.Control && window.L.Control.Draw) {
                drawControl = new L.Control.Draw({
                    position: 'topright',
                    draw: {
                        polygon: {
                            allowIntersection: false,
                            showArea: true,
                            shapeOptions: { color: '#20A683', fillColor: '#20A683', fillOpacity: 0.3 }
                        },
                        rectangle: {
                            shapeOptions: { color: '#0D969C', fillColor: '#0D969C', fillOpacity: 0.3 }
                        },
                        circle: false, circlemarker: false, marker: false, polyline: false
                    },
                    edit: { featureGroup: drawnItems }
                });
                map.addControl(drawControl);
                map.on(L.Draw.Event.CREATED, function(event) {
                    drawnItems.clearLayers();
                    const layer = event.layer;
                    drawnItems.addLayer(layer);
                    const coords = layer.getLatLngs()[0].map(function(ll) {
                        return [ll.lat, ll.lng];
                    });
                    const wktCoords = coords.map(function(c) {
                        return c[1].toFixed(6) + ' ' + c[0].toFixed(6);
                    });
                    if (wktCoords.length && wktCoords[0] !== wktCoords[wktCoords.length - 1]) {
                        wktCoords.push(wktCoords[0]);
                    }
                    emitEvent('__GEOMETRY_EVENT__', {
                        type: event.layerType,
                        wkt: 'POLYGON ((' + wktCoords.join(', ') + '))'
                    });
                });
                map.on(L.Draw.Event.DELETED, function() {
                    emitEvent('__GEOMETRY_EVENT__', null);
                });
            }

            window._bmdMaps[mapId] = {
                map: map,
                drawnItems: drawnItems,
                drawControl: drawControl,
                drawControlVisible: __DRAW_ENABLED__
            };
            window.bmdSetMapInteraction = function(id, interactive) {
                const state = window._bmdMaps[id];
                if (!state) return;
                const controls = [state.map.dragging, state.map.scrollWheelZoom,
                    state.map.doubleClickZoom, state.map.boxZoom, state.map.keyboard,
                    state.map.touchZoom];
                controls.forEach(function(control) {
                    if (control) interactive ? control.enable() : control.disable();
                });
                if (state.drawControl) {
                    if (interactive && !state.drawControlVisible) {
                        state.map.addControl(state.drawControl);
                    } else if (!interactive && state.drawControlVisible) {
                        state.map.removeControl(state.drawControl);
                    }
                    state.drawControlVisible = interactive;
                }
            };
            window.bmdClearMap = function(id) {
                const state = window._bmdMaps[id];
                if (state) state.drawnItems.clearLayers();
            };
            window.bmdSetMapFeature = function(id, geojson) {
                const state = window._bmdMaps[id];
                if (!state) return;
                state.drawnItems.clearLayers();
                const layer = L.geoJSON(geojson, {
                    style: { color: '#0D969C', fillColor: '#20A683', fillOpacity: 0.3 }
                });
                state.drawnItems.addLayer(layer);
                const bounds = layer.getBounds();
                if (bounds.isValid()) state.map.fitBounds(bounds, { padding: [20, 20] });
            };
            window.bmdSetMapInteraction(mapId, __MAP_INTERACTIVE__);
            setTimeout(() => map.invalidateSize(), 50);
        };
        setTimeout(() => tryInit(50), 0);
        return true;
    })();
"""


READONLY_AOI_MAP_INIT_JS = """
    (() => {
        const mapId = __MAP_ID__;
        const geometry = __GEOJSON__;
        const tryInit = (retries) => {
            const mapElement = document.getElementById(mapId);
            if (!mapElement || !window.L || !window.L.map) {
                if (retries > 0) return setTimeout(() => tryInit(retries - 1), 100);
                return;
            }
            const map = L.map(mapId, {
                dragging: false,
                scrollWheelZoom: false,
                doubleClickZoom: false,
                boxZoom: false,
                keyboard: false,
                touchZoom: false,
                zoomControl: true,
                attributionControl: true
            });
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            const layer = L.geoJSON(geometry, {
                style: {
                    color: '#0D969C',
                    weight: 2,
                    fillColor: '#20A683',
                    fillOpacity: 0.3
                }
            }).addTo(map);
            const bounds = layer.getBounds();
            if (bounds.isValid()) map.fitBounds(bounds, { padding: [18, 18] });
            setTimeout(() => map.invalidateSize(), 50);
        };
        tryInit(50);
    })();
"""
