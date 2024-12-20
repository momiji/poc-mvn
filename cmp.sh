#!/bin/bash
set -Eeuo pipefail

d=$1
m=$2
p=$3
[ "${4:-}" = "-f" ] && rm -f $p.x.*

[ -f $p.x.coll ] || ( cd $d ; mvn dependency:collect ) > $p.x.coll
[ -f $p.x.tree ] || ( cd $d ; mvn dependency:tree ) | sed -n "/---.*@ $m/,/---/p" > $p.x.tree
cat $p.x.coll | sed -n "/---.*@ $m/,/---/p" | sed -n '/\[INFO\]   /p' | awk '{print $2}' | sort > $p.x.sorted.coll

python deps.py -f $d/pom.xml --sections deps,tree -pl $m | sed -n "/^Dependencies/,/^Tree/p" | sed -n '/^ /p' | sed 's/^ *//' > $p.x.deps
cat $p.x.deps | sed 's/#.*//' | tr -d ' ' | sort -u | sed '/:parent:/d' > $p.x.sorted.deps

cmp $p.x.sorted.coll $p.x.sorted.deps 2> /dev/null || {
    echo "$p failed"
    delta --diff-so-fancy -w 200 -s $p.x.sorted.coll $p.x.sorted.deps ||:
    exit 1
}

echo "$p successful"
exit 0
