#!/usr/bin/env sh
set -eu

package_name="nut-counter"
version="${NUT_COUNTER_VERSION:-0.1.0}"
build_root="${BUILD_ROOT:-build/package-root}"
output_dir="${OUTPUT_DIR:-build}"
package_root="$build_root/$package_name"

rm -rf "$package_root"
mkdir -p "$package_root"
mkdir -p "$output_dir"

if [ ! -f dist/ui/index.html ]; then
  echo "dist/ui/index.html is missing. Run pnpm build first." >&2
  exit 1
fi

copy_dir() {
  source_dir="$1"
  target_dir="$2"
  mkdir -p "$target_dir"
  tar -C "$source_dir" -cf - . | tar -C "$target_dir" -xf -
}

install_file() {
  source_file="$1"
  target_file="$2"
  mode="$3"
  mkdir -p "$(dirname "$target_file")"
  cp "$source_file" "$target_file"
  chmod "$mode" "$target_file"
}

mkdir -p "$package_root/DEBIAN"
copy_dir debian/DEBIAN "$package_root/DEBIAN"

mkdir -p "$package_root/opt/nut-counter"
copy_dir dist/ui "$package_root/opt/nut-counter/ui"
copy_dir backend "$package_root/opt/nut-counter/backend"
copy_dir config "$package_root/opt/nut-counter/config"
copy_dir systemd "$package_root/opt/nut-counter/systemd"

install_file bin/nut-counter "$package_root/usr/bin/nut-counter" 0755
install_file scripts/wait-for-backend.sh "$package_root/opt/nut-counter/scripts/wait-for-backend.sh" 0755

find "$package_root/DEBIAN" -type f -exec chmod 0755 {} \;

control_file="$package_root/DEBIAN/control"
python3 - "$control_file" "$version" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
version = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
next_lines = []
for line in lines:
    if line.startswith("Version: "):
        next_lines.append(f"Version: {version}")
    else:
        next_lines.append(line)
path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
PY

echo "$package_root"
