#!/bin/bash
set -Eeuo pipefail
cd "$(dirname "$0")"

ls tests/pom*.xml | sed /parent/d | cut -d/ -f2 | cut -c4- | cut -d. -f1 | parallel -k "./test.sh {} 2>&1"
