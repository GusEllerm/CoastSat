window.initShorelinePopup = function (feature, layer, map, e) {
  const container = L.DomUtil.create("div", "shoreline-popup-container");
  container.innerHTML = `
    <div class="shoreline-loading">Loading shoreline micropublication...</div>
  `;

  const popup = L.popup({
    minWidth: 500,
    autoPan: false,
    className: "shoreline-popup"
  })
    .setLatLng(e.latlng)
    .setContent(container)
    .addTo(map);

  const payload = {
    id: feature.properties.id,
    geometry: feature.geometry
  };

  fetch("/shorelinepub/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then((response) => response.json())
    .then((data) => {
      const filename = data.filename;
      const iframe = document.createElement("iframe");
      iframe.src = `/shorelinepub/tmp/${filename}`;
      iframe.className = "shoreline-iframe";
      iframe.loading = "lazy";
      iframe.width = "100%";
      iframe.height = "600";
      iframe.frameBorder = "0";
      container.innerHTML = "";
      container.appendChild(iframe);

      popup.on("remove", () => {
        fetch(`/shorelinepub/delete/${filename}`, { method: "DELETE" });
      });
    })
    .catch((error) => {
      container.innerHTML = `<div class="shoreline-error">Failed to load shoreline publication.</div>`;
      console.error("Shoreline publication error:", error);
    });
};