from pom_loader import load_pom_parents, resolve_value, load_pom_from_file, resolve_artifact, load_pom_from_dependency
from pom_struct import PomProject, PomPaths, PomMgts, PomExclusion, PomProperties, PomDeps, PomDependency
from pom_tracer import *

# Scopes dict (parent scope) -> dict (dependency scope) -> new scope = None if skip as scope is not allowed or starting with '-' if scope is not transitive
# '?' means that the new scope is not yet defined to mimic maven behavior, and must be checked againt real samples
SCOPES = {
    'all':     { 'compile': 'compile' , 'test': 'test', 'runtime': 'runtime', 'provided': 'provided', '': 'compile' },
    'compile': { 'compile': 'compile' , 'test': None  , 'runtime': 'runtime', 'provided': None, '': 'compile' },
    'test':    { 'compile': 'test'    , 'test': None  , 'runtime': 'test'   , 'provided': None, '': 'test'    },
    'runtime': { 'compile': 'runtime' , 'test': None  , 'runtime': 'runtime', 'provided': None, '': 'runtime' },
    'provided':{ 'compile': None      , 'test': None  , 'runtime': None     , 'provided': None, '': None      },
}
ALL_SCOPES = 'all'
KNOWN_SCOPES = [ 'compile', 'test', 'runtime', 'provided', 'import', '' ]
PRIORITY_SCOPES = [ 'all', 'compile', 'runtime', 'provided', 'system', 'test' ] # compile > test > ...

# Scopes order when printing
ORDERED_SCOPES = [ 'all', 'compile', 'test', 'provided', 'runtime', 'system' ] # compile > test > ...

# Types check
ALL_TYPES = [ 'jar', 'parent', 'pom' ]
SKIP_TYPES = [ 'test-jar', 'zip', 'dll', 'dylib', 'so' ]
SKIP_TYPES2 = [ 'pom' ]

Scopes = dict[str, str]
Exclusions = dict[str, PomExclusion]

def resolve_pom(pom: PomProject, paths: PomPaths | None = None, initialMgts: PomMgts | None = None, computeMgts: PomMgts | None = None, excls: Exclusions | None = None, scope = ALL_SCOPES, load_mgts = False, load_deps = False, transitive_only = False, directDepth = 0, loadedDeps: dict[str, PomDependency] | None = None):
    """
    Resolve all dependencies a pom project.
    """
    if paths is None: paths = PomPaths()
    if initialMgts is None: initialMgts = PomMgts()
    if computeMgts is None: computeMgts = PomMgts()
    if excls is None: excls = Exclusions()
    if loadedDeps is None: loadedDeps = {}

    trace = TRACER and TRACER.trace_poms() and TRACER.enter("pom | start", pom.fullname(), 'scope', scope)

    assert pom.groupId
    assert pom.artifactId
    assert pom.version

    # initial properties
    pom.computed_properties = PomProperties()

    # management that override dependency properties, in opposite to computed_managements that are defaults to empty dependencies.
    # intializing computed_managements with initialMgts allows to avoid doing it later
    pom.initial_managements = initialMgts
    pom.computed_managements = computeMgts

    # dependencies that are computed from dependencyManagement
    pom.computed_dependencies = PomDeps()

    # load all pom parents to resolve all properties
    load_pom_parents(pom, paths = paths, props = pom.computed_properties)

    # resolve all properties
    resolve_properties(pom)
    if TRACER:
        for prop in TRACER._props:
            if prop in pom.computed_properties:
                TRACER.trace("prop | property", pom.fullname(), prop, pom.computed_properties[prop].value)

    # load all dependencyManagement
    if load_mgts:
        load_managements(pom, paths = paths)

    # load all dependencies
    if load_deps:
        solvers = []
        solvers.extend(load_dependencies(pom, paths = paths, scope = scope, excls = excls, transitive_only = transitive_only, loadedDeps = loadedDeps))
        for solver in solvers:
            solver()

    if trace and TRACER: TRACER.exit("pom | end", pom.fullname())


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

    1. Properties used for loading are the one loaded from pom (pom.current_properties)
    2. Order of loading is direct > parent > import, and then appearance in pom
    3. Imported dependencyManagement are loaded with new empty properties
    """
    if curr is None: curr = pom
    if paths is None: paths = PomPaths()

    paths = paths + [ curr ]

    # load dependencies from parent, without using resolve_pom as all properties are already loaded
    if curr.parent is not None:
        load_managements(pom, curr.parent.pom, paths = paths)

    # loop dependencies in pom order, as it can be manually changed
    for dep in curr.managements:
        if dep.type == 'pom' and dep.scope == 'import':
            trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace2("mgt | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(paths))
            # resolve artifact
            resolve_artifact(dep, pom.computed_properties, curr.builtins)
            if trace and TRACER: TRACER.trace("mgt | resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            # fail on invalid scope
            if dep.scope not in KNOWN_SCOPES:
                raise Exception(f"Invalid scope '{dep.scope}' found in dependencyManagement {dep.fullname()} of pom {curr.fullname()}")
            # load dependencies from this import with new empty properties
            dep_pom = load_pom_from_dependency(dep, curr.file)
            assert dep_pom
            resolve_pom(dep_pom, paths = paths, computeMgts = pom.computed_managements, load_mgts = True)
        else:
            trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace2("mgt | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(paths))
            # resolve artifact
            resolve_artifact(dep, pom.computed_properties, curr.builtins)
            if trace and TRACER: TRACER.trace("mgt | resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            # fail on invalid scope
            if dep.scope not in KNOWN_SCOPES:
                raise Exception(f"Invalid scope '{dep.scope}' found in dependencyManagement {dep.fullname()} of pom {curr.fullname()}")
            # merge with existing dependencyManagement
            dep = resolve_management(pom, dep, paths)
            if trace and TRACER: TRACER.trace("mgt | merged", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)


def resolve_management(pom: PomProject, mgt: PomDependency, paths: PomPaths) -> PomDependency:
    """
    Merge a dependencyManagement with existing ones.
    This is used while loading a single pom, which is done in correct order direct > import > parent
    so we can rely on paths length to know which one has precedence.
    Beware to untouch the original objects.
    """
    mgt.paths = paths
    mgt.pathsVersion = paths
    mgt.pathsScope = paths
    mgt.pathsOptional = paths
    mgt.pathsExclusions = paths

    if mgt.key_gat() in pom.computed_managements:
        cur = pom.computed_managements[mgt.key_gat()].copy()
        mgt = merge_management(cur, mgt)

    pom.computed_managements[mgt.key_gat()] = mgt
    return mgt


def load_dependencies(pom: PomProject, paths: PomPaths | None = None, excls: Exclusions | None = None, scope = ALL_SCOPES, transitive_only = False, loadedDeps: dict[str, PomDependency] | None = None):
    """
    Load all dependencies from pom.
    It is assumed that all properties have already been loaded.

    1. Properties used for loading are the one from current pom only
    2. DependencyManagement used for loading are the one from root pom only
    3. DependencyManagement may overrides dependency version, see apply_managements
    4. Dependencies from parent are also loaded
    """
    if paths is None: paths = PomPaths()
    if excls is None: excls = Exclusions()
    if loadedDeps is None: loadedDeps = {}

    paths = paths + [ pom ]
    transitive_only = len(paths) > 1

    deps1 = []
    deps2 = []

    # load dependencies from parent, without using resolve_pom as all properties are already loaded
    if pom.parent is not None:
        dep_pom = PomDependency()
        dep_pom.groupId = pom.parent.groupId
        dep_pom.artifactId = pom.parent.artifactId
        dep_pom.version = pom.parent.version
        dep_pom.scope = scope
        dep_pom.type = 'parent'
        dep_pom.classifier = ''
        dep_pom.optional = 'false'
        dep_pom.paths = paths
        dep_pom.exclusions = []
        dep_pom.relativePath = ''
        dep_pom.not_found = False
        dep_pom.pathsVersion = paths
        dep_pom.pathsScope = paths
        dep_pom.pathsOptional = paths
        dep_pom.pathsExclusions = paths
        deps1.append(dep_pom)

    # load dependencies in pom order, as it can be manually changed
    deps1.extend(pom.dependencies)

    # scan dependencies to fix and skip
    for dep in deps1:
        trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace2("dep | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'paths', dump_paths(paths))
        # resolve artifact'
        resolve_artifact(dep, pom.computed_properties, pom.builtins)
        if trace and TRACER: TRACER.trace2("dep | - resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
        # skip exclusions
        if dep.key_excl() in excls:
            continue
        # fail on invalid scope
        if dep.scope not in KNOWN_SCOPES and dep.scope != 'all':
            raise Exception(f"Invalid scope '{dep.scope}' found in dependency {dep.fullname()} of pom {pom.fullname()}")
        # skip on non-supported types
        if dep.type in SKIP_TYPES:
            continue
        # fail on invalid type
        if dep.type not in ALL_TYPES:
            raise Exception(f"Invalid type '{dep.type}' found in dependency {dep.fullname()} of pom {pom.fullname()}")
        # override version and exclusions from dependencyManagement
        apply_to_dependency(pom, dep, paths)
        if trace and TRACER: TRACER.trace2("dep | - applied", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
        # resolve artifact
        resolve_artifact(dep, pom.computed_properties, pom.builtins)
        if dep.optional == '': dep.optional = 'false'
        if dep.optional not in ['true', 'false']:
            raise Exception(f"Invalid optional {dep.optional} found in dependency {dep.fullname()} of pom {pom.fullname()}")
        if trace and TRACER: TRACER.trace2("dep | - fixed", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
        # update scope - this is totally hypothetical, and uses tables at top of this file to convert scopes
        new_scopes = SCOPES[scope]
        new_scope = new_scopes[dep.scope] if dep.scope != 'all' else 'all'
        # skip on non-transitive dependencies
        if new_scope is None:
            if trace and TRACER: TRACER.trace2("dep | - skip (not allowed)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            continue
        if transitive_only and new_scope[0] == '-':
            if trace and TRACER: TRACER.trace2("dep | - skip (not transitive)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            continue
        if dep.optional == 'true':
            if trace and TRACER: TRACER.trace2("dep | - skip (is optional)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            continue
        if new_scope[0] == '-': new_scope = new_scope[1:]
        if new_scope not in KNOWN_SCOPES and new_scope != 'all':
            raise Exception(f"Invalid scope '{new_scope}' found for dependency {dep.fullname2()} ({dep.scope}) of pom {pom.fullname()} ({scope})")
        # update scope after transitive checks, to keep test -> compile before compile is converted to test
        dep.scope = new_scope
        # skip already loaded
        if dep.key_excl() in loadedDeps:
            loaded = loadedDeps[dep.key_excl()]
            # can skip if same scope
            if PRIORITY_SCOPES.index(dep.scope) == PRIORITY_SCOPES.index(loaded.scope):
                if len(paths) >= len(loaded.paths):
                    if trace and TRACER: TRACER.trace2("dep | - skip (already loaded)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
                    continue
            # can skip if new scope is less important
            elif PRIORITY_SCOPES.index(dep.scope) >= PRIORITY_SCOPES.index(loaded.scope):
                    if trace and TRACER: TRACER.trace2("dep | - skip (already loaded)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
                    continue
            # need to change loaded
        # update loaded deps
        if dep.key_excl() in loadedDeps:
            # keep the one with the shortest path
            loaded = loadedDeps[dep.key_excl()]
            fixed = False
            # keep the highest scope as it is used later to skip dependencies
            if PRIORITY_SCOPES.index(dep.scope) < PRIORITY_SCOPES.index(loaded.scope):
                loaded.scope = dep.scope
                fixed = True
            # overwrite all other properties, just updating loadedDeps is not enough
            # as dep is already added to some computed_dependencies
            if len(paths) < len(loaded.paths):
                loaded.version = dep.version
                loaded.type = dep.type
                loaded.classifier = dep.classifier
                loaded.optional = dep.optional
                loaded.paths = dep.paths
                loaded.exclusions = dep.exclusions
                loaded.relativePath = dep.relativePath
                loaded.not_found = dep.not_found
                loaded.pathsVersion = dep.pathsVersion
                loaded.pathsScope = dep.pathsScope
                loaded.pathsOptional = dep.pathsOptional
                loaded.pathsExclusions = dep.pathsExclusions
                fixed = True
            # trace change
            if trace and TRACER and fixed: TRACER.trace2("dep | - loaded updated", loaded.key_gat(), 'version', loaded.version, 'scope', loaded.scope, 'optional', loaded.optional, 'paths', dump_paths(loaded.paths))
        else:
            loadedDeps[dep.key_excl()] = dep
        # add to computed dependencies
        pom.computed_dependencies.append(dep)
        if trace and TRACER: TRACER.trace("dep | import", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(paths))
        deps2.append(dep)

    # dependencies recursion
    dep_inits = new_initial_managements(pom.initial_managements, pom.computed_managements)
    solvers = []
    for dep in deps2:
        # skip on non-supported types
        if dep.type in SKIP_TYPES2:
            continue
        # prepare depenency for recursion
        trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace2("dep | open", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
        dep_pom = load_pom_from_dependency(dep, pom.file, allow_missing = True)
        if dep_pom is None:
            if TRACER and TRACER.trace_poms(): TRACER.trace("dep | missing", dep.fullname2(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
            dep.not_found = True
            continue
        # build new mgts, excls and scopes to initialize recursion
        dep_excls = excls | { excl.key():excl for excl in dep.exclusions }
        dep_scope = dep.scope
        # recursion
        solvers.append(solver(pom, dep, dep_pom, paths, dep_inits, dep_excls, dep_scope, loadedDeps))
    
    return solvers


def solver(pom: PomProject, dep: PomDependency, dep_pom: PomProject, paths: PomPaths, dep_inits: PomMgts, dep_excls: Exclusions, dep_scope: str, loadedDeps: dict[str, PomDependency]):
    def fn():
        if TRACER and TRACER.trace_poms(): TRACER.trace("dep | resolve pom", dep.fullname2(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
        resolve_pom(dep_pom, paths = paths, initialMgts = dep_inits, excls = dep_excls, scope = dep_scope, load_mgts = True, load_deps = True, transitive_only = True, loadedDeps = loadedDeps)
        pom.computed_dependencies.extend(dep_pom.computed_dependencies)
    return fn


def new_initial_managements(initials: PomMgts, computed: PomMgts) -> PomMgts:
    """
    Create a new initial dependencyManagement from an initial and computed one.
    It is not needed to copy computed mgt as it is not modified later because it becomes an initial dependencyMangement.
    """
    new = computed.copy()
    for ini in initials.values():
        if ini.key_gat() in computed:
            mgt = computed[ini.key_gat()]
            apply_initial(ini, mgt)
            new[ini.key_gat()] = mgt
        else:
            new[ini.key_gat()] = ini
    return new

def apply_to_dependency(pom: PomProject, dep: PomDependency, paths: PomPaths):
    """
    Apply dependencyManagement to a dependency.
    """
    dep.paths = paths
    dep.pathsVersion = paths
    dep.pathsScope = paths
    dep.pathsOptional = paths
    dep.pathsExclusions = paths
    # apply computed_management which contains default values
    if dep.key_gat() in pom.computed_managements:
        mgt = pom.computed_managements[dep.key_gat()]
        apply_management(mgt, dep)
    # apply initial_managements which contains imposed values
    if dep.key_gat() in pom.initial_managements:
        mgt = pom.initial_managements[dep.key_gat()]
        apply_initial(mgt, dep)


def merge_management(old: PomDependency, new: PomDependency) -> PomDependency:
    """
    Merge a dependencyManagement (new) onto an exising one (old).
    Overrides only if old is empty or farther in the path.
    """
    if new.version != '' and (old.version == '' or len(new.pathsVersion) < len(old.pathsVersion)):
        old.version = new.version
        old.pathsVersion = new.pathsVersion
    if new.scope != '' and (old.scope == '' or len(new.pathsScope) < len(old.pathsScope)):
        old.scope = new.scope
        old.pathsScope = new.pathsScope
    if new.optional != '' and (old.optional == '' or len(new.pathsOptional) < len(old.pathsOptional)):
        old.optional = new.optional
        old.pathsOptional = new.pathsOptional
    if len(new.exclusions) > 0 and (len(old.exclusions) == 0 or len(new.pathsExclusions) < len(old.pathsExclusions)):
        old.exclusions = new.exclusions
        old.pathsExclusions = new.pathsExclusions
    return old

def apply_management(mgt: PomDependency, dep: PomDependency):
    """
    Apply a dependencyManagement (mgt) onto a dependency (dep).
    Overrides only if dep is empty.
    """
    if mgt.version != '' and dep.version == '':
        dep.version = mgt.version
        dep.pathsVersion = mgt.pathsVersion
    if mgt.scope != '' and dep.scope == '':
        dep.scope = mgt.scope
        dep.pathsScope = mgt.pathsScope
    if mgt.optional != '' and dep.optional == '':
        dep.optional = mgt.optional
        dep.pathsOptional = mgt.pathsOptional
    if len(mgt.exclusions) > 0 and len(dep.exclusions) == 0:
        dep.exclusions = mgt.exclusions
        dep.pathsExclusions = mgt.pathsExclusions

def apply_initial(ini: PomDependency, dep: PomDependency):
    """
    Apply an initial dependencyManagement (ini) onto a dependency (mgt).
    Override values only if ini is not empty.
    """
    if ini.version != '':
        dep.version = ini.version
        dep.pathsVersion = ini.pathsVersion
    if ini.scope != '':
        if dep.scope == '' or PRIORITY_SCOPES.index(ini.scope) < PRIORITY_SCOPES.index(dep.scope):
            dep.scope = ini.scope
            dep.pathsScope = ini.pathsScope
    if ini.optional != '':
        dep.optional = ini.optional
        dep.pathsOptional = ini.pathsOptional
    if len(ini.exclusions) > 0:
        dep.exclusions = ini.exclusions
        dep.pathsExclusions = ini.pathsExclusions


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
