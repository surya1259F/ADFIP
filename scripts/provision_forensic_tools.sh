#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

OS_NAME="$(uname -s)"
OS_DESC="Unknown"
if [ -f /etc/os-release ]; then
  # shellcheck source=/dev/null
  . /etc/os-release
  OS_DESC="${PRETTY_NAME:-$NAME}"
fi

echo "ADFIR FORENSIC TOOL PROVISIONING"
echo "==============================="
echo ""
echo "Operating System: $OS_DESC ($OS_NAME)"

PKG_MGR="none"
if command -v apt-get >/dev/null 2>&1; then
  PKG_MGR="apt"
fi
echo "Package Manager: $PKG_MGR"
echo ""

# Ensure tools/bin directory exists for verified native sidecar binaries
mkdir -p "$ROOT_DIR/tools/bin"

echo "Checking Native Forensic Binaries:"

# 1. Sleuth Kit
if command -v fls >/dev/null 2>&1; then
  FLS_VER="$(fls -V 2>&1 | head -n 1)"
  echo "[OK] Sleuth Kit ($FLS_VER)"
elif [ -x "$ROOT_DIR/tools/bin/fls" ]; then
  FLS_VER="$("$ROOT_DIR/tools/bin/fls" -V 2>&1 | head -n 1)"
  echo "[OK] Sleuth Kit ($FLS_VER)"
else
  echo "[UNAVAILABLE] Sleuth Kit (fls) is not installed"
fi

# 2. YARA
if command -v yara >/dev/null 2>&1; then
  YARA_VER="$(yara --version 2>&1 | head -n 1)"
  echo "[OK] YARA (v$YARA_VER)"
elif [ -x "$ROOT_DIR/tools/bin/yara" ]; then
  YARA_VER="$("$ROOT_DIR/tools/bin/yara" --version 2>&1 | head -n 1)"
  echo "[OK] YARA (v$YARA_VER)"
else
  echo "[UNAVAILABLE] YARA is not installed"
fi

# 3. ExifTool
if command -v exiftool >/dev/null 2>&1; then
  EXIF_VER="$(exiftool -ver 2>&1 | head -n 1)"
  echo "[OK] ExifTool (v$EXIF_VER)"
elif [ -x "$ROOT_DIR/tools/bin/exiftool" ]; then
  EXIF_VER="$("$ROOT_DIR/tools/bin/exiftool" -ver 2>&1 | head -n 1)"
  echo "[OK] ExifTool (v$EXIF_VER)"
else
  echo "[UNAVAILABLE] ExifTool is not installed"
fi

# 4. Volatility 3
if command -v vol >/dev/null 2>&1; then
  VOL_VER="$(vol --version 2>&1 | head -n 1)"
  echo "[OK] Volatility 3 ($VOL_VER)"
elif [ -x "$ROOT_DIR/tools/bin/vol" ]; then
  VOL_VER="$("$ROOT_DIR/tools/bin/vol" --version 2>&1 | head -n 1)"
  echo "[OK] Volatility 3 ($VOL_VER)"
else
  echo "[UNAVAILABLE] Volatility 3 is not installed"
fi

echo ""
echo "Forensic tool validation check complete."
