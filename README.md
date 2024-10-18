## Projects

myartifact:
- parent: myparent
- dependency junit:
    - defined in parent dependencyManagement, default version is 5.11.0
    - used version 5.10.0 is defined in property
    - dependency:tree shows version 5.10.0 even though both 10 and 11 are downloaded
        - it's then not needed to analyze 5.11.0 => RULE 1

myparent:
- define junit-bom
- add openfeign-bom import with version xxx
- version is overriden in myartifact but is not used as properties inheritance is only for parents

## Rules

RULE_1

Project properties are computed by taking project properties, then parent properties that are not defined yet, ...
Therefore, if the parent uses a property overriden in project, it is the project one that wins.

    junit is in version 5.10.0 as specified in myartifact
    grp-core is in version 1.68.0 as specified un myparent

RULE_2

For dependencyManagement, we don't inherit project properties.
We always start with a fresh new empty props.

    commons-pool is in version 1.6 as specified in spring-boot dependencyManagement

The same applies for dependencies.

    jackson-databind is in version 2.17.2 as specified in dependency


## Install

Use script install.sh to build and install all pom into local m2 repository.
