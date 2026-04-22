#!/bin/bash
set -euo pipefail

FILE="$1"
ENTRY="$2"

mkdir -p "$(dirname "$FILE")"
printf "%s\n" "$ENTRY" >> "$FILE"
