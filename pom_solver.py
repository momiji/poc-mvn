from pom_loader import load_pom_parents, resolve_value, load_pom_from_file, resolve_artifact, load_pom_from_dependency
from pom_struct import PomProject, PomPaths, PomMgts, PomExclusion, PomProperties, PomDeps, PomDependency
from pom_tracer import *

# ALL_SCOPES = { '_name':'all', 'compile': 'compile', 'provided': 'provided', 'runtime': 'runtime', 'system': 'system', 'test': 'test', 'import': 'import', '': 'compile' }
# ALL_SCOPES_KEYS = list(ALL_SCOPES.keys())

# COMPILE_SCOPES = { '_name':'compile', 'compile': 'compile', 'provided': '?provided', 'runtime': '?runtime', 'system': '?system', '': 'compile' }
# PROVIDED_SCOPES = { '_name':'provided', 'compile': '?provided', 'provided': 'provided', 'runtime': '?provided', 'system': '?system', '': 'provided' }
# RUNTIME_SCOPES = { '_name':'runtime', 'compile': '?runtime', 'provided': '?runtime', 'runtime': 'runtime', 'system': '?system', '': 'runtime' }
# TEST_SCOPES = { '_name':'test', 'compile': 'compile', 'provided': '?provided', 'runtime': '?runtime', 'test': 'test', 'system': '?system', '': 'compile', '*': 'test' }

# NEW_SCOPES = {'compile': COMPILE_SCOPES, 'provided': PROVIDED_SCOPES, 'runtime': RUNTIME_SCOPES, 'test': TEST_SCOPES, 'system': None}

# TRANSITIVE_SCOPES = ['compile', 'runtime']


# Scopes dict (parent scope) -> dict (dependency scope) -> new scope if transitive, so pom can be loaded
SCOPES = {
    'all':     { 'compile': 'compile' , 'test': 'test', 'runtime': 'runtime', 'provided': None, '': 'compile' },
    'compile': { 'compile': 'compile' , 'test': None  , 'runtime': 'runtime', 'provided': None, '': 'compile' },
    'test':    { 'compile': 'compile' , 'test': None  , 'runtime': 'runtime', 'provided': None, '': 'compile' },
    'runtime': { 'compile': 'runtime' , 'test': None  , 'runtime': 'runtime', 'provided': None, '': 'runtime' },
    'provided':{ 'compile': '?'       , 'test': '?'   , 'runtime': '?'      , 'provided': '?' , '': '?'       },
}
ALL_SCOPES = 'all'
KNOWN_SCOPES = [ 'compile', 'test', 'runtime', 'provided', 'import', '' ]

# Scopes order when printing
ORDERED_SCOPES = [ 'compile', 'test', 'provided', 'runtime', 'system' ] # the higher wins

# Types check
ALL_TYPES = ['jar', 'pom']
SKIP_TYPES = ['test-jar', 'zip', 'dll', 'dylib','so']

Scopes = dict[str, str]
Exclusions = dict[str, PomExclusion]

def resolve_pom(pom: PomProject, paths: PomPaths | None = None, initialMgts: PomMgts | None = None, computeMgts: PomMgts | None = None, excls: Exclusions | None = None, scope = ALL_SCOPES, load_mgts = False, load_deps = False, transitive_only = False, directDepth = 0, loadedDeps: dict[str, int] | None = None):
    """
    Resolve all dependencies a pom project.
    """
    if paths is None: paths = PomPaths()
    if initialMgts is None: initialMgts = PomMgts()
    if computeMgts is None: computeMgts = PomMgts()
    if excls is None: excls = Exclusions()
    if loadedDeps is None: loadedDeps = {}

    trace = TRACER2 and TRACER2.trace_poms() and TRACER2.enter("pom | start", pom.fullname(), 'scope', scope)

    # skip loading pom if already loaded with same or lower path
    # if paths is not None and pom.fullname() in loaded:
    #     if loaded[pom.fullname()] <= len(paths):
    #         return
    # loaded[pom.key_excl()] = len(paths)

    # print(f"({len(paths)}) resolve_pom {pom.fullname()} count={len(loaded)}")

    # initial properties
    pom.computed_properties = PomProperties()

    # management that override dependency properties, in opposite to computed_managements that are defaults to empty dependencies.
    # intializing computed_managements with initialMgts allows to avoid doing it later
    pom.initial_managements = initialMgts
    pom.computed_managements = computeMgts

    # print(id(pom.initial_managements))
    # print(pom.initial_managements["joda-time:joda-time:jar"].fullname()) if "joda-time:joda-time:jar" in pom.initial_managements else print("not found")
    # print(id(pom.computed_managements))
    # print(pom.computed_managements["joda-time:joda-time:jar"].fullname()) if "joda-time:joda-time:jar" in pom.computed_managements else print("not found")

    # dependencies that are computed from dependencyManagement
    pom.computed_dependencies = PomDeps()

    # pom.computed_managements2 = initialMgts2

    # load all pom parents to resolve all properties
    load_pom_parents(pom, paths = paths, props = pom.computed_properties)

    # resolve all properties
    resolve_properties(pom)
    if TRACER2:
        for prop in TRACER2._props:
            if prop in pom.computed_properties:
                TRACER2.trace("prop | property", pom.fullname(), prop, pom.computed_properties[prop].value)

    # load all dependencyManagement
    if load_mgts:
        load_managements2(pom, paths = paths)
    
    if len(paths) == 0:
        print("*" * 200)
        print("*" * 200)
        print("*" * 200)

    # load all dependencies
    if load_deps:
        load_dependencies(pom, paths = paths, scope = scope, excls = excls, transitive_only = transitive_only, loadedDeps = loadedDeps)

    if trace and TRACER2: TRACER2.exit("pom | end", pom.fullname())


def resolve_properties(pom: PomProject):
    """
    Resolve all properties from pom.
    It is assumed that all properties have already been loaded.
    """
    for prop in pom.computed_properties.values():
        prop.value = resolve_value(prop.value, pom.computed_properties, pom.builtins)


def load_managements2(pom: PomProject, curr: PomProject | None = None, paths: PomPaths | None = None):
    """
    Load all dependencyManagement from pom.
    It is assumed that all properties have already been loaded.

    1. Properties used for loading are the one loaded from pom
    2. Order of loading is direct > parent > import
    3. Imported dependencyManagement are loaded with new empty properties
    """
    if curr is None: curr = pom
    if paths is None: paths = PomPaths()

    paths = paths + [ curr ]

    if curr.key_ga() == "com.amazonaws:aws-java-sdk-core":
        pass

    # load dependencies from parent, without using resolve_pom as all properties are already loaded
    if curr.parent is not None:
        if TRACER: TRACER.enter()
        load_managements2(pom, curr.parent.pom, paths = paths)
        if TRACER: TRACER.exit()

    # loop dependencies in pom order, as it can be manually changed
    for dep in curr.managements:
        if dep.type == 'pom' and dep.scope == 'import':
            trace = TRACER2 and TRACER2.trace_dep(dep.key_trace()) and TRACER2.trace2("mgt | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'paths', dump_paths(paths))
            # resolve artifact
            resolve_artifact(dep, pom.computed_properties, curr.builtins)
            if trace and TRACER2: TRACER2.trace("mgt | resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope)
            # fail on invalid scope
            if dep.scope not in KNOWN_SCOPES:
                raise Exception(f"Invalid scope '{dep.scope}' found in dependencyManagement {dep.fullname()} of pom {curr.fullname()}")
            # load dependencies from this import with new empty properties
            dep_pom = load_pom_from_dependency(dep, curr.file)
            assert dep_pom
            resolve_pom(dep_pom, paths = paths, computeMgts = pom.computed_managements, load_mgts = True)
        else:
            trace = TRACER2 and TRACER2.trace_dep(dep.key_trace()) and TRACER2.trace2("mgt | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'paths', dump_paths(paths))
            # resolve artifact
            resolve_artifact(dep, pom.computed_properties, curr.builtins)
            if trace and TRACER2: TRACER2.trace("mgt | resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope)
            # fail on invalid scope
            if dep.scope not in KNOWN_SCOPES:
                raise Exception(f"Invalid scope '{dep.scope}' found in dependencyManagement {dep.fullname()} of pom {curr.fullname()}")
            # merge with existing dependencyManagement
            dep = merge_managements2(pom, dep, paths)
            if trace and TRACER2: TRACER2.trace("mgt | merged", dep.key_gat(), 'version', dep.version, 'scope', dep.scope)


def merge_managements2(pom: PomProject, mgt: PomDependency, paths: PomPaths) -> PomDependency:
    """
    Merge a dependencyManagement with existing ones.
    This is used while loading a single pom, which is done in correct order direct > import > parent
    so we can rely on paths length to know which one has precedence.
    """
    mgt.paths = paths
    mgt.pathsVersion = paths
    mgt.pathsScope = paths
    mgt.pathsOptional = paths
    mgt.pathsExclusions = paths
    if mgt.key_gat() not in pom.computed_managements:
        pom.computed_managements[mgt.key_gat()] = mgt
        return mgt

    # it is needed to use a new mgt object to replace ini in the dictionary
    # because the dictionnary is just copied and cloned
    ini = pom.computed_managements[mgt.key_gat()]
    replace = True

    # if ini.key_gat() == "joda-time:joda-time:jar":
    #     print(id(pom.computed_managements))
    #     print(id(ini), ini.fullname2())

    # replace ini with new mgt
    if mgt.version != '' and (ini.version == '' or len(mgt.pathsVersion) < len(ini.pathsVersion)):
        if replace:
            ini = ini.copy()
            pom.computed_managements[mgt.key_gat()] = ini
            replace = False
        #
        ini.version = mgt.version
        ini.pathsVersion = mgt.pathsVersion
    if mgt.scope != '' and (ini.scope == '' or  len(mgt.pathsScope) < len(ini.pathsScope)):
        if replace:
            ini = ini.copy()
            pom.computed_managements[mgt.key_gat()] = ini
            replace = False
        #
        ini.scope = mgt.scope
        ini.pathsScope = mgt.pathsScope
    if mgt.optional != '' and (ini.optional == '' or len(mgt.pathsOptional) < len(ini.pathsOptional)):
        if replace:
            ini = ini.copy()
            pom.computed_managements[mgt.key_gat()] = ini
            replace = False
        #
        ini.optional = mgt.optional
        ini.pathsOptional = mgt.pathsOptional
    if len(mgt.exclusions) > 0 and (len(ini.exclusions) == 0 or len(mgt.pathsExclusions) < len(ini.pathsExclusions)):
        if replace:
            ini = ini.copy()
            pom.computed_managements[mgt.key_gat()] = ini
            replace = False
        #
        ini.exclusions.extend(mgt.exclusions)

    # if ini.key_gat() == "joda-time:joda-time:jar":
    #     print(id(ini), ini.fullname2())

    # replace ini with new mgt
    return ini


def load_dependencies(pom: PomProject, paths: PomPaths | None = None, excls: Exclusions | None = None, scope = ALL_SCOPES, transitive_only = False, direct = True, loadedDeps: dict[str, int] | None = None):
    """
    Load all dependencies from pom.
    It is assumed that all properties have already been loaded.

    1. Properties used for loading are the one from current pom only
    2. DependencyManagement used for loading are the one from root pom only
    3. DependencyManagement overrides dependency version
    4. Exclusions from DependencyManagement are appended to dependencies
    """
    direct = not transitive_only
    if paths is None: paths = PomPaths()
    if excls is None: excls = Exclusions()
    if loadedDeps is None: loadedDeps = {}

    paths = paths + [ pom ]

    if pom.key_ga() == "com.amazonaws:aws-java-sdk-core":
        pass

    # dependencies
    deps = []
    for dep in pom.dependencies:
        if dep.fullname2() == "com.amazonaws:aws-java-sdk-kms:jar:${awsjavasdk.version}":
            pass
        trace = TRACER2 and TRACER2.trace_dep(dep.key_trace()) and TRACER2.trace2("dep | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'paths', dump_paths(paths))
        # resolve artifact'
        resolve_artifact(dep, pom.computed_properties, pom.builtins)
        if trace and TRACER2: TRACER2.trace2("dep | - resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'optional', dep.optional)
        # skip exclusions
        if dep.key_excl() in excls:
            continue
        # fail on invalid scope
        if dep.scope not in KNOWN_SCOPES:
            raise Exception(f"Invalid scope '{dep.scope}' found in dependency {dep.fullname()} of pom {pom.fullname()}")
        # skip on non-supported types
        if dep.type in SKIP_TYPES:
            continue
        # fail on invalid type
        if dep.type not in ALL_TYPES:
            raise Exception(f"Invalid type {dep.type} found in dependency {dep.fullname()} of pom {pom.fullname()}")
        if dep.optional == '': dep.optional = 'false'
        if dep.optional not in ['true', 'false']:
            raise Exception(f"Invalid optional {dep.optional} found in dependency {dep.fullname()} of pom {pom.fullname()}")
        # override version and exclusions from dependencyManagement
        apply_managements(pom, dep, paths, direct)
        if trace and TRACER2: TRACER2.trace2("dep | - merged", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'optional', dep.optional)
        # skip already loaded
        if dep.key_excl() in loadedDeps and len(paths) >= loadedDeps[dep.key_excl()]:
            if trace and TRACER2: TRACER2.trace2("dep | - skip (already loaded)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'optional', dep.optional)
            continue
        # resolve artifact
        resolve_artifact(dep, pom.computed_properties, pom.builtins)
        if trace and TRACER2: TRACER2.trace2("dep | - fixed", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'optional', dep.optional)
        # update scope - this is totally hypothetical, and uses tables at top of this file to convert scopes
        new_scopes = SCOPES[scope]
        new_scope = new_scopes[dep.scope]
        # skip on non-transitive dependencies
        if new_scope is None:
            if trace and TRACER2: TRACER2.trace2("dep | - skip (not transitive)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'optional', dep.optional)
            continue
        if transitive_only and dep.optional == 'true':
            if trace and TRACER2: TRACER2.trace2("dep | - skip (is optional)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'optional', dep.optional)
            continue
        if new_scope not in KNOWN_SCOPES:
            raise Exception(f"Invalid scope '{new_scope}' found for dependency {dep.fullname2()} ({dep.scope}) of pom {pom.fullname()} ({scope})")
        # update scope after transitive checks, to keep test -> compile before compile is converted to test
        dep.scope = new_scope
        # add to computed dependencies
        pom.computed_dependencies.append(dep)
        if trace and TRACER2: TRACER2.trace("dep | import", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'direct', direct, 'optional', dep.optional, 'paths', dump_paths(paths))
        loadedDeps[dep.key_excl()] = len(paths)
        deps.append(dep)

    # dependencies recursion
    for dep in deps:
        if TRACER: TRACER.trace(f"recursion for dependency {dep.fullname()} with version={dep.version} scope={dep.scope} type={dep.type} optional={dep.optional}")
        if TRACER: TRACER.enter()
        trace = TRACER2 and TRACER2.trace_dep(dep.key_trace()) and TRACER2.trace2("dep | open", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
        dep_pom = load_pom_from_dependency(dep, pom.file, allow_missing = True)
        if dep_pom is None:
            if TRACER2 and TRACER2.trace_poms(): TRACER2.trace("dep | missing", dep.fullname2(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
            dep.not_found = True
            continue
        # build new mgts, excls and scopes to initialize recursion
        dep_mgts = pom.computed_managements.copy()
        dep_mgts2 = pom.computed_managements.copy()
        dep_excls = excls | { excl.key():excl for excl in dep.exclusions }
        dep_scope = dep.scope
        # recursion
        if TRACER2 and TRACER2.trace_poms(): TRACER2.trace("dep | resolve pom", dep.fullname2(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
        resolve_pom(dep_pom, paths = paths, initialMgts = dep_mgts, computeMgts = dep_mgts2, excls = dep_excls, scope = dep_scope, load_mgts = True, load_deps = True, transitive_only = True, loadedDeps = loadedDeps)
        pom.computed_dependencies.extend(dep_pom.computed_dependencies)
        if TRACER: TRACER.exit()


def apply_managements(pom: PomProject, dep: PomDependency, paths: PomPaths, direct: bool):
    """
    Apply dependencyManagement to a dependency.
    """
    dep.paths = paths
    dep.pathsVersion = paths
    # apply computed_management which contains default values
    if dep.key_gat() in pom.computed_managements:
        mgt = pom.computed_managements[dep.key_gat()]
        if dep.version == '' and mgt.version != '':
            dep.version = mgt.version
            dep.pathsVersion = mgt.pathsVersion
        if dep.scope == '' and mgt.scope != '':
            dep.scope = mgt.scope
            dep.pathsScope = mgt.pathsScope
        if dep.optional == '' and mgt.optional != '':
            dep.optional = mgt.optional
            dep.pathsOptional = mgt.pathsOptional
        if len(dep.exclusions) == 0 and len(mgt.exclusions) > 0:
            dep.exclusions.extend(mgt.exclusions)
            dep.pathsExclusions = mgt.pathsExclusions
    # apply initial_managements which contains imposed values
    if dep.key_gat() in pom.initial_managements:
        mgt = pom.initial_managements[dep.key_gat()]
        if mgt.version != '':
            dep.version = mgt.version
            dep.pathsVersion = mgt.pathsVersion
        if mgt.scope != '':
            dep.scope = mgt.scope
        if mgt.optional != '':
            dep.optional = mgt.optional
        dep.exclusions.extend(mgt.exclusions)


def dump_paths(paths: list[PomProject]):
    """
    Dump paths to a string.
    """
    if len(paths) == 1:
        return '.'
    return f"{len(paths)} / {' '.join([p.fullname() for p in paths[1:]])}]"


if __name__ == "__main__":
    pom1 = load_pom_from_file('myartifact/pom.xml')
    assert pom1
    resolve_pom(pom1)
    for dep1 in pom1.computed_managements.values():
        print(dep1.fullname())
