// Set this to your production API endpoint if hosting remotely
const MICROPUB_API_BASE = 'http://localhost:8765';
let lastGeneratedFilename = null;
window.initMicropublicationPopup = function (p, g, e, url, map, download, debug) {
  const container = document.createElement("div");
  container.className = "popup-content";

  const tabs = `
    <div class="tab-buttons">
      <button class="tab-button active" data-tab="tab1">Info</button>
      <button class="tab-button" data-tab="tab2">MicroPublication</button>
    </div>
    <div id="tab1" class="tab-content active">
      <b>${p.id}</b><br>
      along_dist: ${p.along_dist?.toFixed(2)}<br>
      along_dist_norm: ${p.along_dist_norm?.toFixed(2)}<br>
      origin point (landward): ${g[0][1].toFixed(6)},${g[0][0].toFixed(6)}<br>
      destination point (seaward): ${g[1][1].toFixed(6)},${g[1][0].toFixed(6)}<br>
      beach_slope: ${p.beach_slope}<br>
      n_points: ${p.n_points}<br>
      n_points_nonan: ${p.n_points_nonan}<br>
      orientation: ${p.orientation?.toFixed(2)}<br>
      trend: ${p.trend?.toFixed(2)} m/year<br>
      R² score: ${p.r2_score?.toFixed(2)} ${p.r2_score < .05 ? " score < 0.05 - linear trend might not be reliable" : ""}<br>
      mae: ${p.mae?.toFixed(2)}<br>
      mse: ${p.mse?.toFixed(2)}<br>
      rmse: ${p.rmse?.toFixed(2)}<br>
      site: ${p.site_id}<br>
      ${download}
      ${debug ? `<img id="img" style='height: 100%; width: 100%; object-fit: contain'>` : ""}
      <!-- <div id="plot"></div> -->
    </div>
    <div id="tab2" class="tab-content">
      <iframe id="debug-iframe" style="width: 100%; border: none;" height="400"></iframe>
    </div>
    <div id="debug-plot"></div>`;
  container.innerHTML = tabs;

  const tabButtons = container.querySelectorAll(".tab-button");
  const tabContents = container.querySelectorAll(".tab-content");
  
  tabButtons.forEach(button => {
      button.addEventListener("click", function () {
        tabButtons.forEach(btn => btn.classList.remove("active"));
        tabContents.forEach(content => content.classList.remove("active"));

        this.classList.add("active");
        const targetId = this.getAttribute("data-tab");
        const targetContent = container.querySelector(`#${targetId}`);
        if (targetContent) {
          targetContent.classList.add("active");
        }
        const tabId = button.dataset.tab;
        if (tabId === "tab2") {
          const iframe = document.getElementById('debug-iframe');
          // iframe.srcdoc = "<p>Generating micropublication...</p>";

          fetch(`${MICROPUB_API_BASE}/request`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: p.id })  // Send the ID for publication
          })
            .then(r => r.json())
            .then(data => {
              const filename = data.filename;
              console.log("Micropublication response:", data);
              console.log("Expected iframe.src:", `${MICROPUB_API_BASE}/tmp/${filename}`);
              iframe.src = `${MICROPUB_API_BASE}/tmp/${filename}`;
              lastGeneratedFilename = filename;
            })
            .catch(err => {
              console.error("Failed to load micropublication:", err);
              iframe.srcdoc = "<p style='color:red;'>Failed to load debug info.</p>";
            });
        }
      });
    });

  window.popup = L.popup({ minWidth: 800 })
    .setContent(container)
    .setLatLng(e.latlng)
    .addTo(map);

  Papa.parse(url, {
    download: true,
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
    complete: function (results) {
      const filtered_data = results.data.filter(d => d[p.id]);
      const dates = filtered_data.map(d => d.dates);
      const values = filtered_data.map(d => d[p.id]);
      const satname = filtered_data.map(d => d.satname);
      const mean = Plotly.d3.mean(values);
      const adjusted_values = values.map(v => v ? v - mean : v);

      const min_date = new Date(results.data[0].dates);
      const max_date = new Date(results.data[results.data.length - 1].dates);
      const datediff = (max_date - min_date) / 1000 / 60 / 60 / 24 / 365.25;

      const data = [{
        type: "scatter",
        mode: "lines+markers",
        name: "chainage",
        x: dates,
        y: adjusted_values,
      }, {
        type: "line",
        x: [min_date, max_date],
        y: [p.intercept - mean, p.trend * datediff + p.intercept - mean],
        name: "trendline"
      }];

      const layout = {
        title: `Time series for ${p.id}`,
        xaxis: { title: "Date/Time" },
        yaxis: { title: "cross-shore change [m]", hoverformat: '.1f' }
      };

      Plotly.newPlot(container.querySelector("#plot"), data, layout);

      if (debug) {
        container.querySelector("#plot").addEventListener('plotly_hover', function (event) {
          const d = event.detail.points[0].x;
          const dt = dates[event.detail.points[0].pointIndex].replace("+00:00", "").replace(/[ :]/g, "-");
          const sat = satname[event.detail.points[0].pointIndex];
          const plot_url = `https://wave.storm-surge.cloud.edu.au/CoastSat_data/${p.site_id}/jpg_files/detection/${dt}_${sat}.jpg`;
          container.querySelector("#img").src = plot_url;
        });
      }
    }
  });

  map.on('popupclose', function () {
    // Reset iframe content for cleanup
    console.log("Popup closed, cleaning up micropublication file...");
    if (lastGeneratedFilename) {
      console.log(`🗑️ Cleaning up micropublication file: ${lastGeneratedFilename}`);
      fetch(`${MICROPUB_API_BASE}/delete/${lastGeneratedFilename}`, {
        method: 'DELETE'
      })
      .then(res => {
        if (!res.ok) throw new Error("Failed to delete file");
        console.log(`🗑️ Deleted ${lastGeneratedFilename}`);
      })
      .catch(err => {
        console.warn("⚠️ Failed to delete micropublication file:", err);
      });

      lastGeneratedFilename = null;
    }
  });
};