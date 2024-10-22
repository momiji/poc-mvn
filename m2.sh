r=$1
a=${r%%:*}
r=${r#*:}
b=${r%%:*}
r=${r#*:}
c=${r%%:*}
r=${r#*:}
d=${r%%:*}

a=${a//.//}
[ -n "$d" ] && c=$d

cat ~/.m2/repository/$a/$b/$c/$b-$c.pom | bat --color=always | less -SR
