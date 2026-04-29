#!/usr/bin/env sh
set -eu

package_name="nut-counter"
version="${NUT_COUNTER_VERSION:-0.1.0}"
output_dir="${OUTPUT_DIR:-build}"
package_root="$(BUILD_ROOT="${BUILD_ROOT:-build/package-root}" OUTPUT_DIR="$output_dir" NUT_COUNTER_VERSION="$version" scripts/assemble-package.sh)"
deb_path="$output_dir/${package_name}_${version}_arm64.deb"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "dpkg-deb not found. Package layout assembled at $package_root" >&2
  echo "Run this command on Debian/Raspberry Pi OS to create $deb_path." >&2
  exit 127
fi

dpkg-deb --build --root-owner-group "$package_root" "$deb_path"
echo "$deb_path"
