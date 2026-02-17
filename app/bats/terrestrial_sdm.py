"""Terrestrial SDM create workflow page."""

import json
from pathlib import Path

from fastapi.responses import RedirectResponse
from nicegui import Client, app, ui

from config import LOCAL_API_BASE_URL
from ui_common import (
    apply_bmd_theme,
    check_auth,
    create_footer,
    create_header,
    optional_label,
    required_label,
)


@ui.page("/create/terrestrial")
async def terrestrial_sdm_page(client: Client):
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    time_periods = [
        "1981-2010",
        "2011-2040",
        "2041-2070",
        "2071-2100",
    ]

    static_candidates = [
        Path(__file__).resolve().parent.parent / "static",
        Path(__file__).resolve().parent.parent.parent / "static",
    ]
    static_dir = next((p for p in static_candidates if p.exists()), static_candidates[0])
    ias_path = static_dir / "eu-ias-directive.json"
    try:
        with ias_path.open("r", encoding="utf-8") as handle:
            ias_data = json.load(handle)
    except Exception:
        ias_data = []

    ias_species_names = [
        entry.get("scientificName", "").strip()
        for entry in ias_data
        if entry.get("scientificName")
    ]
    habitat_species_names = []

    def build_species_options(selected_directives):
        options = {}
        if "invasive_species" in (selected_directives or []):
            for name in ias_species_names:
                options[name] = f"{name} <span class='species-pill'>IAS</span>"
        if "habitat" in (selected_directives or []):
            for name in habitat_species_names:
                options[name] = f"{name} <span class='species-pill'>HAB</span>"
        return options

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header("create")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        ui.label("Create New Workflow").classes("text-3xl font-bold").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )

        with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
            with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                ui.label("Workflow Parameters").classes(
                    "text-xl font-semibold mb-4 text-gray-800"
                )

                with ui.column().classes("w-full gap-1"):
                    required_label("Workflow Name")
                    name_input = (
                        ui.input(placeholder="e.g., Alpine Species Survey")
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-4"):
                    optional_label("Description")
                    desc_input = (
                        ui.textarea(placeholder="Describe your analysis...")
                        .props("outlined rows=3")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Choose EU Directive")
                    with ui.row().classes("w-full gap-4"):
                        invasive_cb = ui.checkbox(
                            "Invasive Species", value=False
                        ).props("checked-icon=check_box").classes("flex-1")
                        habitat_cb = (
                            ui.checkbox("Habitat", value=False)
                            .props("checked-icon=check_box disable")
                            .classes("flex-1")
                        )

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Species List")
                    species_select = (
                        ui.select(
                            options=build_species_options([]),
                            value=None,
                        )
                        .props("outlined use-input input-debounce=0 options-html")
                        .classes("w-full")
                    )

                def update_species_options():
                    selected = []
                    if invasive_cb.value:
                        selected.append("invasive_species")
                    if habitat_cb.value:
                        selected.append("habitat")
                    species_select.options = build_species_options(selected)
                    if species_select.value not in species_select.options:
                        species_select.value = None
                    species_select.update()

                def update_species_display():
                    species_select.props(
                        f"display-value={json.dumps(species_select.value or '')}"
                    )
                    species_select.update()

                invasive_cb.on_value_change(lambda _: update_species_options())
                habitat_cb.on_value_change(lambda _: update_species_options())
                species_select.on_value_change(lambda _: update_species_display())

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Time Period")
                    time_period_checks = []
                    for period in time_periods:
                        time_period_checks.append(
                            ui.checkbox(period, value=False).classes("w-full")
                        )

                def get_selected_time_periods():
                    return [
                        period
                        for period, checkbox in zip(time_periods, time_period_checks)
                        if checkbox.value
                    ]

                ui.label("Additional Parameters").classes(
                    "text-sm font-semibold text-gray-600 mt-4 mb-2"
                )

                with ui.row().classes("w-full gap-4 mb-4"):
                    min_obs = (
                        ui.number("Min Observations", value=10)
                        .props("outlined")
                        .classes("flex-1")
                    )
                    confidence = ui.slider(min=0, max=100, value=80).classes("flex-1")
                    ui.label().bind_text_from(
                        confidence, "value", lambda v: f"Confidence: {v}%"
                    )

                include_historical = ui.checkbox("Include historical data", value=True)
                generate_report = ui.checkbox("Generate PDF report", value=True)

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Selected Area")
                    ui.label("WKT: None - Draw on map ->").classes(
                        "text-sm text-gray-500 p-3 bg-gray-50 rounded-lg"
                    ).props("id=geometry-wkt")

                async def submit_workflow():
                    if not name_input.value:
                        ui.notify("Please enter a workflow name", type="warning")
                        return

                    directive_values = []
                    if invasive_cb.value:
                        directive_values.append("invasive_species")
                    if habitat_cb.value:
                        directive_values.append("habitat")

                    if not directive_values:
                        ui.notify("Please choose an EU directive", type="warning")
                        return
                    if not species_select.value:
                        ui.notify("Please select a species", type="warning")
                        return
                    selected_time_periods = get_selected_time_periods()
                    if not selected_time_periods:
                        ui.notify("Please select a time period", type="warning")
                        return

                    geo_type = await ui.run_javascript(
                        "return (window.geometryType ? window.geometryType : null);",
                        timeout=5.0,
                    )
                    geo_wkt = await ui.run_javascript(
                        "return (window.geometryWkt ? window.geometryWkt : null);",
                        timeout=5.0,
                    )

                    if not geo_type or geo_type == "null":
                        ui.notify("Please draw an area on the map", type="warning")
                        return
                    if not geo_wkt or geo_wkt == "null":
                        ui.notify("Geometry WKT not available", type="warning")
                        return

                    token = app.storage.user.get("token")
                    workflow_payload = {
                        "name": name_input.value,
                        "description": desc_input.value or "",
                        "species_name": species_select.value,
                        "ecosystem_type": "terrestrial",
                        "geometry_type": geo_type,
                        "geometry_wkt": geo_wkt,
                        "parameters": {
                            "min_observations": min_obs.value,
                            "confidence_threshold": confidence.value,
                            "time_period": ";".join(selected_time_periods),
                            "directive_types": directive_values,
                            "include_historical": include_historical.value,
                            "generate_report": generate_report.value,
                        },
                    }

                    import httpx

                    async with httpx.AsyncClient() as http_client:
                        try:
                            response = await http_client.post(
                                f"{LOCAL_API_BASE_URL}/api/workflows/submit",
                                json=workflow_payload,
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            if response.status_code == 200:
                                result = response.json()
                                ui.notify(
                                    f'Workflow submitted! ID: {result["workflow_id"][:8]}...',
                                    type="positive",
                                )
                                ui.run_javascript(
                                    "if(window.drawnItems) window.drawnItems.clearLayers();",
                                    timeout=5.0,
                                )
                                ui.navigate.to("/workflows")
                            else:
                                ui.notify(f"Error: {response.text}", type="negative")
                        except Exception as exc:
                            ui.notify(f"Error: {str(exc)}", type="negative")

                ui.button("Submit Workflow", on_click=submit_workflow).classes(
                    "w-full bmd-btn text-lg py-3 mt-6"
                ).props("icon=send")

            with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label("Select Analysis Area").classes(
                        "text-xl font-semibold text-gray-800"
                    )
                    ui.label("*").classes("required-asterisk text-xl")
                ui.label(
                    "Draw a rectangle or polygon on the map (Europe only)"
                ).classes("text-sm text-gray-500 mb-4")

                ui.html('<div id="map"></div>', sanitize=False).classes("w-full")

                ui.button(
                    "Clear Selection",
                    on_click=lambda: ui.run_javascript(
                        "if(window.drawnItems) { window.drawnItems.clearLayers(); window.geometryType = null; window.geometryWkt = null; var wktEl = document.getElementById('geometry-wkt'); if (wktEl) wktEl.textContent = 'WKT: None - Draw on map ->'; }"
                    ),
                ).classes("mt-4 bmd-btn-secondary bmd-btn").props("icon=delete outline")

    await client.connected()
    ui.run_javascript(
        """
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
    """,
        timeout=5.0,
    )
    create_footer()
