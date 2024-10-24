#!/bin/bash
set -Eeuo pipefail

d=$1
m=$2
p=$3

[ -f $p.x.coll ] || ( cd $d ; mvn dependency:collect ) > $p.x.coll
[ -f $p.x.deps ] || ( cd $d ; mvn dependency:tree ) > $p.x.tree
cat $p.x.coll | sed -n "/---.*@ $m/,/---/p" | sed -n '/\[INFO\]   /p' | awk '{print $2}' | sort > $p.x.sorted.coll

python deps.py $d/pom.xml --sections deps -m $m | grep '^ ' | sed 's/^ *//' > $p.x.deps
cat $p.x.deps | sed 's/#.*//' | tr -d ' ' | sort -u | sed '/:parent:/d' > $p.x.sorted.deps

diff -u $p.x.sorted.coll $p.x.sorted.deps
