#!/bin/bash
set -Eeuo pipefail

./cmp.sh ~/work/LTV/marvel-ltv marvel-ltv-upload-lambda cmp3 "$@"
