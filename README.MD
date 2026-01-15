# CoastSat dashboard with LivePublication integration (fork)

> - This repository is a fork/derivative of upstream CoastSat: https://github.com/UoA-eResearch/CoastSat [![DOI](https://zenodo.org/badge/829830765.svg)](https://zenodo.org/doi/10.5281/zenodo.13835882)
> - Purpose of this fork: integrate LivePublication outputs (shoreline + micropublications) into a dashboard/map UI (Chapter 6).
> - High-level summary of modifications (this fork vs upstream):
>   - LivePublication ingestion/embedding points: `micro_integration/` (micropublication generation), `index.html` integration hooks, and related JS/CSS (`micro_integration/glify_micropublication.js`, `micro_integration/glify_micropublication.css`).
>   - UI components added/modified: `index.html` (Leaflet + Plotly dashboard).
>   - Build/deploy changes: dashboard deployed at https://coastsat.livepublication.org/.

## What this dashboard does
- Visualises shoreline change transects in an interactive map.
- Allows clicking a transect to view a time-series plot.
- Generates micropublications for each transect when enabled.
- Generates shoreline publications for each site when enabled.\

## How to run locally (minimal)
```bash
pip install -r requirements.txt
python -m http.server 8000
```
Then open `http://localhost:8000/index.html`.

## How to deploy / view live
Live dashboard: https://coastsat.livepublication.org/

## Inputs
- CSV and GeoJSON inputs (tracked in this repo): `csv_run7/`, `transects.geojson`, `shorelines.geojson`, `polygons.geojson`, `global_shoreline_5deg_1081.geojson`.
- LivePublication inputs (used for micropublications): shoreline and micropublication crates from the related artefacts list below.

## How to cite
Until Zenodo mints a DOI for the thesis snapshot, cite the GitHub repository URL. After release/archival, update this section (and `CITATION.cff`) with the Zenodo DOI.

## Related artefacts (DOIs + repos)
- Upstream CoastSat baseline repo: https://github.com/UoA-eResearch/CoastSat
- CoastSat shoreline LivePublication (Zenodo): https://doi.org/10.5281/zenodo.18250478
- CoastSat interface.crate generation tool (Zenodo): https://doi.org/10.5281/zenodo.18250232
- LivePublication Interface Schemas (DPC/DSC) (Zenodo): https://doi.org/10.5281/zenodo.18250033
- CoastSat transect micropublication LivePublication (Zenodo): https://doi.org/10.5281/zenodo.18250889
- Live dashboard URL: https://coastsat.livepublication.org/

## License
MIT License (from upstream CoastSat). See `LICENSE` for full text. This applies to the software in this repository unless otherwise noted.

## LivePublication micropublication integration (implementation notes)

This fork includes an experimental integration with the LivePublication framework, allowing each transect popup to procedurally generate a micropublication that embeds contextual information and a Plotly time-series visualisation based on the selected transect’s data.

- A global `ENABLE_MICROPUBLICATIONS` flag controls whether micropublications are shown instead of the default popup content.
- The flag can be toggled using a UI switch in the sidebar or via a URL query parameter, e.g. `?micro=true`.
- Integration code is isolated within `micro_integration/`, including:
  - `glify_micropublication.js` — popup logic for micropublications
  - `glify_micropublication.css` — styles for the tabbed popup layout

### Micropublication generation
When enabled, micropublications are generated dynamically in response to user interaction. This is handled via a lightweight Python service (`micro_integration/micropub_watcher.py`) that watches for micropublication requests and runs a Stencila pipeline using a procedural narrative template.

- When a user clicks on a transect, a request is posted to the watcher service (`http://localhost:8765/request`) with the transect ID.
- The watcher generates a unique HTML file from a `.smd` template (`micro_integration/micropub_templates/base_template.smd`) using Stencila, and places the result in `micro_integration/tmp/`.
- The client receives the filename in the response and embeds it as an iframe inside the popup.

Additional logic in `glify_micropublication.js` includes:
- A preload mechanism that fetches and prepares the micropublication upon transect selection.
- Cleanup logic to remove previous requests and prevent accumulation of stale files.

### Shoreline publication generation
When shoreline publications are enabled, a watcher service prepares site-level LivePublication content for shoreline context and summary views.

- The shoreline publication workflow is handled by `livepub_integration/shorelinepub_watcher.py`.
- Generated shoreline publications are represented as RO-Crate bundles (for example, `livepub_integration/shorelinepub_publication.crate/ro-crate-metadata.json`).


## Notes from the existing pipeline
- Everything in New Zealand and Sardinia was calculated by @neon-ninja using CoastSat. Everything else was calculated by @kvos and downloaded from https://zenodo.org/records/15614554 (v1.6).
- `batch_process_NZ.py` automates CoastSat runs using a Google Earth Engine service account.
- Tidal corrections use the NIWA Tide API; see `tidal_correction.ipynb`.
- New Zealand results were calculated on the `wave.storm-surge.cloud.edu.au` NeCTAR VM (32 CPUs, 128GB RAM).
- The `.gitignore` is used to only track the `*.csv` results within the `data/` folder; other large assets are ignored.

## Update automation
Cron job (configured on the NeCTAR VM):
```bash
# m h  dom mon dow   command
  0 0  1   *   *     cd CoastSat && ./update.sh &> update.log
```
On the 1st of every month, this process:
- Downloads any new Landsat satellite imagery
- Runs CoastSat to classify images and extract shorelines/transect intersects
- Runs tide correction
- Recalculates linear trends
- Commits new results to this repo

## TODO (maintainer checklist)
- Identify files/modules where LivePublication crates are read and update this README + RO-Crate hasPart list.
- Choose release tag/version for Zenodo archival snapshot.
- After DOI minted: backfill DOI into README, `CITATION.cff`, `codemeta.json`, and `ro-crate-metadata.json`.
