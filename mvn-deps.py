import os
import pom

def parse_pom_file(file):
    return pom.Pom(file).parse()

def find_pom_file(dep, base):
    if 'relativePath' in dep:
        file = os.path.join(os.path.dirname(base), dep['relativePath'])
    else:
        file = '%s-%s.pom' % (dep['artifactId'], dep['version'])
        file = os.path.join('~/.m2/repository', dep['groupId'], dep['artifactId'], dep['version'], file)
    return file

# starting pom
root_pom_file = 'myartifact/pom.xml'
print(f"Parsing project pom: {root_pom_file}")
root_pom = parse_pom_file(root_pom_file)

# list parent poms
parent_poms = [ root_pom ]
parent_pom = root_pom
while parent_pom.parent is not None:
    parent_pom_file = find_pom_file(parent_pom.parent, parent_pom.file)
    print(f"Parsing parent pom: {parent_pom_file}")
    parent_pom = parse_pom_file(parent_pom_file)
    parent_poms.append(parent_pom)

# compute properties from root and all parents
print("Computing properties")
props = pom.properties(parent_poms)

# compute dependencies from root and all parents
print("Computing dependencyManagement")
depMgt = []
depMgtMap = {}
for p in parent_poms:
    for dep in p.dependencyManagement:
        key = (dep['groupId'], dep['artifactId'])
        dep = dep.copy()
        if key in depMgtMap:
            depMgt[depMgtMap[key]] = None
        depMgtMap[key] = len(depMgt)
        depMgt.append(dep)
print(depMgt)
print(depMgtMap)

# compute pom import in dependencyManagement
print("Computing pom import in dependencyManagement")
for dep in depMgt:
    pass

# compute dependencies from root and all parents
print("Computing dependencies")
deps = []
depsMap = {}
for p in reversed(parent_poms):
    for dep in p.dependencies:
        key = (dep['groupId'], dep['artifactId'])
        dep = dep.copy()
        if key in depsMap:
            deps[depsMap[key]] = None
        depsMap[key] = len(deps)
        deps.append(dep)
deps = [dep for dep in deps if dep is not None]
depsMap = None
print(deps)

# resolve properties in dependencies
print("Resolving properties in dependencies")
for dep in deps:
    if dep["version"] is None:
        key = (dep['groupId'], dep['artifactId'])
        if key in depMgtMap:
            depMgtDep = depMgt[depMgtMap[key]]
            if "version" in depMgtDep:
                dep["version"] = depMgtDep["version"]
                dep["sourceVersion"] = depMgtDep["sourceVersion"]
    if dep["version"] is None:
        raise Exception(f"Could not resolve version for {dep['groupId']}:{dep['artifactId']}")
    print(dep["version"])
    dep["version"] = pom.resolve(dep["version"], props)
