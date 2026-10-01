# Verification reports

Committed validation records describe checks actually executed. Locally generated benchmark reports include raw synthetic smoke timings and are ignored by Git by default. They are not capacity guarantees and do not measure the user's computer.


## v3 workflow evidence

`trip-workflow-ui.json` records local browser-preview and mocked API-contract checks. These checks cover registration, trip lifecycle, review, responsive layouts and token handling; they are not evidence that a hosted backend is running. Python unit checks and real PostgreSQL/Redis CI results are separate. Existing `render-live-verification.json` and `hosted-dashboard-checks.json` describe the older v2.1 dashboard, not the new managed-trip feature.

`trip-workflow-hosted.json` records 25 successful real hosted checks of the managed-trip API, PostgreSQL history preservation, Redis GEO/fan-out, authenticated WebSocket events and lifecycle behavior. GPS is synthetic. Its tested commit and deployment are recorded explicitly. The live UI also has a separate, repeatable local contract suite.
