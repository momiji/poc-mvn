import os, pathlib, re
from pom_struct import PomProject, PomParent, PomDependency, PomProperties, PomPaths, PomInfos
from pom_reader import read_pom
from pom_tracer import *
from packaging.version import Version

M2_HOME = os.path.join(pathlib.Path.home(), '.m2/repository')

cache_poms: dict[str, PomProject] = {} # file -> pom
cache_deps: dict[str, str] = {}        # dep -> file

def load_pom_from_file(file: str, allow_missing = False) -> PomProject | None:
    """
    Load a pom file from its path.
    """
    file = os.path.abspath(file)
    if file in cache_poms:
        return cache_poms[file].copy()
    
    # if allow_missing and not os.path.exists(file):
    #     return None
    
    pom = read_pom(file)
    cache_poms[file] = pom

    return pom.copy()


def load_pom_from_dependency(dependency: PomParent | PomDependency, base: str, allow_missing = False) -> PomProject | None:
    """
    Load a pom file from its dependency groupId, artifactId and version.
    """
    file = find_pom_location(dependency, base)
    pom = load_pom_from_file(file, allow_missing = allow_missing)
    if pom: cache_deps[pom.gav()] = file
    return pom


def find_pom_location(dependency: PomParent | PomDependency, base: str) -> str:
    """
    Find the location of the pom file of a dependency.
    """
    if dependency.fullname() in cache_deps:
        return cache_deps[dependency.fullname()]
    # try to load relativePath, maven silently ignore missing files
    if dependency.relativePath != '' and not base.startswith(M2_HOME):
        file = os.path.join(os.path.dirname(base), dependency.relativePath)
        if os.path.exists(file):
            return file
    if isinstance(dependency, PomDependency) and dependency.version[:1] == '[':
        dependency.version = resolve_range_version(dependency)
    file = os.path.join(M2_HOME, dependency.groupId.replace(".", "/"), dependency.artifactId, dependency.version, f"{dependency.artifactId}-{dependency.version}.pom")
    return file


def resolve_range_version(dependency: PomDependency) -> str:
    """
    Find the version of a dependency, or return original version.
    """
    if dependency.version[:1] != '[':
        return dependency.version
    # get minimal version and maximal version
    min_version, max_version = dependency.version[1:-1].split(',')
    min_version = min_version.strip()
    max_version = max_version.strip()
    min_version = Version(min_version) if min_version != '' else None
    max_version = Version(max_version) if max_version != '' else None
    # list all folders in the repository
    dir = os.path.join(M2_HOME, dependency.groupId.replace(".", "/"), dependency.artifactId)
    if not os.path.exists(dir):
        return dependency.version
    versions = [ name for name in os.listdir(dir) if os.path.isdir(os.path.join(dir, name)) ]
    # filter versions
    highest = None
    for version in versions:
        version = Version(version)
        if (min_version is None or min_version <= version) and (max_version is None or version < max_version):
            if highest is None or version > highest:
                highest = version
    # return highest version
    if TRACER and TRACER.trace_range(dependency.key_trace()): TRACER.trace("ver | range", dependency.fullname(), 'version', highest)
    return str(highest) if highest is not None else dependency.version


def register_pom_locations(file: str, initialProps: PomProperties | None = None):
    """
    Register the location of a pom file, so that it uses this file when searched by dependency.

    Modules are also registered.
    """
    if initialProps is None: initialProps = PomProperties()

    file = os.path.abspath(file)
    pom = load_pom_from_file(file)
    assert pom

    # add initial properties, allowing submodules to have parent properties
    for prop in initialProps.values():
        pom.properties.addIfMissing(prop.name, prop.value)

    # load parents to resolve properties, but not in the pom as we don't provide props = pom.computed_properties
    # the only change on the pom should be groupId, artifactId and version
    # allowing to overwrite cache with a correct pom
    load_pom_parents(pom)
    cache_deps[pom.gav()] = pom.file
    cache_poms[file] = pom

    for module in pom.modules:
        module_file = os.path.join(os.path.dirname(file), module, 'pom.xml')
        register_pom_locations(module_file, initialProps = pom.properties)


def load_pom_parents(pom: PomProject, xinitialProps: PomProperties | None = None, props: PomProperties | None = None, paths: PomPaths | None = None):
    """
    Load the properties of a pom file into props, pom parents.
    It resolves only the necessary properties to find the parents.

    It returns all poms, from root to the top parent one.
    """
    if xinitialProps is None: xinitialProps = PomProperties()
    if props is None: props = PomProperties()
    if paths is None: paths = PomPaths()

    paths = paths + [ pom ]

    # add initial properties
    for prop in xinitialProps.values():
        props.set(prop.name, prop.value, paths)

    # add project properties
    for prop in pom.properties.values():
        props.addIfMissing(prop.name, prop.value, paths)

    # resolve properties to find parent
    if pom.parent is not None:
        resolve_artifact(pom.parent, props, pom.builtins)
        parent_pom = load_pom_from_dependency(pom.parent, pom.file)
        assert parent_pom
        pom.parent.pom = parent_pom
        load_pom_parents(pom.parent.pom, props = props, paths = paths)

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
    pom1 = load_pom_from_file('tests/pom1.xml')
    assert pom1 and pom1.gav() == 'mygroup:myartifact:${revision}'
    # register pom
    register_pom_locations('tests/pom1.xml')
    # load pom from dependency
    dep1 = PomDependency()
    dep1.groupId = 'mygroup'
    dep1.artifactId = 'myartifact'
    dep1.version = '1.0-SNAPSHOT'
    pom2 = load_pom_from_dependency(dep1, 'tests/pom1.xml')
    # although it's found with version 1.0-SNAPSHOT, it's still unresolved
    assert pom2 and pom2.gav() == 'mygroup:myartifact:1.0-SNAPSHOT'
    # passed
    print("PASSED")

    # find version
    dep1 = PomDependency()
    dep1.groupId = 'org.apache.maven'
    dep1.artifactId = 'maven-model'
    dep1.version = '[3.0,)'
    resolve_range_version(dep1)
    dep1 = PomDependency()
    dep1.groupId = 'org.apache.maven'
    dep1.artifactId = 'maven-model'
    dep1.version = '[3.0,4)'
    resolve_range_version(dep1)
    dep1 = PomDependency()
    dep1.groupId = 'org.apache.maven'
    dep1.artifactId = 'maven-model'
    dep1.version = '[,3.5)'
    resolve_range_version(dep1)
