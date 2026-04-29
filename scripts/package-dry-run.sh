#!/usr/bin/env sh
set -eu

required_paths="
dist/ui/index.html
backend/nut_counter/server.py
backend/nut_counter/streaming/webrtc.py
backend/nut_counter/streaming/sources.py
backend/nut_counter/streaming/ai.py
backend/nut_counter/hardware/gpio.py
backend/nut_counter/hardware/camera.py
backend/nut_counter/hardware/inference.py
bin/nut-counter
config/default-config.json
systemd/nut-counter-backend.service
systemd/nut-counter-kiosk.service
debian/DEBIAN/preinst
debian/DEBIAN/postinst
debian/DEBIAN/prerm
debian/DEBIAN/postrm
scripts/assemble-package.sh
scripts/build-deb.sh
"

missing=0
for path in $required_paths; do
  if [ ! -e "$path" ]; then
    echo "missing: $path" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "Package dry-run failed" >&2
  exit 1
fi

package_root="$(BUILD_ROOT="$(mktemp -d)/package-root" scripts/assemble-package.sh)"

layout_paths="
$package_root/DEBIAN/control
$package_root/opt/nut-counter/ui/index.html
$package_root/opt/nut-counter/backend/nut_counter/server.py
$package_root/opt/nut-counter/backend/nut_counter/hardware/gpio.py
$package_root/opt/nut-counter/config/default-config.json
$package_root/opt/nut-counter/systemd/nut-counter-backend.service
$package_root/opt/nut-counter/scripts/wait-for-backend.sh
$package_root/usr/bin/nut-counter
"

for path in $layout_paths; do
  if [ ! -e "$path" ]; then
    echo "missing assembled package path: $path" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "Package dry-run failed" >&2
  exit 1
fi

echo "Package dry-run passed: $package_root"
