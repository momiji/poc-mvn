#!/bin/bash
set -Eeuo pipefail
cd "$(dirname "$0")"

install -m 0755 -d tmp

# install mygroup:myartifact with multiple versions to b able to test version ranges
for v in 1.0 1.1 1.2 1.3 2.0 2.1 ; do
    cat tests/sample.xml | sed "s/VERSION/$v/" > tmp/sample-$v.xml
    mvn install -f tmp/sample-$v.xml -DskipTests
done
