# BAT onboarding guide

This document provides a short overview and references of the implementation
of BATs (Biodiversity Analysis Tools) in the BMD project.

* 📔 A glossary of acronyms and useful terms can be found
  [at the end of this document](#glossary).

</br>

## BAT workflow and technical implementation

A BAT is composed of the following elements:

* 👤 **Frontend**: a web interface where end-users can provide their input
  values and launch the BAT.
* 🤖 **Backend**: code doing the actual computation. This can e.g. by a Python
  or R script. Backend code must be containerized in a Docker container, which
  is run via the
  [ARGO workflow engine](https://argo-workflows.readthedocs.io/en/latest/quick-start).
* ⚙️ **Job configuration files**: in order to communicate inputs from the
  frontend to the backend, a BAT must define two template files:
  `ro-crate-metadata.json` and `workflow.yaml`.
* 📚 **Documentation**: explanations for the end user about what the BAT does,
  what its input arguments are, and how to interpret its output.

</br>

### 👤 Frontend

End-users interact with a BAT via a frontend (webpage) written in the
[NiceGUI](https://nicegui.io) python framework. At its simplest, the frontend
is a single webpage with input fields for the different parameters that the
user can specify for a given analysis, such as:

* Geographical extent.
* Species to model.
* Time frame for future projections.

The frontend also allows users to submit and launch their analysis, as well
as to view its output.

Practically, the frontend is implemented/deployed via a
[shared project on GitHub](https://github.com/Biodiversity-Meets-Data/bat-nicegui),
where each BAT can add their small bit of code to create their webpage where
users enter their analysis argument values.

* 🦉 Note: the encoding of the selected geographical extent should be done in
  [WKT - well known text](https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry)
  format.

</br>

### 🤖 Backend

**The backend of a BAT** is implemented as a (one or more) Docker container
that are run by the
[ARGO workflow engine](https://argo-workflows.readthedocs.io/en/latest/quick-start).

The docker containers should accept arguments/parameters that correspond to
the inputs the user provides via the NiceGUI interface.

* Example of a BAT: [bat-sdm](https://github.com/Biodiversity-Meets-Data/bat-sdm)

</br>

### ⚙️ Workflow engine and job configuration files

Since analyses offered by the different BATs are usually time and compute
intensive, they cannot be run in real time by the application's frontend.
Instead, analyses are submitted to a compute backend via the
[ARGO workflow engine](https://argo-workflows.readthedocs.io/en/latest/quick-start).

* ✨ URL of workflow engine web-interface: <http://134.94.199.13/workflows>

Once a user submits the input form of a BAT, the `bat-nicegui` app creates
a so-called [**RO-crate**](https://www.researchobject.org/ro-crate) for the
BAT. This is basically a `.zip` that contains the BAT's 2 template files:

* **`ro-crate-metadata.json`**: metadata describing the BAT's workflow: its
  name, description, author and license, as well as the list of its input
  parameters (name, type and description of each) and outputs. It describes
  the inputs, but does not contain the values entered by the user.

* **`workflow.yaml`**: config file defining the jobs to be run by the ARGO
  workflow manager. In other words, a file that indicates what are the
  different steps to run. Each step runs in a separate Docker container.

  **Artifacts** can be defined as outputs to preserve of each step, and
  these are then available to the subsequent steps of the workflow. E.g.,
  if the first step of the workflow consists in downloading data from GBIF,
  then the downloaded data can be marked as an artifact so that it becomes
  available to the next step in the workflow. Overall, this is fairly
  similar to a GitLab/GitHub CI/CD workflow.

  The `workflow.yaml` file follows the
  [ARGO workflow](https://argoproj.github.io/workflows) specifications.

Both files are selected from the BAT registry using the name of the BAT, and
are packaged unmodified into the RO-Crate: the same files are sent for every
run of a BAT. The values entered by the user are sent separately, as `param-*`
fields of the request to the workflow API.

For available workflow-related Kubernetes secrets (for example GBIF
credentials), see the [Argo Workflow Secrets Catalog](./argo-secrets-catalog.md).

To learn more about how the RO-crate are built, one function to look at is
[`build_rocrate_zip()`](https://github.com/Biodiversity-Meets-Data/bat-nicegui/blob/main/app/workflow_utils.py),
which generates the `.zip` RO-Crate.

#### How arguments are passed from frontend (niceGUI) to backend

1. A user enters their input via fields defined in the BAT frontend (each
   BAT has its own webpage in the BMD SAP - single access point - application).

   Reminder: BAT frontends use the niceGUI python framework and are hosted
   in [this project](https://github.com/Biodiversity-Meets-Data/bat-nicegui).

2. When the user submits the form, the BAT webpage sends the user input as a
   JSON request to the `/api/workflows/submit` endpoint of the
   [bat-nicegui](https://github.com/Biodiversity-Meets-Data/bat-nicegui)
   app itself. The JSON contains the BAT registry name (`bat_name`), the
   values common to all BATs (e.g. `geometry_wkt`, `species_col_id`), and two
   dicts with the BAT-specific values: `parameters` (stored in the database)
   and `workflow_parameters` (sent to ARGO, see step 4).

3. The submit endpoint uses `bat_name` to look up the BAT's template files
   (`workflow.yaml` and `ro-crate-metadata.json`) in the BAT registry, and
   packages them into an RO-Crate ZIP. **The template files are packaged
   unchanged**: no values are inserted into them at this stage.

4. The submit endpoint then sends a second request to the **workflow API**, a
   separate service that submits workflows to ARGO. This request is a
   multipart form (the same format as an HTML form with a file upload)
   containing the following fields:

   | Field              | Content                                        |
   |--------------------|------------------------------------------------|
   | `rocratefile`      | The RO-Crate ZIP file.                         |
   | `webhook_url`      | URL that ARGO calls when the run finishes.     |
   | `dry_run`, `force` | Settings of the workflow API.                  |
   | `param-<name>`     | Value of the ARGO workflow parameter `<name>`. |

   Example of `param-*` fields, for the terrestrial SDM BAT:

   ```text
   param-target_species  = 456G3
   param-climate_periods = 1981-2010;2071-2100
   param-aoi_wkt         = POLYGON ((8.74 49.21, 12.78 49.21, ...))
   ```

   The `param-` prefix is a convention of the workflow API: it separates the
   workflow input values from the fields that configure the workflow API
   itself.

   The `param-*` fields come from two sources:

   * **Values common to all BATs**, added by the submit endpoint:
     `param-aoi_wkt` (always) and `param-target_species` (only when the user
     selected a species). A BAT's `workflow.yaml` must use exactly these
     names for these values.
   * **BAT-specific values**, supplied by the BAT through its
     `to_workflow_parameters` method: each key is sent as `param-<key>`, so
     each key must match an ARGO parameter name in the BAT's `workflow.yaml`.

   A BAT also has a separate `parameters` dict (from `to_api_parameters`),
   which is stored in the database but not sent to ARGO.

5. The workflow API removes the `param-` prefix from each field and uses the
   rest as an ARGO parameter name. For each field, it replaces the default
   `value` of the parameter with that name under `spec.arguments.parameters`
   in `workflow.yaml`. It then submits the workflow to ARGO (equivalent to
   `argo submit workflow.yaml -p aoi_wkt="POLYGON (...)"`).

   ```yaml
   spec:
     arguments:
       parameters:
         - name: aoi_wkt            # set by the field "param-aoi_wkt"
           value: "POLYGON (...)"   # default value, replaced by the user value
   ```

   The parameter names in `workflow.yaml` must therefore match the names of
   the `param-*` fields exactly.

6. ARGO runs the workflow. The `{{ }}` placeholders in `workflow.yaml` are
   ARGO template expressions (not Jinja), and ARGO resolves them when it
   starts each step:

   * `{{workflow.parameters.<name>}}` is the value of a workflow parameter
     (set in the previous step). It is typically used in the main template to
     pass a value to a step as one of its inputs.
   * `{{inputs.parameters.<name>}}` is the value of an input of the current
     step. It is typically used to build the arguments of the step's
     container, e.g. `--aoi_wkt={{inputs.parameters.aoi_wkt}}`.
   * `{{steps.<step>.outputs.artifacts.<name>}}` refers to the output files
     of an earlier step, and is only resolved once that step has finished.

Summary of the whole chain:

```text
BAT webpage --▶ JSON --▶ bat-nicegui /api/workflows/submit
                          │  builds RO-Crate ZIP (templates unchanged)
                          │  + param-* form fields
                          ▼
                      workflow API --▶ sets spec.arguments values,
                                       submits the workflow to ARGO
                                          │
                                          ▼
                                        ARGO: resolves {{ }} as each
                                        step starts, runs the containers
```

</br>
</br>

## Hardware available to run BATs

Currently, the following hardware is available to run BATs:

* 32 VCPUs (shared among all BATs)
* 128 GB RAM (shared among all BATs)
* 20 GB disk per BAT, ~500 GB in total.

Note that the BMD project does not have good access to GPUs, and it is
therefore best to avoid creating BATs that rely on GPUs for their processing.
This will be especially true once BATs are deployed in production, as it is
unlikely that GPUs will be available on the production system.

</br>
</br>

### Data cubes

Data Cubes are bundles of raster data (e.g. climatic, topographic, land use)
that share the same extent and resolution.

* Data cubes are stored in [netCDF4](https://www.unidata.ucar.edu/software/netcdf)
  format.
* More specifically, data cubes are stored as
  [xarray `DataTree`](https://docs.xarray.dev/en/stable/generated/xarray.DataTree.html)
  objects. `DataTree`s are xarray objects that contain a series of
  [xarray `DataSet`](https://docs.xarray.dev/en/stable/generated/xarray.Dataset.html#xarray.Dataset).

Here is a short example of how a data cube file can be loaded in Python:

```py
import xarray as xr

# Load the data cube file as a DataTree object.
cube_path =  "../bmd/test_data/demo_cube.nc"
data_cube = xr.open_datatree(cube_path, engine="netcdf4")
print(data_cube)
```

</br>
</br>

## Glossary

* **SAP - Single Access Point**: the main online portal through which end-users
  can access BATs and run their analysis.

* **BAT - Biodiversity Analysis Tools** (sometimes also referred to as **VRE**,
  Virtual Research Environment): tools developed by the BMD project to help
  conservation planners make informed decisions.  
  BATs should in principle address specific monitoring needs that stem from an
  EU directive, such as e.g. the
  [30 by 30 directive](https://en.wikipedia.org/wiki/30_by_30).

* **RO-Crate**: Research Object Crate. RO-Crate is a community effort to
  establish a lightweight approach to packaging research data with their
  metadata.
  
  For details see <https://www.researchobject.org/ro-crate/about_ro_crate>.

* **CHELSA**: a collection of
  [widely used climate datasets](https://www.chelsa-climate.org).
