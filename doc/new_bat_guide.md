# Developer guide: adding a new BAT to the codebase

<br>

This document describes the steps to add a new BAT (Biodiversity Analysis Tool)
to the codebase.

Before you start, please make sure to read the following documents:

* [BAT onboarding guide](bat_onboarding_guide.md): for a high-level overview
  of the BAT submission workflow.
* [bat-nicegui developer guide](dev_guide.md).

<br>

## BAT code organization

All BAT-related code lives in `app/bats/`:

* Each BAT is defined in its own `.py` module.
* The naming of BAT `.py` modules should follow the convention
  `<ecosystem category>_<bat name>.py`. For example, the BAT module for the
  CAPTAIN tool is named `terrestrial_captain.py`.
* It is mandatory that each BAT module file name starts with the category:
  `terrestrial_`, `marine_` or `freshwater_`.
* Each BAT must have a "long-form description" stored in a markdown file
  under `about/<ecosystem category>_<bat name>.md`. For instance, the
  description for the CAPTAIN tool is stored under
  `about/terrestrial_captain.md`.
* `registry.py` is the module where all BATs must be registered, i.e. the
  single source of truth.
* Other modules contain code that is shared/re-used among the BATs.

```sh
app/bats/
├── about/           # One long-form description markdown file per BAT
│   └── <bat_name>.md
├── <bat_name>.py    # One module per BAT: its parameters + its page class
├── base_page.py     # BasePage: the parent class of every BAT page.
├── map_widget.py    # Shared "Analysis Area" Leaflet map widget
├── map_data.py      # Server-side country and Natura2000 data access
├── registry.py      # Single source of truth: Bat, EcosystemCategory, BAT_REGISTRY
└── workflow.py      # Domain layer: payload, validation, submission

scripts/
└── build_natura2000_index.py  # Builds lookup-friendly Natura2000 map artifacts
```

> **✨ Notes:**
>
> * A BAT page should never depend on another BAT page, i.e. it should never
>   import another BAT page.
> * Shared modules should never import a BAT page.
> * If two BATs need the same helper, it belongs in one of the shared modules.

<br>

### BAT components

Every BAT is made of the same four components:

* **Registry entry** in `bats/registry.py`. This is where the name, category,
  label, card description, icon, and workflow template paths for the BAT are
  defined. It derives the page route and is the server-side source of truth for
  template selection.
* **About text** in `bats/about/<bat_name>.md`. This is the long-form
  description of the BAT, shown in the "About" dialogue of the BAT selection
  page.
* **Parameters class** in `bats/<bat_name>.py`. This is where the BAT's typed
  parameters are defined. It validates the parameters and serializes them for
  the API.
* **Page class** in `bats/<bat_name>.py`. A subclass of the shared base page.
  It builds the BAT-specific input widgets and collects their values.
* **Species lists** are configured on the registry entry when the BAT needs a
  species selector. The shared base page loads the selected lists, merges
  duplicate `colId` values, and displays searchable scientific names with list
  pills.

* **Workflow templates** in `app/templates/<template-name>/`. Each
  submit-ready BAT must provide its own `workflow.yaml` and
  `ro-crate-metadata.json` files.

### Workflow and RO-Crate templates

Template selection is configured in the BAT registry, not in the API request
and not by passing filesystem paths from the browser. Register paths relative
to `app/templates`:

```py
Bat(
    name="freshwater_river_connectivity",
    category=EcosystemCategory.FRESHWATER,
    label="River Connectivity",
    description="Assess barriers to fish migration",
    icon="water_drop",
    workflow_yaml_path="freshwater-river-connectivity/workflow.yaml",
    rocrate_path="freshwater-river-connectivity/ro-crate-metadata.json",
)
```

The page's registry name is sent as `bat_name` with each workflow submission.
The backend resolves that name through `BAT_REGISTRY`, verifies that both
registered files exist beneath `app/templates`, and packages exactly these two
files in the RO-Crate ZIP. Do not expose absolute paths or accept template
paths from user input.

The `BasePage` submission flow adds `bat_name` automatically from the page's
`BAT` registry entry. BAT-specific runtime values continue to be sent through
the workflow API parameters, so the template files should define the
appropriate Argo parameter names and container arguments.

If a BAT has no template paths configured, it remains visible in the registry
but submission is rejected with a configuration error. This is the current
state of CAPTAIN; add its two template files and registry paths before making
it submit-ready.

### Configuring the shared species selector

The updated species assets in `static/` use records with `colId` and
`scientificName`. Configure the lists in `bats/registry.py`; do not load JSON
files directly from an individual BAT page:

```py
from species import ALL_SELECTABLE_SPECIES_LISTS

Bat(
    name="terrestrial_sdm",
    category=EcosystemCategory.TERRESTRIAL,
    label="Species Distribution Modeling",
    description="Predict suitable habitats for terrestrial species",
    icon="pin_drop",
    species_lists=ALL_SELECTABLE_SPECIES_LISTS,
)
```

Use a tuple of selected `SpeciesList` values instead when a BAT should expose
only a subset. Leave the default empty tuple for BATs that do not accept a
species. The selector searches scientific names and `colId`, shows all list
memberships as pills, and keeps both values: `species_name` is the scientific
name stored in the local database, while `species_col_id` is the Catalogue of
Life identifier sent as the external workflow's `param-target_species` value.

The currently selectable assets and their directive filters are:

| Checkbox label | Directive key | JSON assets |
| --- | --- | --- |
| Invasive Species Regulations | `invasive_species` | `Invasive_Alien_Species_of_Union_Concern.json` |
| Habitats | `habitat` | `Habitats_Directive_Annex_II.json`, `Habitats_Directive_Annex_IV.json`, `Habitats_Directive_Annex_V.json`, `Habitats_Directive_Characteristic_Species_Annex_I.json` |
| Bird | `bird` | `Birds_Directive_Annex_I.json`, `Birds_Directive_Annex_II.json`, `Birds_Directive_Annex_III.json` |

`GRIIS_Combined.json`, `Harmonized_Directive_Species_List.json`, and the
legacy `eu-ias-directive.json` are not selectable through this shared
selector. A BAT can expose only selected directive lists by configuring a
tuple explicitly:

```py
from species import SpeciesList

species_lists=(
    SpeciesList.IAS_UNION_CONCERN,
    SpeciesList.HABITATS_ANNEX_IV,
)
```

The page's directive controls filter that configured tuple. If a species is
present in more than one enabled asset, it appears once and receives one pill
for every matching asset. Pill colors identify the directive family: red for
Invasive Species Regulations, blue shades for Habitats annexes, and purple
shades for Bird annexes. The shared selector is rendered by `BasePage`; a BAT
page should not load these JSON files or build a second species dropdown.

Species assets must contain records in this shape:

```json
{
  "colId": "9606",
  "scientificName": "Homo sapiens"
}
```

<br>

### What the base page already does for you

[`BasePage`](../app/bats/base_page.py) owns everything that is common to all
BATs, so a new BAT only supplies its own parameters. You inherit:

* The page skeleton (two-column layout, page title, card styling).
* The shared inputs: workflow name, description, and analysis area.
* The map widget, its geometry callback, and the "Clear Selection" button.
* The "Submit Workflow" button, the validation/submission flow, and turning a
  validation error into a user notification.
* Route registration and the authentication guard (unauthenticated visitors
  are redirected to the login page).

The map selection methods are configured on the BAT registry entry. Each BAT
can enable any combination of drawing, country selection, and Natura2000 site
selection:

```py
from bats.map_widget import MapSelectionMode

Bat(
    name="freshwater_river_connectivity",
    category=EcosystemCategory.FRESHWATER,
    label="River Connectivity",
    description="Assess barriers to fish migration",
    icon="water_drop",
    map_selection_modes=frozenset(
        {
            MapSelectionMode.DRAW,
            MapSelectionMode.COUNTRY,
            MapSelectionMode.NATURA2000,
        }
    ),
)
```

Every method produces the same `MapGeometry` callback value and therefore the
same `geometry_wkt` workflow field. Selecting a country or Natura2000 site
replaces the current map selection, just as drawing a new shape does.

Country and Natura2000 data are read server-side from S3. Configure the
following environment variables when running a deployment:

```sh
AWS_BUCKET_NAME=your-bucket
AWS_REGION=eu-north-1
AWS_COUNTRIES_KEY=countries/countries.parquet
AWS_NATURA_INDEX_KEY=natura2000/index/sites.parquet
AWS_NATURA_GEOMETRY_PREFIX=natura2000
```

The raw Natura2000 polygon object is large and is not scanned during user
interaction. A maintainer or external data pipeline must first generate the
lookup-friendly index and per-site GeoJSON objects:

```sh
uv run python scripts/build_natura2000_index.py \
  --output-dir ./data/natura2000-map \
  --upload-prefix natura2000
```

The script loads `AWS_BUCKET_NAME` and the AWS credentials from the local
`.env` file. Alternatively, export the variables in the shell and pass
`--bucket` explicitly.

The script reads
`natura2000/Natura2000_end2024/NaturaSite_polygon.parquet`, writes
`sites.parquet` and one `geometries/<SITECODE>.geojson` file per site, and can
publish them under the configured S3 prefix. The application uses the index for
search and fetches only the selected site's geometry.

<br>
<br>

## Step-by-step: adding a new BAT to the codebase

Here we illustrate how to add a new BAT using a fictional BAT called
"River Connectivity", in the category "Freshwater".

### 1. Register the new BAT in `bats/registry.py`

Add an entry for the new BAT to `BAT_REGISTRY` in `bats/registry.py`:

```py
BAT_REGISTRY: tuple[Bat, ...] = (
    ...
    Bat(
        name="freshwater_river_connectivity",
        category=EcosystemCategory.FRESHWATER,
        label="River Connectivity",
        description="Assess barriers to fish migration",
        icon="water_drop",
        workflow_yaml_path="freshwater-river-connectivity/workflow.yaml",
        rocrate_path="freshwater-river-connectivity/ro-crate-metadata.json",
    ),
)
```

* The **`name`** field must be a unique name that identifies the new BAT:
  * It must start with the name of the BAT's category, i.e. one of
    `terrestrial_`, `marine_` or `freshwater_`.
  * The name will have to correspond to the BAT's python module file, in
    ou example `bats/freshwater_river_connectivity.py` (see the next step).
    Therefore, the bat name should be all in **lower case**, and use only
    **`_` (underscores)** as separator (no space).

* The **`category`** field must match the category prefix used in the name. It
  determines the ecosystem tab under which the BAT's card is displayed, and,
  together with the name, derives the **page route** (URL) of the new BAT:
  the category prefix is stripped from the name, so that our example BAT is
  served at `/bat/freshwater/river_connectivity`.

* **`label`** and **`description`** are what the user sees on the BAT card of
  the workflow selection page — keep the description short.

* **`icon`** is the symbol used for your BAT on its card in the workflow
  selection page. It must be the name of an existing
  [Material icon](https://fonts.google.com/icons).

<br>

### 2. Create a module for the new BAT

1. Create a new module file for the BAT under
   `app/bats/freshwater_river_connectivity.py`. The module name must match
   the `name` of the BAT as defined in the BAT registry (see step 1 above).

   The easiest approach is to copy an existing BAT module and then adapt it.

2. In the BAT module, create a class that inherits from `BasePage`. You can
   name it as you like, but we suggest that it has a `Page` suffix.

    ```py
    class FreshwaterConnectivityPage(BasePage):

        BAT = get_bat_by_name("freshwater_river_connectivity")

        def add_specific_parameters(self) -> None:
            """Add the BAT-specific parameters (user-input widgets) to the page."""
            ...

        def get_specific_parameters(self) -> FreshwaterConnectivityParameters:
            """Collect BAT-specific user inputs."""
            ...

    FreshwaterConnectivityPage.register()
    ```

    This is the class that will be used to build the user-input page for our
    new BAT. It must define at least the class attribute and the two methods
    shown in the example above.

    * **`BAT`:** class attribute that links the page to the BAT's registry
      entry (`get_bat_by_name` is imported from `bats.registry`). The base page
      uses it to derive the page's route and the workflow's ecosystem type.
      The lookup raises an error if the BAT is not in the registry.

    * **`add_specific_parameters`:** method that adds the user input widgets
      that are BAT-specific (i.e. not shared with other BATs). The method is
      called when the page is built. Store each input widget that will have to
      be read later as an instance attribute (`self.<widget name>`) of the
      `FreshwaterConnectivityPage` class.

    * **`get_specific_parameters`:** method to collect/read the user input from
      the BAT-specific user inputs. The method is called when the user submits
      the BAT workflow. The method should read the widgets and return an object
      of the class `FreshwaterConnectivityParameters` (in our example). It
      should not perform validation itself, as this is done by the
      `FreshwaterConnectivityParameters` class (see below).

    At the bottom of the BAT module, we must call the `.register()` method
    of `FreshwaterConnectivityPage` so that the page gets registered when the
    application is started.

3. Create a class that inherits from `BatSpecificParameters`. This is a
   dataclass that contains all the workflow parameters (arguments) that are
   specific to our new BAT.

    ```py
    @dataclass(frozen=True, slots=True, kw_only=True)
    class FreshwaterConnectivityParameters(BatSpecificParameters):

        def validate_input(self) -> None:
            """Validate the BAT-specific user inputs and raise a
            WorkflowValidationError if input is invalid.
            """

            if not self.directive_types:
                raise WorkflowValidationError("Please choose an EU directive")

        def to_api_parameters(self) -> dict[str, Any]:
            """Serialize to the "parameters" dict POSTed to /api/workflows/submit.

            Key order is part of the wire/DB contract and must stay stable.
            """
            ...
    ```

   The `FreshwaterConnectivityParameters` class must implement the following
   two methods:

   * **`validate_input`:** a method that validates all BAT-specific
     parameters. If a check fails, a `WorkflowValidationError` should be
     raised, with a message intended for the user. If all checks pass, the
     method simply returns without raising.

   * **`to_api_parameters`:** a method that serializes the BAT-specific
     parameters to a `dict`. This `dict` is what gets POSTed to the workflow
     submission API and stored in the database.

<br>

### 3. Add a description in `bats/about/`

Create a file `app/bats/about/freshwater_river_connectivity.md` — the file's
name must match the name in the registry (which also matches the name of the
BAT's python module).

The file should contain a description of your BAT, and its content is rendered
in the **"About" dialogue** of the BAT card. The description should typically
be a summary of the BAT's main features and its typical use cases.

> **✨ Note:** the test suite checks that every registered BAT has a readable,
> non-empty about file. A missing or misnamed about file will cause the CI/CD
> checks to fail.

<br>
<br>

## Running the app and CI/CD checks

Run the app locally and open the new page:

```bash
export DATABASE_PATH="./data/bmd.db"
uv run -- uvicorn main:fastapi_app --reload --app-dir app
```

Check that the BAT card appears under the right category tab on
`/select-workflow`, that its "About" dialogue renders, and that clicking the
card opens the new BAT page - `/bat/freshwater/river_connectivity` in our
example. Then check that the page submits, including that each invalid input
produces the notification you expect.

Then run the checks that CI runs. All must be clean:

```bash
uv run ruff check           # Lint.
uv run ruff format --check  # Formatting (run `uv run ruff format` to fix).
uv run mypy                 # Type check (strict over app/).
uv run pytest               # Unit tests.
```

<br>
<br>

## Best practices

### Widgets

* **Use the shared UI widgets.** To ensure visual consistency across the
  application, you should use the UI widgets defined in `ui_widgets.py` rather
  than redefining them on your own.

  If a widget is missing, feel free to add it to `ui_widgets.py`. Only
  genuinely BAT-specific widgets should be kept in a BAT's module.

* **Model closed sets of choices as an `Enum`.** Pair it with `drop_down_menu`,
  which builds the options from the enum members, and serialize the member
  value in the parameters dict. An invalid choice then cannot even be
  constructed, rather than having to be caught by validation after the fact.

### General considerations

* **Keep domain logic out of the UI layer.** Validation, serialization and any
  computation live in the parameters class or in `workflow.py`; the page class
  only builds widgets and reads them. Code that does not touch `ui` is code you
  can unit-test.

* **Prefer NiceGUI APIs over raw JavaScript.** Use `ui.query(...)` and element
  methods rather than `ui.run_javascript(...)`; reserve raw JS for genuinely
  client-only components (the Leaflet map is the one case in this codebase).

* **Follow the project's typing and naming conventions.** Modern type hints
  (`X | None`, `list[str]`), every function annotated, `mypy --strict` clean.
  Names: module and registry name in `snake_case` with the category prefix,
  classes as `<Bat>Parameters` and `<Bat>Page`.

* **Write docstrings that survive renames.** Describe a member's role rather
  than naming the specific methods or symbols it relies on.

* **Add tests for what you can test without a browser.** Tests live in the
  top-level `tests/` directory and import app modules the way the app does
  (no `app.` prefix). Parameter validation and serialization are the natural
  targets: one test per rejected input, one asserting the serialized dict.

* **Commit with a Conventional-Commit prefix.** A new BAT is a `feat:`. CI
  derives semantic versions from these prefixes.
