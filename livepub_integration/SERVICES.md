# Live Publication Integration Services

This directory contains microservices for integrating dynamic publications with the CoastSat interface.

## Service Architecture

### Micropublication Service (`micropub_watcher.py`)
- **Port**: 8765
- **Endpoints**: `/request`, `/tmp/<filename>`, `/delete/<filename>`
- **Crate**: Downloads from `GusEllerm/CoastSat-micropublication`
- **Local Crate**: `micropub_publication.crate/`
- **Temp Dir**: `tmp/`
- **Purpose**: Handles transect-level micropublications

### Shoreline Publication Service (`shorelinepub_watcher.py`)
- **Port**: 8766
- **Endpoints**: `/request`, `/tmp/<filename>`, `/delete/<filename>`
- **Crate**: Downloads from `GusEllerm/CoastSat-shorelinepublication`
- **Local Crate**: `shorelinepub_publication.crate/`
- **Temp Dir**: `shoreline_tmp/`
- **Purpose**: Handles site-level comprehensive publications

## Service Isolation

Each service maintains its own:
- Publication crate directory (service-specific naming)
- Version tracking files (`{service}_crate_version.txt`)
- Temporary file directories
- Request processing directories
- Network ports

This prevents conflicts when multiple services download and extract publication crates.

## Usage

### Start Micropublication Service
```bash
python micropub_watcher.py
# Runs on http://localhost:8765
```

### Start Shoreline Publication Service  
```bash
python shorelinepub_watcher.py
# Runs on http://localhost:8766
```

### Client Integration
- `glify_micropublication.js` → micropub service (port 8765)
- `glify_shorelinepublication.js` → shorelinepub service (port 8766)

## Directory Structure
```
livepub_integration/
├── micropub_watcher.py              # Micropub service
├── shorelinepub_watcher.py          # Shoreline pub service
├── micropub_publication.crate/      # Micropub crate (auto-downloaded)
├── shorelinepub_publication.crate/  # Shoreline crate (auto-downloaded)
├── tmp/                            # Micropub temp files
├── shoreline_tmp/                  # Shoreline temp files
├── requests/                       # Micropub requests
├── shoreline_requests/             # Shoreline requests
└── glify_*.js                      # Client-side integration
```
