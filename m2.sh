r=$1
a=${r%%:*} ; a=${a//.//}
r=${r#*:}
b=${r%%:*}
r=${r#*:}
c=${r%%:*}
cat ~/.m2/repository/$a/$b/$c/$b-$c.pom | bat --color=always | less -SR
