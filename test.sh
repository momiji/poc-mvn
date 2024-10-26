#!/bin/bash
set -Eeuo pipefail
cd "$(dirname "$0")"

t=$1
collect=0
module=myartifact

install -m 0755 -d tmp

[ -f tmp/test-$t.md5 ] || md5sum tests/pom$t.xml tests/pom$t-*.xml 2> /dev/null > tmp/test-$t.md5 ||:
md5sum tests/pom$t.xml tests/pom$t-*.xml 2> /dev/null > tmp/test-$t.md5.test ||:

# mvn collect
cmp tmp/test-$t.md5 tmp/test-$t.md5.test &> /dev/null || collect=1
[ -f tmp/test-$t.coll ] || collect=1

[ $collect = 1 ] && {
    mvn dependency:collect -f tests/pom$t.xml > tmp/test-$t.coll
    cp tmp/test-$t.md5.test tmp/test-$t.md5
}

rm tmp/test-$t.md5.test

cat tmp/test-$t.coll | sed -n "/---.*@ $module/,/---/p" | sed -n '/\[INFO\]   /p' | awk '{print $2}' | sort > tmp/test-$t.coll.sorted

# deps.py
python deps.py tests/pom$t.xml --sections deps -m $module | grep '^ ' | sed 's/^ *//' > tmp/test-$t.deps
cat tmp/test-$t.deps | sed 's/#.*//' | tr -d ' ' | sort -u | sed '/:parent:/d' > tmp/test-$t.deps.sorted

# compare
cmp tmp/test-$t.coll.sorted tmp/test-$t.deps.sorted 2> /dev/null || {
    echo "test $t failed"
    delta --diff-so-fancy -w 200 -s tmp/test-$t.coll.sorted tmp/test-$t.deps.sorted ||:
    exit 1
}

echo "test $t successful"
exit 0
