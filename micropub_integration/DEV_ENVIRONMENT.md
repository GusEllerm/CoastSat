# CoastSat Micropublication Development Environment

This development environment has been set up for the micropublication integration in the `livepublication` branch of the CoastSat repository.

## 🏗️ Project Overview

CoastSat is a shoreline analysis tool that combines satellite imagery analysis with interactive web visualization. The micropublication integration adds experimental support for generating dynamic transect-level publications using the LivePublication framework.

### Key Components:
- **Web Interface**: Interactive map showing shoreline changes (`index.html`)
- **Data Processing**: Python scripts for satellite imagery analysis
- **LivePublication Services**: Microservices for generating dynamic publications
- **Jupyter Notebooks**: Analysis and visualization workflows

## 📦 Environment Setup

### Python Environment
- **Type**: Virtual Environment (`.venv/`)
- **Python Version**: 3.13.5
- **Dependencies**: Installed from `requirements.txt`

### Key Dependencies:
- `coastsat_package` - Core shoreline analysis
- `geopandas` - Geospatial data processing
- `flask` - Web services
- `jupyter` - Interactive development
- `watchdog` - File monitoring for services

## 🚀 Quick Start

### Using VS Code Tasks (Recommended)
1. Open Command Palette (`Cmd+Shift+P`)
2. Type "Tasks: Run Task"
3. Select "Start All Services"

### Manual Startup
```bash
# Start micropublication service (port 8765)
python livepub_integration/micropub_watcher.py

# Start shoreline publication service (port 8766)  
python livepub_integration/shorelinepub_watcher.py

# Serve web interface (port 8000)
python -m http.server 8000

# Start Jupyter Lab (port 8888)
jupyter lab
```

## 🌐 Services & Ports

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Web Interface | 8000 | http://localhost:8000 | Main CoastSat application |
| Micropublication | 8765 | http://localhost:8765 | Transect-level publications |
| Shoreline Publication | 8766 | http://localhost:8766 | Site-level publications |
| Jupyter Lab | 8888 | http://localhost:8888 | Development environment |

## 📁 Project Structure

```
├── index.html                    # Main web interface
├── livepub_integration/          # LivePublication services
│   ├── micropub_watcher.py      # Micropublication service
│   ├── shorelinepub_watcher.py  # Shoreline publication service
│   ├── glify_micropublication.js # Frontend integration
│   └── tmp/                     # Generated publications
├── data/                        # Shoreline analysis data
├── requirements.txt             # Python dependencies
├── *.ipynb                      # Jupyter analysis notebooks
└── batch_process_*.py           # Automated processing scripts
```

## 🔧 Development Workflows

### Working with the Web Interface
1. Start the web server: `python -m http.server 8000`
2. Navigate to http://localhost:8000
3. Enable micropublications with `?micro=true` URL parameter

### Working with Jupyter Notebooks
1. Start Jupyter Lab: `jupyter lab`
2. Key notebooks:
   - `compare_profiles.ipynb` - Profile comparison analysis
   - `tidal_correction.ipynb` - Tidal corrections
   - `slope_estimation.ipynb` - Shoreline slope analysis
   - `linear_models.ipynb` - Trend analysis

### Working with LivePublication Services
1. Start both services (micropub and shoreline)
2. Services automatically download publication crates from GitHub
3. Test with web interface by clicking transects

## 🛠️ Development Tools

### Available VS Code Tasks:
- **Start Micropublication Service** - Transect-level publications
- **Start Shoreline Publication Service** - Site-level publications  
- **Start Jupyter Lab** - Interactive development
- **Serve Web Interface** - Main application
- **Start All Services** - Launch everything at once

### Testing Services
```bash
# Test micropublication service
curl -X POST http://localhost:8765/request -H "Content-Type: application/json" -d '{"id": "test-transect-id"}'

# Test shoreline publication service  
curl -X POST http://localhost:8766/request -H "Content-Type: application/json" -d '{"id": "test-site-id"}'
```

## 📊 Data Processing

### Automated Updates
- `update.sh` - Monthly automated updates via cron job
- Downloads new satellite imagery
- Processes shoreline changes
- Updates web interface data

### Manual Processing
- `batch_process_NZ.py` - New Zealand shoreline processing
- `batch_process_sar.py` - SAR imagery processing
- `make_xlsx.py` - Export data to Excel format

## 🚨 Troubleshooting

### Common Issues:

1. **Port conflicts**: Check if ports 8000, 8765, 8766, 8888 are available
2. **Missing data**: Some services need to download publication crates on first run
3. **Python path**: Ensure virtual environment is activated (`/Users/eller/Projects/CoastSat-livepubweb/.venv/bin/python`)

### Logs:
- Service logs appear in terminal when running services
- Check `tmp/` directories for generated publications
- Use browser developer tools for frontend debugging

## 🔗 External Dependencies

### APIs:
- Google Earth Engine (for satellite imagery)
- NIWA Tide API (for tidal corrections)
- GitHub API (for publication crates)

### System Requirements:
- Python 3.13+
- Modern web browser
- Internet connection for external APIs

## 📚 Additional Resources

- [CoastSat Original Repository](https://github.com/kvos/CoastSat)
- [LivePublication Framework](https://github.com/UoA-eResearch/LivePublication)
- [Zenodo Data](https://zenodo.org/records/15614554)

---

**Development Environment Status**: ✅ Ready for development
**Last Setup**: January 2025
