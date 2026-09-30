# Third-party assets

Locally bundled, pinned assets keep core map/chart JavaScript available without CDN requests. Map tiles still require an Internet connection and remain attributed on the map.

- Leaflet 1.9.4: BSD-2-Clause. `static/vendor/LEAFLET-LICENSE.txt`. Upstream https://leafletjs.com
- Chart.js 4.4.1: MIT. `static/vendor/CHARTJS-LICENSE.txt`. Upstream https://www.chartjs.org
- Map tiles/data: OpenStreetMap contributors, https://www.openstreetmap.org/copyright. Respect the tile provider's usage policy; this is a low-traffic demonstration, not an offline tile pack.

Backend dependency names and tested versions are in `pyproject.toml`. No private map service token is embedded.
