from pom_loader import load_pom_parents, resolve_value, load_pom_from_file, resolve_artifact, load_pom_from_dependency, resolve_range_version
from pom_struct import PomProject, PomPaths, PomMgts, PomExclusion, PomProperties, PomDeps, PomDependency
from pom_tracer import *

# Scopes dict (parent scope) -> dict (dependency scope) -> new scope = None if skip as scope is not allowed or starting with '-' if scope is not transitive
# '?' means that the new scope is not yet defined to mimic maven behavior, and must be checked againt real samples
SCOPES = {
    'all':     { 'compile': 'compile' , 'test': 'test', 'runtime': 'runtime', 'provided': 'provided', '': 'compile', 'all': 'compile' },
    'compile': { 'compile': 'compile' , 'test': None  , 'runtime': 'runtime', 'provided': None, '': 'compile' },
    'test':    { 'compile': 'test'    , 'test': None  , 'runtime': 'test'   , 'provided': None, '': 'test'    },
    'runtime': { 'compile': 'runtime' , 'test': None  , 'runtime': 'runtime', 'provided': None, '': 'runtime' },
    'provided':{ 'compile': None      , 'test': None  , 'runtime': None     , 'provided': None, '': None      },
}
DEFAULT_SCOPE = 'all'
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

def resolve_pom(pom: PomProject, paths: PomPaths | None = None, initialMgts: PomMgts | None = None, computeMgts: PomMgts | None = None, excls: Exclusions | None = None, scope = DEFAULT_SCOPE, load_mgts = False, load_deps = False):
    """
    Resolve all dependencies a pom project.
    """
    if paths is None: paths = PomPaths()
    if initialMgts is None: initialMgts = PomMgts()
    if computeMgts is None: computeMgts = PomMgts()
    if excls is None: excls = Exclusions()

    trace = TRACER and TRACER.trace_poms() and TRACER.enter("pom | start", pom.gav(), 'scope', scope)

    top_pom = len(paths) == 0

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
    if top_pom:
        pom.added_dependencies = PomDeps()
        pom.computed_dependencies = PomMgts()

    # load all pom parents to resolve all properties
    load_pom_parents(pom, paths = paths, props = pom.computed_properties)

    # resolve all properties
    resolve_properties(pom)
    if TRACER:
        for prop in TRACER._props:
            if prop in pom.computed_properties:
                TRACER.trace("prop | property", pom.gav(), prop, pom.computed_properties[prop].value)

    # load all dependencyManagement
    if load_mgts:
        load_managements(pom, paths = paths)

    # load all dependencies
    # by using solvers, dependencies are loaded by depth, in hope it'll
    # minimize the number of dependencies to reload
    solvers = []
    if load_deps:
        solvers.extend(load_dependencies(pom, paths = paths, scope = scope, excls = excls))

    if top_pom:
        for solver in solvers:
            solvers.extend(solver())
        solvers.clear()

    if trace and TRACER: TRACER.exit("pom | end", pom.gav())

    return solvers


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
        curr.parent.pom.computed_scope = ''
        load_managements(pom, curr.parent.pom, paths = paths)

    # loop dependencies in pom order, as it can be manually changed
    for dep in curr.managements:
        dep = dep.copy()
        trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace2("mgt | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(paths))

        # resolve artifact
        resolve_artifact(dep, pom.computed_properties, curr.builtins)
        if trace and TRACER: TRACER.trace("mgt | resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # fail on invalid scope
        if dep.scope not in KNOWN_SCOPES:
            raise Exception(f"Invalid scope '{dep.scope}' found in dependencyManagement {dep.fullname()} of pom {curr.gav()}")

        if dep.type == 'pom' and dep.scope == 'import':
            # load dependencies from this import with new empty properties
            dep_pom = load_pom_from_dependency(dep, curr.file)
            assert dep_pom
            dep_pom.computed_scope = ''
            resolve_pom(dep_pom, paths = paths, computeMgts = pom.computed_managements, load_mgts = True)
        else:
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
        cur = pom.computed_managements[mgt.key_gat()]
        mgt = merge_management(cur, mgt)

    pom.computed_managements[mgt.key_gat()] = mgt
    return mgt


def load_dependencies(pom: PomProject, paths: PomPaths | None = None, excls: Exclusions | None = None, scope = DEFAULT_SCOPE):
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

    deps1: PomDeps = []
    deps2: PomDeps = []

    # as transitive is computed from path length, increment it only for non-parent
    paths = paths + [ pom ]
    transitive_only = paths[-1].computed_scope != 'all'

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
        dep_pom.relativePath = pom.parent.relativePath
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
        dep = dep.copy()
        trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace2("dep | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'paths', dump_paths(paths))
        
        # resolve artifact
        resolve_artifact(dep, pom.computed_properties, pom.builtins)
        if trace and TRACER: TRACER.trace2("dep | - resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # skip exclusions
        if dep.key_excl() in excls:
            continue

        # fail on invalid scope
        if dep.scope not in KNOWN_SCOPES and dep.scope != 'all':
            raise Exception(f"Invalid scope '{dep.scope}' found in dependency {dep.fullname()} of pom {pom.gav()}")
        
        # skip on non-supported types
        if dep.type in SKIP_TYPES:
            continue

        # fail on invalid type
        if dep.type not in ALL_TYPES:
            raise Exception(f"Invalid type '{dep.type}' found in dependency {dep.fullname()} of pom {pom.gav()}")
        
        # apply default values to dependency
        apply_default_to_dependency(pom, dep, paths)

        # transitive check
        # pom6 => C1 -> C2 (dm->T2) : C2 is lost if transitivity is checked against T. In pom6, C2 -> T2 is done by initial and not by default
        # this is why default is done before checking transitivity and initial is done after
        transitive_scope = SCOPES[scope][dep.scope]
        is_transitive = transitive_scope is None
        if transitive_only and is_transitive:
            if trace and TRACER: TRACER.trace2("dep | - skip (not transitive)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            continue

        # optional check
        # it is assumed it must stay around transitivity check :-)
        if transitive_only and dep.optional == 'true':
            if trace and TRACER: TRACER.trace2("dep | - skip (is optional)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            continue

        # apply initial values to dependency
        apply_initial_to_dependency(pom, dep, paths)

        # resolve artifact again
        resolve_artifact(dep, pom.computed_properties, pom.builtins)

        # lower scope if it too high
        # C -> C2 (dm->T2) -> C3 : C3 must be lowered to T3 as its parent is a T and no more a C
        max_scope = 'compile' if pom.computed_scope == 'all' else pom.computed_scope
        if dep.scope == '':
            dep.scope = max_scope
        if PRIORITY_SCOPES.index(dep.scope) < PRIORITY_SCOPES.index(max_scope):
            dep.scope = max_scope
        if trace and TRACER: TRACER.trace2("dep | - resolvd", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # resolve version if it is a range
        dep.version = resolve_range_version(dep)
        if dep.optional == '': dep.optional = 'false'
        if dep.optional not in ['true', 'false']:
            raise Exception(f"Invalid optional {dep.optional} found in dependency {dep.fullname()} of pom {pom.gav()}")
        if trace and TRACER: TRACER.trace2("dep | - fixed", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # skip already loaded dependencies
        skip = False
        if dep.key_excl() in pom.computed_dependencies:
            loaded = pom.computed_dependencies[dep.key_excl()]
            # can skip if same scope
            if PRIORITY_SCOPES.index(dep.scope) == PRIORITY_SCOPES.index(loaded.scope):
                if len(paths) >= len(loaded.paths):
                    if trace and TRACER: TRACER.trace2("dep | - skip (already loaded)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
                    skip = True
            # can skip if new scope is less important
            elif PRIORITY_SCOPES.index(dep.scope) >= PRIORITY_SCOPES.index(loaded.scope):
                    if trace and TRACER: TRACER.trace2("dep | - skip (already loaded)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
                    skip = True

        # update loaded deps
        if not skip:
            if dep.key_excl() in pom.computed_dependencies:
                # keep the one with the shortest path
                loaded = pom.computed_dependencies[dep.key_excl()]
                fixed = False
                # always keep the highest scope as it is used later to skip dependencies
                if PRIORITY_SCOPES.index(dep.scope) < PRIORITY_SCOPES.index(loaded.scope):
                    loaded.scope = dep.scope
                    fixed = True
                # overwrite all other properties, just updating loadedDeps as it is a copy
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
                pom.computed_dependencies[dep.key_excl()] = dep.copy()

        # add to computed dependencies
        pom.added_dependencies.append(dep)
        if not skip:
            if trace and TRACER: TRACER.trace("dep | added", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(paths))
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
        dep_pom.computed_scope = dep.scope

        # build new mgts, excls and scopes to initialize recursion
        dep_pom.added_dependencies = pom.added_dependencies
        dep_pom.computed_dependencies = pom.computed_dependencies
        dep_excls = excls | { excl.key():excl for excl in dep.exclusions }
        dep_scope = dep.scope

        # recursion
        solver = new_solver(pom, dep, paths, dep_pom, dep_inits, dep_excls, dep_scope)
        solvers.append(solver)
    
    # return
    return solvers


def new_solver(pom: PomProject, dep: PomDependency, paths: PomPaths, dep_pom: PomProject, dep_inits: PomMgts, dep_excls: dict[str, PomExclusion], dep_scope: str):
    def fn():
        if TRACER and TRACER.trace_poms(): TRACER.trace("dep | enter", dep.fullname2(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
        solvers = resolve_pom(dep_pom, paths = paths, initialMgts = dep_inits, excls = dep_excls, scope = dep_scope, load_mgts = True, load_deps = True)
        return solvers
    return fn


def new_initial_managements(initials: PomMgts, computed: PomMgts) -> PomMgts:
    """
    Create a new initial dependencyManagement from an initial and computed one.
    It is not needed to copy computed mgt as it is not modified later because it becomes an initial dependencyMangement.
    """
    new = computed #.copy()
    for ini in initials.values():
        if ini.key_gat() in computed:
            mgt = computed[ini.key_gat()]
            if TRACER and TRACER.trace_dep(mgt.key_trace()):
                TRACER.trace2("mgt | merging", ini.key_gat(), 'version', ini.version, 'scope', ini.scope, 'optional', ini.optional)
                TRACER.trace2("mgt | - applying forced from", ini.key_gat(), 'version', ini.version, 'scope', ini.scope, 'optional', ini.optional, 'paths', dump_paths(ini.paths))
            apply_forced_management(ini, mgt)
            if TRACER and TRACER.trace_dep(mgt.key_trace()):
                TRACER.trace("mgt | merged", mgt.key_gat(), 'version', mgt.version, 'scope', mgt.scope, 'optional', mgt.optional, 'paths', dump_paths(mgt.paths))
            new[ini.key_gat()] = mgt
        else:
            new[ini.key_gat()] = ini
    return new

def apply_default_to_dependency(pom: PomProject, dep: PomDependency, paths: PomPaths):
    """
    Update dependency with default values from dependencyManagement.
    """
    dep.paths = paths
    dep.pathsVersion = paths
    dep.pathsScope = paths
    dep.pathsOptional = paths
    dep.pathsExclusions = paths
    # apply computed_management which contains default values
    if dep.key_gat() in pom.computed_managements:
        mgt = pom.computed_managements[dep.key_gat()]
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace2("dep | - applying default from", mgt.key_gat(), 'version', mgt.version, 'scope', mgt.scope, 'optional', mgt.optional, 'paths', dump_paths(mgt.paths))
        apply_default_management(mgt, dep)
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace2("dep | - applied default", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(dep.paths))


def apply_initial_to_dependency(pom: PomProject, dep: PomDependency, paths: PomPaths):
    """
    Update dependency with initial values from dependencyManagement.
    """
    # apply initial_managements which contains imposed values
    if dep.key_gat() in pom.initial_managements:
        mgt = pom.initial_managements[dep.key_gat()]
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace2("dep | - applying initial from", mgt.key_gat(), 'version', mgt.version, 'scope', mgt.scope, 'optional', mgt.optional, 'paths', dump_paths(mgt.paths))
        apply_forced_management(mgt, dep)
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace2("dep | - applied initial", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(dep.paths))


def merge_management(old: PomDependency, new: PomDependency) -> PomDependency:
    """
    Return the dependencyManagement with the shorter path.
    """
    if len(new.paths) < len(old.paths):
        return new
    return old
    # """
    # Merge a dependencyManagement (new) onto an exising one (old). Returns a copy of old wihout modifying the original.
    # Overrides values of old only if old is empty or farther in the path.
    # """
    # old = old.copy()
    # if new.version != '':
    #     if old.version == '':
    #         # if old is empty, just use new
    #         old.version = new.version
    #         old.pathsVersion = new.pathsVersion
    #     elif len(new.pathsVersion) < len(old.pathsVersion):
    #         # if new is shorter, use it
    #         old.version = new.version
    #         old.pathsVersion = new.pathsVersion
    # if new.scope != '':
    #     if old.scope == '':
    #         # if old is empty, just use new
    #         old.scope = new.scope
    #         old.pathsScope = new.pathsScope
    #     elif PRIORITY_SCOPES.index(new.scope) < PRIORITY_SCOPES.index(old.scope):
    #         # if new is higher priority, use it
    #         old.scope = new.scope
    #         old.pathsScope = new.pathsScope
    #     elif PRIORITY_SCOPES.index(new.scope) == PRIORITY_SCOPES.index(old.scope) and len(new.pathsScope) < len(old.pathsScope):
    #         # if new is same priority but shorter path, use it
    #         old.scope = new.scope
    #         old.pathsScope = new.pathsScope
    # if new.optional != '':
    #     if old.optional == '':
    #         # if old is empty, just use new
    #         old.optional = new.optional
    #         old.pathsOptional = new.pathsOptional
    #     elif len(new.pathsOptional) < len(old.pathsOptional):
    #         # if new is shorter, use it
    #         old.optional = new.optional
    #         old.pathsOptional = new.pathsOptional
    # if len(new.exclusions) > 0:
    #     if len(old.exclusions) == 0:
    #         # if old is empty, just use new
    #         old.exclusions = new.exclusions
    #         old.pathsExclusions = new.pathsExclusions
    #     elif len(new.pathsExclusions) < len(old.pathsExclusions):
    #         # if new is shorter, use it
    #         old.exclusions = new.exclusions
    #         old.pathsExclusions = new.pathsExclusions
    # return old


def apply_default_management(mgt: PomDependency, dep: PomDependency):
    """
    Apply a dependencyManagement (mgt) onto a dependency (dep). Modifies dep.
    Overrides values of dep only if dep is empty.
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


def apply_forced_management(mgt: PomDependency, dep: PomDependency):
    """
    Apply an initial dependencyManagement (mgt) onto a dependency (dep). Modified dep.
    Override values of dep only if mgt is not empty.
    """
    if mgt.version != '':
        # if mgt is not empty, use it
        dep.version = mgt.version
        dep.pathsVersion = mgt.pathsVersion
    if mgt.scope != '':
        dep.scope = mgt.scope
        dep.pathsScope = mgt.pathsScope
        # if dep.scope == '':
        #     # if dep is empty, use it
        #     dep.scope = mgt.scope
        #     dep.pathsScope = mgt.pathsScope
        # elif PRIORITY_SCOPES.index(mgt.scope) < PRIORITY_SCOPES.index(dep.scope):
        #     # if mgt is higher priority, use it
        #     dep.scope = mgt.scope
        #     dep.pathsScope = mgt.pathsScope
        # elif PRIORITY_SCOPES.index(mgt.scope) == PRIORITY_SCOPES.index(dep.scope) and len(mgt.pathsScope) < len(dep.pathsScope):
        #     # if mgt is same priority but shorter path, use it
        #     dep.scope = mgt.scope
        #     dep.pathsScope = mgt.pathsScope
    if mgt.optional != '':
        # if mgt is not empty, use it
        dep.optional = mgt.optional
        dep.pathsOptional = mgt.pathsOptional
    if len(mgt.exclusions) > 0:
        # if mgt is not empty, use it
        dep.exclusions = mgt.exclusions
        dep.pathsExclusions = mgt.pathsExclusions


def dump_paths(paths: list[PomProject]):
    """
    Dump paths to a string.
    """
    if len(paths) == 1:
        return '.'
    return f"{len(paths)} / {' '.join([p.fullname() for p in paths[1:]])}"


if __name__ == "__main__":
    pom1 = load_pom_from_file('tests/pom1.xml')
    assert pom1
    pom1.computed_scope = 'all'
    resolve_pom(pom1)
    for dep1 in pom1.computed_managements.values():
        print(dep1.fullname())
    # passed
    print("PASSED")
