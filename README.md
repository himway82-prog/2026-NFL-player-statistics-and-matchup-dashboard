# NFL Matchup Dashboard — Render-ready

This package contains the dashboard, its Python HTTP API, and a Render Blueprint (`render.yaml`). No dependencies beyond Python 3.10+.

## Deploy from a phone (no local Python needed)

1. Sign in to GitHub using a browser. Create a new repository and upload **server.py**, **index.html**, **render.yaml**, and **.gitignore** at the repository root.
2. Sign in to https://dashboard.render.com/ using your browser. Connect your GitHub account.
3. Choose **New → Blueprint** and select the repository; review the Free web service configuration and deploy.
4. After deployment, open the assigned `https://...onrender.com` URL on your phone.

Data is fetched from nflverse on requests and cached for six hours **while the service is running**. This is on-demand automatic updating, **not a scheduled background job**. Free Render instances sleep when idle and can take time to wake. Cache is ephemeral and may be lost on restart; when nflverse is unreachable the service displays an error rather than inventing statistics.

Security: No mobile app install or phone permissions. Website traffic uses Render HTTPS. Basic response security headers provided. Site is publicly accessible to anyone knowing the URL; do not enter confidential data. No sportsbook account connection.

Known limits: This build has not been end-to-end verified with live 2026 NFL data. Future schedules are derived from nflverse, with potential edge cases near week transitions and postponed games. Defensive stats are position-group aggregates rather than true betting probabilities.
