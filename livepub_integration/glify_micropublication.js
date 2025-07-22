// Dynamically select API endpoint based on hostname
const MICROPUB_API_BASE = location.hostname === 'localhost' || location.hostname === '127.0.0.1'
  ? `${location.protocol}//localhost:8765`
  : `${location.protocol}//coastsat.livepublication.org/micropub`;
let lastGeneratedFilename = null;
let popupListenerRegistered = false;
window.initMicropublicationPopup = function (p, g, e, url, map, download, debug) {
  const container = document.createElement("div");
  const tabs = `
  <div class="popup-content">
    <div class="micropub-iframe-container with-fade">
      <div id="iframe-loading" class="loading-spinner"></div>
      <iframe id="debug-iframe" style="width: 100%; border: none; display: none;" height="500"></iframe>
    </div>
    <div class="micropub-plot-container">
      <div id="plot"></div>
    </div>
  </div>`;
  container.innerHTML = tabs;

  window.popup = L.popup({
    minWidth: 800,
    autoPan: false
  })
    .setContent(container)
    .setLatLng(e.latlng)
    .addTo(map);

  fetch(`${MICROPUB_API_BASE}/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: p.id })
  })
    .then(r => r.json())
    .then(data => {
      const filename = data.filename;
      console.log("Micropublication response:", data);
      const thisPopupFilename = filename;
      lastGeneratedFilename = thisPopupFilename;
      // Wait until the file exists before attempting to load it
      const maxAttempts = 10;
      let attempts = 0;
      const checkMicropublicationReady = () => {
        const iframe = document.getElementById('debug-iframe');
        const mciro_url = `${MICROPUB_API_BASE}/tmp/${thisPopupFilename}`;
        fetch(mciro_url, { method: 'HEAD' })
          .then(res => {
            if (res.ok) {
              if (lastGeneratedFilename === thisPopupFilename) {
                iframe.src = mciro_url;
                document.getElementById('iframe-loading').style.display = "none";
                iframe.style.display = "block";
              }
            } else if (attempts < maxAttempts) {
              attempts++;
              setTimeout(checkMicropublicationReady, 1000);
            }
          })
          .catch(() => {
            if (attempts < maxAttempts) {
              attempts++;
              setTimeout(checkMicropublicationReady, 1000);
            }
          });
      };
      checkMicropublicationReady();
    })
    .catch(err => {
      console.error("Failed to load micropublication:", err);
    });

  Papa.parse(url, {
    download: true,
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
    complete: function (results) {
      console.log(results)
      var filtered_data = results.data.filter(d => d[p.id])
      var dates = filtered_data.map(d => d.dates)
      var values = filtered_data.map(d => d[p.id])
      var satname = filtered_data.map(d => d.satname)
      var mean = Plotly.d3.mean(values)
      values = values.map(v => v ? v - mean : v)
      console.log(dates, values)
      var min_date = new Date(results.data[0].dates)
      var max_date = new Date(results.data[results.data.length - 1].dates)
      var datediff = (max_date - min_date) / 1000 / 60 / 60 / 24 / 365.25
      var data = [{
        type: "scatter",
        mode: "lines+markers",
        name: "chainage",
        x: dates,
        y: values,
      }, {
        type: "line",
        x: [min_date, max_date],
        y: [p.intercept - mean, p.trend * datediff + p.intercept - mean],
        name: "trendline"
      }];
      var layout = {
        height: 250,
        font: { size: 10 },
        margin: { l: 50, r: 20, t: 10, b: 40 },
        yaxis: {
          title: "cross-shore change [m]",
          hoverformat: '.1f',
          gridcolor: '#eee'
        },
        xaxis: {
          gridcolor: '#eee'
        },
        showlegend: false
      };
      Plotly.newPlot("plot", data, layout);
      var px = map.project(e.latlng);
      console.log(px)
      px.y -= 400;
      map.panTo(map.unproject(px), { animate: true });
      if (debug) {
        $("#plot").on('plotly_hover plotly_click', function (event, data) {
          console.log(data)
          var d = data.points[0].x;
          console.log(`Hovered on ${d}`)
          var dt = dates[data.points[0].pointIndex].replace("+00:00", "").replace(/[ :]/g, "-");
          var sat = satname[data.points[0].pointIndex]
          var plot_url = `https://wave.storm-surge.cloud.edu.au/CoastSat_data/${p.site_id}/jpg_files/detection/${dt}_${sat}.jpg`
          console.log(plot_url)
          $("#img").attr("src", plot_url);
        })
      }
    }
  });

  if (!popupListenerRegistered) {
    map.on('popupclose', function () {
      const iframe = document.getElementById('debug-iframe');
      if (iframe) iframe.src = "";
      console.log("Popup closed, cleaning up micropublication file...");
      if (lastGeneratedFilename) {
        console.log(`🗑️ Cleaning up micropublication file: ${lastGeneratedFilename}`);
        fetch(`${MICROPUB_API_BASE}/delete/${lastGeneratedFilename}`, {
          method: 'DELETE'
        })
        .then(res => {
          if (res.status === 404) {
            console.warn(`⚠️ Tried to delete ${lastGeneratedFilename}, but it didn't exist yet (probably still generating).`);
          } else if (!res.ok) {
            throw new Error("Failed to delete file");
          } else {
            console.log(`🗑️ Deleted ${lastGeneratedFilename}`);
          }
          lastGeneratedFilename = null;
        })
        .catch(err => {
          console.warn("⚠️ Failed to delete micropublication file:", err);
        });
      }
    });
    popupListenerRegistered = true;
  }
};