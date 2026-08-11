# DEEP-Seek Rider Mobile

Production mobile rider client contract. The repository's PWA remains the fallback, while a native Android/iOS build can consume the same API.

Required capabilities:
- foreground/background location permission
- encrypted token storage
- periodic location updates to `POST /api/gps`
- delivery task accept/start/arrive/complete
- proof-of-delivery photo/signature upload
- COD collection confirmation
- offline queue with idempotency keys

Recommended implementation: Expo/React Native or Flutter. Build signing, App Store/Play Store credentials and location permissions must be supplied by the deployment owner.

API base URL and rider token are runtime configuration; no credentials are committed.
