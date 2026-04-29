# Nut Counter

Raspberry Pi nut and washer counting appliance. The production app is a React
SPA served by a Python backend that owns config, mock hardware state, camera
preview endpoints, and the future GPIO/camera/AI integrations.

## Project Structure

```text
src/                    React SPA source
backend/nut_counter/    Python backend, CLI, config, static hosting
config/                 Default appliance config
systemd/                Backend and Firefox ESR kiosk units
debian/DEBIAN/          Debian maintainer scripts
scripts/                Packaging and service helper scripts
public/                 Static machine assets
```

Build the SPA into `dist/ui`, then run the Python backend to serve both the UI
and local API.

## Development

```bash
pnpm dev
pnpm dev:backend
```

Open [http://localhost:5173](http://localhost:5173) for Vite dev or
[http://localhost:8787](http://localhost:8787) when testing the backend-served
build.

## Checks

```bash
pnpm build
pnpm lint
pnpm typecheck
pnpm test:backend
pnpm package:dry-run
```

## CI/CD

GitHub Actions runs the full check suite on pull requests and pushes to `main`:

```text
lint -> typecheck -> backend tests -> UI build -> package dry-run
```

The CI workflow also builds an arm64 Debian package and uploads it as a workflow
artifact:

```text
build/nut-counter_<version>_arm64.deb
```

To publish a GitHub Release with the `.deb` attached, push a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

You can also run the `Release` workflow manually from GitHub Actions and provide
a version number.
