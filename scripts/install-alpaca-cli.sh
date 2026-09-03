#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="0.0.14"
system="$(uname -s | tr '[:upper:]' '[:lower:]')"
machine="$(uname -m)"

case "$system/$machine" in
  darwin/arm64)
    platform="darwin_arm64"
    checksum="142b26997157748e6db4146133f63066c29ef18be5857eae4b05f9d3157ccfd5"
    ;;
  darwin/x86_64)
    platform="darwin_amd64"
    checksum="9b2a420b6a3e2e0dbaf408d14c8ef1b9e01608764c84bf479e2839bca2f41246"
    ;;
  linux/x86_64)
    platform="linux_amd64"
    checksum="6c82ef31f94dd61aae1c90e40fc41fdfaf8111bd50e9a2780b9d8d304eb2ba66"
    ;;
  linux/aarch64 | linux/arm64)
    platform="linux_arm64"
    checksum="621270e2b935dbae587e6ae05fe04a10bc178b4c9c638961a3d0214568ff2617"
    ;;
  *)
    echo "Unsupported platform: $system/$machine" >&2
    exit 2
    ;;
esac

install_directory="$repository_root/.alpaca-cli"
temporary_directory="$(mktemp -d)"
archive="$temporary_directory/cli.tar.gz"
trap 'rm -rf "$temporary_directory"' EXIT

url="https://github.com/alpacahq/cli/releases/download/v${version}/cli_${version}_${platform}.tar.gz"
curl --fail --location --silent --show-error --output "$archive" "$url"

if command -v shasum >/dev/null 2>&1; then
  printf '%s  %s\n' "$checksum" "$archive" | shasum -a 256 -c -
else
  printf '%s  %s\n' "$checksum" "$archive" | sha256sum -c -
fi

mkdir -p "$install_directory"
tar -xzf "$archive" -C "$install_directory" alpaca LICENSE README.md
chmod 700 "$install_directory/alpaca"
"$install_directory/alpaca" version
