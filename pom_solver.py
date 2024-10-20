from pom_loader import load_pom_parents, resolve_value, load_pom_from_file, resolve_artifact, load_pom_from_dependency
from pom_struct import PomProject, PomPaths, PomMgts, PomExclusion, PomProperties

ALL_SCOPES = {'compile': 'compile', 'provided': 'provided', 'runtime': 'runtime', 'system': 'system', 'test': 'test'}
ALL_SCOPES_KEYS = list(ALL_SCOPES.keys())

COMPILE_SCOPES = {'compile': 'compile', 'provided': 'provided', 'runtime': 'runtime', 'system': 'system'}
PROVIDED_SCOPES = {'compile': 'provided', 'provided': 'provided', 'runtime': 'provided', 'system': 'system'}
RUNTIME_SCOPES = {'compile': 'runtime', 'provided': 'runtime', 'runtime': 'runtime', 'system': 'system'}
TEST_SCOPES = {'compile': 'test', 'provided': 'test', 'runtime': 'test', 'test': 'test', 'system': 'system'}

NEW_SCOPES = {'compile': COMPILE_SCOPES, 'provided': PROVIDED_SCOPES, 'runtime': RUNTIME_SCOPES, 'test': TEST_SCOPES}

ORDERED_SCOPES = [ 'system', 'test', 'compile', 'provided', 'runtime' ]

Scopes = dict[str, str]
Exclusions = dict[str, PomExclusion]

def resolve_pom(pom: PomProject, paths: PomPaths | None = None, props: PomProperties | None = None, mgts: PomMgts | None = None, excls: Exclusions | None = None, scopes: Scopes | None = None, load_mgts = False, load_deps = False):
    """
    Resolve all dependencies a pom project.
    """
    if paths is None: paths = PomPaths()
    if props is None: props = PomProperties()
    if mgts is None: mgts = PomMgts()
    if excls is None: excls = Exclusions()
    if scopes is None: scopes = ALL_SCOPES

    pom.computed_properties = props
    pom.computed_managements = mgts

    # load all pom parents to resolve all properties
    load_pom_parents(pom, props = pom.computed_properties, paths = paths)
    resolve_properties(pom)

    # load all dependencyManagement
    if load_mgts:
        load_managements(pom, paths = paths)

    # load all dependencies
    if load_deps:
        load_dependencies(pom, paths = paths, scopes = scopes, excls = excls)


def resolve_properties(pom: PomProject):
    """
    Resolve all properties from pom.
    It is assumed that all properties have already been loaded.
    """
    for prop in pom.computed_properties.values():
        prop.value = resolve_value(prop.value, pom.computed_properties, pom.builtins)
    

def load_managements(pom: PomProject, curr: PomProject | None = None, paths: PomPaths | None = None):
    """
    Load all dependencyManagement from pom.
    It is assumed that all properties have already been loaded.

    1. Properties used for loading are the one loaded from pom
    2. Order of loading is direct > import > parent
    3. Imported dependencyManagement are loaded with new empty properties but current computed dependencyManagement
    """
    if curr is None: curr = pom
    if paths is None: paths = PomPaths()

    paths = paths + [ curr ]

    # normal dependencies
    for dep in curr.managements:
        # skip import dependencies
        if dep.type == 'pom' and dep.scope == 'import':
            continue
        resolve_artifact(dep, pom.computed_properties, curr.builtins)
        # fail on invalid scope
        if dep.scope != '' and dep.scope not in ALL_SCOPES_KEYS:
            raise Exception(f"Invalid scope {dep.scope} found in dependencyManagement {dep.fullname()} of pom {curr.fullname()}")
        # skip already loaded dependencies
        if dep.key_ga() in pom.computed_managements:
            continue
        # add to computed dependencies
        dep.paths = paths
        pom.computed_managements[dep.key_ga()] = dep

    # import dependencies
    for dep in curr.managements:
        # skip normal dependencies
        if dep.type != 'pom' or dep.scope != 'import':
            continue
        # skip already loaded dependencies
        resolve_artifact(dep, pom.computed_properties, curr.builtins)
        if dep.key_ga() in pom.computed_managements:
            continue
        # add to computed dependencies
        dep.paths = paths
        pom.computed_managements[dep.key_ga()] = dep
        # load dependencies from this import with new empty properties but current computed dependencyManagement
        dep_pom = load_pom_from_dependency(dep, curr.file)
        resolve_pom(dep_pom, paths = paths, mgts = pom.computed_managements, load_mgts = True)

    # load dependencies from parent, without using resolve_pom as all properties are already loaded
    if curr.parent is not None:
        load_managements(pom, curr.parent.pom, paths = paths)

def load_dependencies(pom: PomProject, paths: PomPaths | None = None, excls: Exclusions | None = None, scopes: Scopes | None = None):
    """
    Load all dependencies from pom.
    It is assumed that all properties have already been loaded.

    1. Properties used for loading are the one from current pom only
    2. DependencyManagement used for loading are the one from root pom only
    3. DependencyManagement overrides dependency version
    4. Exclusions from DependencyManagement are appended to dependencies
    """
    if paths is None: paths = PomPaths()
    if excls is None: excls = Exclusions()
    if scopes is None: scopes = ALL_SCOPES

    paths = paths + [ pom ]

    # dependencies
    deps = []
    for dep in pom.dependencies:
        # skip exclusions
        if dep.key_ga() in excls:
            continue
        # fail on invalid scope
        if dep.scope != '' and dep.scope not in ALL_SCOPES_KEYS:
            raise Exception(f"Invalid scope {dep.scope} found in dependency {dep.fullname()} of pom {pom.fullname()}")
        # skip not allowed scopes
        if dep.scope != '' and dep.scope not in scopes.keys():
            continue
        # override version and exclusions from dependencyManagement
        dep.paths = paths
        dep.pathsVersion = paths
        if dep.key_ga() in pom.computed_managements:
            mgt = pom.computed_managements[dep.key_ga()]
            if dep.version == '':
                dep.version = mgt.version
                dep.pathsVersion = mgt.paths
            if dep.scope == '': dep.scope = mgt.scope
            if dep.type == '': dep.type = mgt.type
            dep.version = mgt.version
            dep.paths = paths
            dep.pathsVersion = mgt.paths
            dep.exclusions.extend(mgt.exclusions)
        # update dependency with defaults
        if dep.scope == '': dep.scope = 'compile'
        if dep.type == '': dep.type = 'jar'
        dep.scope = scopes[dep.scope]
        # resolve artifact
        resolve_artifact(dep, pom.computed_properties, pom.builtins)
        # add to computed dependencies
        pom.computed_dependencies.append(dep)
        deps.append(dep)

    # dependencies recursion
    for dep in deps:
        dep_pom = load_pom_from_dependency(dep, pom.file)
        # build new mgts, excls and scopes to initialize recursion
        dep_mgts = pom.computed_managements.copy()
        dep_excls = excls | { excl.key():excl for excl in dep.exclusions }
        dep_scopes = NEW_SCOPES[dep.scope]
        # recursion
        resolve_pom(dep_pom, paths = paths, mgts = dep_mgts, excls = dep_excls, scopes = dep_scopes, load_mgts = True, load_deps = True)
        pom.computed_dependencies.extend(dep_pom.computed_dependencies)


if __name__ == "__main__":
    pom1 = load_pom_from_file('myartifact/pom.xml')
    resolve_pom(pom1)
    for dep1 in pom1.computed_managements.values():
        print(dep1.fullname())
