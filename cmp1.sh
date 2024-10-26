#!/bin/bash
set -Eeuo pipefail

./cmp.sh ~/work/raven2/bug-json-parser/Jarvis/crr crr-compute-ecl cmp1 "$@"
