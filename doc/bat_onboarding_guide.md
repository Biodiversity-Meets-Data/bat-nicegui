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
  frontend to the backend each BAT must define two template files:
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

Once a user submits the input form of a BAT, the `bat-nicegui` frontend creates
a so-called [**RO-crate**](https://www.researchobject.org/ro-crate) based on
the user input. This is basically a `.zip` that contains 2 files:

* **`ro-crate-metadata.json`**: stores a summary of the input argument values
  entered by the user, and to be used in the BAT run. Also stores other
  metadata about the BAT.

* **`workflow.yaml`**: config file defining the jobs to be run by the ARGO
  workflow manager. In other words, a file that indicates what are the
  different steps to run. Each step runs in a separate Docker container.

  Input values passed by the user are first stored in `ro-crate-metadata.json`,
  and a custom script then injects/copies them to `workflow.yaml`.

  **Artifacts** can be defined as outputs to preserve of each step, and
  these are then available to the subsequent steps of the workflow. E.g.,
  if the first step of the workflow consists in downloading data from GBIF,
  then the downloaded data can be marked as an artifact so that it becomes
  available to the next step in the workflow. Overall, this is fairly
  similar to a GitLab/GitHub CI/CD workflow.

  The `workflow.yaml` file follows the
  [ARGO workflow](https://argoproj.github.io/workflows) specifications.

For available workflow-related Kubernetes secrets (for example GBIF
credentials), see the [Argo Workflow Secrets Catalog](./argo-secrets-catalog.md).

To learn more about how the RO-crate are built, one function to look at is
[`build_rocrate_zip()`](https://github.com/Biodiversity-Meets-Data/bat-nicegui/blob/main/app/main.py#L68),
which generates the `.zip` RO-Crate.

#### How arguments are passed from frontend (niceGUI) to backend

1. User enters its input via fields defined in the BAT frontend (i.e. each
   BAT has its own webpage in the BMD SAP - single access point - application).
   * Reminder: BAT frontend use the niceGUI python framework and are hosted
     in [this project](https://github.com/Biodiversity-Meets-Data/bat-nicegui).

2. The [bat-nicegui](https://github.com/Biodiversity-Meets-Data/bat-nicegui)
   app creates a new `ro-crate-metadata.json` for the current run based on the
   defined template. The important aspect is that the user input values are
   stored in the `input:` section of the JSON file, by replacing the variable
   placeholders (`#target_species` and `#aoi_wkt`) in the example below with
   the user inputs.

   ```json
   "input": [
     {
       "@id": "#target_species"
     },
     {
       "@id": "#aoi_wkt"
     }
   ]
   ```

3. A custom scrips generates a new `workflow.yaml` (based on the template
   defined for the specific BAT that is being run) and injects the input
   values defined in `ro-crate-metadata.json` into the `parameters:` section
   of the `workflow.yaml` file.

   ```yaml
   spec:
     arguments:
       parameters:
        - name: target_species
          description: Species scientific name
          value: "Myotis myotis"
        - name: aoi_wkt
          description: Geographical extent of analysis in WKT format
          value: "POLYGON((3.8 51.2, 4.2 51.2, 4.2 50.8, 3.8 50.8, 3.8 51.2))"
   ```

4. A new run of the BAT is initiated by passing the `workflow.yaml` file
   (which now contains all input argument values from the user) to the ARGO
   workflow manager.

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
