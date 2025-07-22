window.initShorelinePopup = function (feature, layer, map, e) {
  const container = L.DomUtil.create("div", "shoreline-popup-container");
  container.innerHTML = `
    <div class="shoreline-loading with-fade">
      <div class="loading-text">Generating shoreline publication...</div>
      <div class="loading-spinner"></div>
    </div>
  `;

  const popup = L.popup({
    minWidth: 800,
    maxWidth: 800,
    autoPan: false,
    className: "shoreline-popup"
  })
    .setLatLng(e.latlng)
    .setContent(container)
    .addTo(map);

  const site_id = feature.properties.id;
  console.log(`🌊 Requesting shoreline publication for site: ${site_id}`);

  const payload = {
    id: site_id,
    geometry: feature.geometry
  };

  fetch("http://localhost:8766/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then((response) => response.json())
    .then((data) => {
      const filename = data.filename;
      console.log("📄 Shoreline publication response:", data);
      
      // Wait for the file to be ready with retry logic
      const maxAttempts = 15; // Longer timeout for publication generation
      let attempts = 0;
      
      const checkPublicationReady = () => {
        const publication_url = `http://localhost:8766/tmp/${filename}`;
        fetch(publication_url, { method: 'HEAD' })
          .then(res => {
            if (res.ok) {
              // Publication is ready, create and show iframe
              const iframe = document.createElement("iframe");
              iframe.src = publication_url;
              iframe.className = "shoreline-iframe";
              iframe.loading = "lazy";
              iframe.width = "100%";
              iframe.height = "700";
              iframe.frameBorder = "0";
              iframe.style.display = "block";
              
              // Replace loading content with iframe container that has fade effect
              container.innerHTML = "";
              const iframeContainer = document.createElement("div");
              iframeContainer.className = "shoreline-iframe-container with-fade";
              iframeContainer.appendChild(iframe);
              container.appendChild(iframeContainer);
              
              console.log(`✅ Shoreline publication loaded: ${publication_url}`);
              
              // Set up cleanup on popup close
              popup.on("remove", () => {
                console.log(`🗑️ Cleaning up publication: ${filename}`);
                fetch(`http://localhost:8766/delete/${filename}`, { method: "DELETE" })
                  .catch(err => console.warn("Cleanup warning:", err));
              });
              
            } else if (attempts < maxAttempts) {
              attempts++;
              console.log(`⏳ Publication not ready yet, attempt ${attempts}/${maxAttempts}`);
              setTimeout(checkPublicationReady, 2000); // Check every 2 seconds
            } else {
              throw new Error("Publication generation timed out");
            }
          })
          .catch((error) => {
            if (attempts < maxAttempts) {
              attempts++;
              console.log(`⏳ Retrying publication check, attempt ${attempts}/${maxAttempts}`);
              setTimeout(checkPublicationReady, 2000);
            } else {
              container.innerHTML = `<div class="shoreline-error">
                <h3>⚠️ Publication Generation Failed</h3>
                <p>Unable to generate shoreline publication for site <strong>${site_id}</strong></p>
                <p>This may be due to missing data or processing issues.</p>
              </div>`;
              console.error("Shoreline publication timeout:", error);
            }
          });
      };
      
      // Start checking if publication is ready
      checkPublicationReady();
      
    })
    .catch((error) => {
      container.innerHTML = `<div class="shoreline-error">
        <h3>❌ Request Failed</h3>
        <p>Failed to request shoreline publication for site <strong>${site_id}</strong></p>
        <p>Please check your connection and try again.</p>
      </div>`;
      console.error("Shoreline publication request error:", error);
    });
};