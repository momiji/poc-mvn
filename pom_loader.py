import os, pathlib, re
from pom_struct import PomProject, PomParent, PomDependency, PomProperties, PomPaths, PomInfos
from pom_reader import read_pom

cache: dict[str, PomProject] = {}
locations: dict[str, str] = {}

def load_pom_from_file(file: str) -> PomProject:
    """
    Load a pom file from its path.
    """
    file = os.path.abspath(file)
    if file in cache:
        return cache[file].clone()
    
    pom = read_pom(file)
    cache[file] = pom

    return pom.clone()


def load_pom_from_dependency(dependency: PomParent | PomDependency, base: str) -> PomProject:
    """
    Load a pom file from its dependency groupId, artifactId and version.
    """
    file = find_pom_location(dependency, base)
    return load_pom_from_file(file)


def find_pom_location(dependency: PomParent | PomDependency, base: str) -> str:
    """
    Find the location of the pom file of a dependency.
    """
    if dependency.fullname() in locations:
        return locations[dependency.fullname()]
    # try to load relativePath, maven silently ignore missing files
    if dependency.relativePath != "":
        file = os.path.join(os.path.dirname(base), dependency.relativePath)
        if os.path.exists(file):
            return file
    file = os.path.join(pathlib.Path.home(), '.m2/repository', dependency.groupId.replace(".", "/"), dependency.artifactId, dependency.version, f"{dependency.artifactId}-{dependency.version}.pom")
    return file


def register_pom_location(file: str):
    """
    Register the location of a pom file, so that it uses this file when searched by dependency.
    """
    pom = load_pom_from_file(file)
    load_pom_parents(pom)
    locations[pom.fullname()] = file


def load_pom_parents(pom: PomProject, props: PomProperties | None = None, paths: PomPaths | None = None):
    """
    Load the properties of a pom file into props, pom parents.
    It resolves only the necessary properties to find the parents.

    It returns all poms, from root to the top parent one.
    """
    props = PomProperties() if props is None else props
    paths = [] if paths is None else paths

    paths = paths + [ pom ]

    # add project properties
    for prop in pom.properties.values():
        props.add(prop.name, prop.value, paths)

    # resolve properties to find parent
    if pom.parent is not None:
        resolve_artifact(pom.parent, props, pom.builtins)
        pom.parent.pom = load_pom_from_dependency(pom.parent, pom.file)
        load_pom_parents(pom.parent.pom, props, paths)

    # resolve properties to get fullname
    resolve_artifact(pom, props, pom.builtins)


def resolve_artifact(infos: PomInfos, props: PomProperties, builtins: PomProperties):
    """
    Resolve groupId, artifactId and version.
    """
    infos.groupId = resolve_value(infos.groupId, props, builtins)
    infos.artifactId = resolve_value(infos.artifactId, props, builtins)
    infos.version = resolve_value(infos.version, props, builtins)

def resolve_value(value: str, props: PomProperties, builtins: PomProperties) -> str:
    """
    Resolve value using provided properties: ${name} -> value.
    """
    if '$' not in value: return value
    def resolve_match(match):
        key = match.group(1)
        prop = props.get(key, None)
        if prop is not None: return prop.value
        builtin = builtins.get(key, None)
        if builtin is not None: return builtin.value
        return match.group(0)

    original = value
    while True:
        value = re.sub(r'\$\{([^}]+)}', resolve_match, value)
        if original == value or '$' not in value:
            return value
        original = value


if __name__ == "__main__":
    # load pom
    pom1 = load_pom_from_file('myartifact/pom.xml')
    assert pom1.fullname() == 'mygroup:myartifact:${revision}'
    # register pom
    register_pom_location('myartifact/pom.xml')
    # load pom from dependency
    dep1 = PomDependency()
    dep1.groupId = 'mygroup'
    dep1.artifactId = 'myartifact'
    dep1.version = '1.0-SNAPSHOT'
    pom2 = load_pom_from_dependency(dep1, 'myartifact/pom.xml')
    # although it's found with version 1.0-SNAPSHOT, it's still unresolved
    assert pom2.fullname() == 'mygroup:myartifact:${revision}'
    # passed
    print("PASSED")
