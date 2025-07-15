# CoastSat

[![DOI](https://zenodo.org/badge/829830765.svg)](https://zenodo.org/doi/10.5281/zenodo.13835882)

This repository contains a [Leaflet.glify](https://github.com/robertleeplummerjr/Leaflet.glify) map ([`index.html`](index.html)) of shoreline change around the Pacific Rim. The user can click on a transect to view a plotly.js plot of change over time for that transect. The HTML and CSVs are hosted on GitHub Pages. It also contains code required to update data in New Zealand.

Installation: `pip install -r requirements.txt`

Everything in New Zealand and Sardinia was calculated by me ([@neon-ninja](https://github.com/neon-ninja)) using [CoastSat](https://github.com/kvos/CoastSat), everything else was calculated by [@kvos](https://github.com/kvos) and downloaded from this Zenodo link: https://zenodo.org/records/15614554 (v1.6). I used `batch_process_NZ.py` to automate CoastSat, as well as run multiple sites in parallel. This file uses a Google Earth Engine service account to download satellite imagery, to allow for automated processing. I used the [NIWA Tide API](https://developer.niwa.co.nz/docs/tide-api/1/overview) for tidal corrections. See `tidal_correction.ipynb` for specifics.

New Zealand results were calculated on the `wave.storm-surge.cloud.edu.au` NeCTAR VM (32 CPUs, 128GB RAM). The total size of the data folder is 1.3TB. The `.gitignore` is used to only track the *.csv results within this data folder with git, everything else in the data folder is gitignored.

Additionally, I've configured a cron job:

```bash
# m h  dom mon dow   command
  0 0  1   *   *     cd CoastSat && ./update.sh &> update.log
```

On the above mentioned NeCTAR VM, which should, on the 1st of every month:
- Download any new Landsat satellite imagery
- Run CoastSat to classify these images, find the shorelines, and transect intersects
- Run tide correction
- Recalculate the linear trend
- Commit the new results to this repo

## LivePublication Micropublication Integration

This fork of CoastSat includes an experimental integration with the [LivePublication](https://github.com/UoA-eResearch/LivePublication) framework, allowing each transect popup to procedurally generate a micropublication. This micropublication includes contextual information and a Plotly time-series visualization based on the selected transect’s data.

The micropublication content is modular and conditionally enabled:
- A global `ENABLE_MICROPUBLICATIONS` flag controls whether micropublications are shown instead of the default popup content.
- This flag can be toggled using a UI switch included in the sidebar or via a URL query parameter, e.g. `?micro=true`.
- The integration code is isolated within the `micro_integration/` directory and includes:
  - `glify_micropublication.js` — handles popup logic for micropublications
  - `glify_micropublication.css` — styles for the tabbed popup layout

This setup is designed to be safely ignorable by upstream developers and does not interfere with existing functionality when disabled.