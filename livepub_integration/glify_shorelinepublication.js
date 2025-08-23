// Dynamically select API endpoint based on hostname
const SHORELINEPUB_API_BASE = location.hostname === 'localhost' || location.hostname === '127.0.0.1'
  ? `${location.protocol}//localhost:8766`
  : `${location.protocol}//coastsat.livepublication.org/shorelinepub`;

// Debug: Log that this script has loaded
console.log('🔧 Shorelinepublication script loaded with timer feature!');

window.initShorelinePopup = function (feature, layer, map, e) {
  console.log('🌊 initShorelinePopup called for:', feature.properties.id);
  const container = L.DomUtil.create("div", "shoreline-popup-container");
  container.innerHTML = `
    <div class="shoreline-loading with-fade">
      <div class="loading-spinner"></div>
      <div class="loading-progress">
        <div class="progress-time">
          <span>I can take a while to load, please be patient...</span>
          <span class="elapsed-time">0:00</span>
        </div>
        <div class="progress-bar" style="width: 100%; height: 10px; background-color: #e0e0e0; border-radius: 4px; overflow: hidden; margin-bottom: 10px; position: relative;">
          <div class="progress-fill" style="width: 0%; height: 100%; background-color: #4CAF50; position: absolute; top: 0; left: 0; transition: width 0.3s ease; -webkit-transition: width 0.3s ease;"></div>
        </div>
      </div>
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

  // Start timer immediately when request begins
  const maxAttempts = 90; // 3 minute timeout for publication generation (90 attempts × 2 seconds)
  const maxTimeSeconds = maxAttempts * 2; // Total time in seconds (180 seconds = 3 minutes)
  const elapsedTimeEl = container.querySelector('.elapsed-time');
  const progressFillEl = container.querySelector('.progress-fill');
  const startTime = Date.now();
  
  // Debug: Check if elements exist and log their initial styles
  console.log('Progress fill element:', progressFillEl);
  console.log('Progress fill parent (progress-bar):', progressFillEl?.parentElement);
  if (progressFillEl) {
    const computedStyle = window.getComputedStyle(progressFillEl);
    console.log('Initial progress fill computed style:', {
      width: computedStyle.width,
      height: computedStyle.height,
      backgroundColor: computedStyle.backgroundColor,
      display: computedStyle.display
    });
  }
  
  console.log('Timer elements found:', {
    elapsedTimeEl: !!elapsedTimeEl,
    progressFillEl: !!progressFillEl
  });
  
  // Start timer immediately
  const timerInterval = setInterval(() => {
    const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    const progressPercent = Math.min((elapsedSeconds / maxTimeSeconds) * 100, 100);
    
    console.log(`Timer update: ${minutes}:${seconds.toString().padStart(2, '0')} (${progressPercent.toFixed(1)}%)`);
    
    if (elapsedTimeEl) {
      elapsedTimeEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
    if (progressFillEl) {
      // Safari-compatible styling - avoid !important and use direct property setting
      progressFillEl.style.width = `${progressPercent}%`;
      progressFillEl.style.backgroundColor = '#4CAF50';
      progressFillEl.style.height = '100%';
      progressFillEl.style.display = 'block';
      progressFillEl.style.position = 'absolute';
      progressFillEl.style.top = '0';
      progressFillEl.style.left = '0';
      progressFillEl.style.transition = 'width 0.3s ease';
      progressFillEl.style.webkitTransition = 'width 0.3s ease'; // Safari prefix
      
      console.log(`Setting progress bar width to: ${progressPercent}%, actual width: ${progressFillEl.style.width}`);
      
      // Debug: Check computed style after setting
      const computedAfter = window.getComputedStyle(progressFillEl);
      if (elapsedSeconds % 5 === 0) { // Log every 5 seconds to avoid spam
        console.log('Computed style after setting:', {
          width: computedAfter.width,
          backgroundColor: computedAfter.backgroundColor,
          display: computedAfter.display,
          position: computedAfter.position
        });
      }
    }
    
    if (elapsedSeconds >= maxTimeSeconds) {
      clearInterval(timerInterval);
    }
  }, 1000);

  // Validate date range before sending request
  function validateDateForRequest(dateStr) {
    if (!dateStr) return true;
    const date = new Date(dateStr);
    const minDate = new Date('1984-01-01');
    const maxDate = new Date(); // Today
    return date >= minDate && date <= maxDate;
  }

  // Check if dates are valid before proceeding
  if (window.SHORELINE_DATE_FROM && !validateDateForRequest(window.SHORELINE_DATE_FROM)) {
    container.innerHTML = `<div class="shoreline-error">
      <h3>❌ Invalid Date Range</h3>
      <p>From date must be between 1984-01-01 and today.</p>
      <p>Please adjust your date range in the toolbar and try again.</p>
    </div>`;
    clearInterval(timerInterval);
    return;
  }

  if (window.SHORELINE_DATE_TO && !validateDateForRequest(window.SHORELINE_DATE_TO)) {
    container.innerHTML = `<div class="shoreline-error">
      <h3>❌ Invalid Date Range</h3>
      <p>To date must be between 1984-01-01 and today.</p>
      <p>Please adjust your date range in the toolbar and try again.</p>
    </div>`;
    clearInterval(timerInterval);
    return;
  }

  if (window.SHORELINE_DATE_FROM && window.SHORELINE_DATE_TO && 
      new Date(window.SHORELINE_DATE_FROM) > new Date(window.SHORELINE_DATE_TO)) {
    container.innerHTML = `<div class="shoreline-error">
      <h3>❌ Invalid Date Range</h3>
      <p>From date cannot be after To date.</p>
      <p>Please adjust your date range in the toolbar and try again.</p>
    </div>`;
    clearInterval(timerInterval);
    return;
  }

  const payload = {
    id: site_id,
    geometry: feature.geometry,
    // Add date range if specified
    ...(window.SHORELINE_DATE_FROM && { date_from: window.SHORELINE_DATE_FROM }),
    ...(window.SHORELINE_DATE_TO && { date_to: window.SHORELINE_DATE_TO })
  };

  console.log('📅 Shoreline publication payload:', payload);

  fetch(`${SHORELINEPUB_API_BASE}/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then((response) => response.json())
    .then((data) => {
      const filename = data.filename;
      console.log("📄 Shoreline publication response:", data);
      
      // Wait for the file to be ready with retry logic
      let attempts = 0;
      
      const checkPublicationReady = () => {
        const publication_url = `${SHORELINEPUB_API_BASE}/tmp/${filename}`;
        fetch(publication_url, { method: 'HEAD' })
          .then(res => {
            if (res.ok) {
              // Clear the timer
              clearInterval(timerInterval);
              
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
                fetch(`${SHORELINEPUB_API_BASE}/delete/${filename}`, { method: "DELETE" })
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
              clearInterval(timerInterval);
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
      // Clear any running timer (though it might not exist yet)
      if (typeof timerInterval !== 'undefined') {
        clearInterval(timerInterval);
      }
      container.innerHTML = `<div class="shoreline-error">
        <h3>❌ Request Failed</h3>
        <p>Failed to request shoreline publication for site <strong>${site_id}</strong></p>
        <p>Please check your connection and try again.</p>
      </div>`;
      console.error("Shoreline publication request error:", error);
    });
};