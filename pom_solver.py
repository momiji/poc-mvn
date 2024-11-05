from pom_loader import load_pom_parents, resolve_value, load_pom_from_file, resolve_artifact, load_pom_from_dependency, resolve_range_version
from pom_struct import PomProject, PomPaths, PomMgts, PomExclusion, PomProperties, PomDeps, PomDependency, PomExclusions
from pom_tracer import *
from packaging.version import Version
import platform

# Scopes dict (parent scope) -> dict (dependency scope) -> new scope = None if skip as scope is not allowed or starting with '-' if scope is not transitive
# '?' means that the new scope is not yet defined to mimic maven behavior, and must be checked against real samples
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

JDK = '21.0.2'
OS_NAME = platform.system().lower()
OS_ARCH = "amd64" if platform.machine().lower() == "x86_64" else platform.machine().lower()
OS_VERSION = platform.release().lower()
OS_FAMILY = "windows" if OS_NAME == "windows" else "unix"

Scopes = dict[str, str]

def resolve_pom(pom: PomProject, paths: PomPaths | None = None, initialProps: PomProperties | None = None, initialMgts: PomMgts | None = None, computeMgts: PomMgts | None = None, excls: PomExclusions | None = None, scope = DEFAULT_SCOPE, load_mgts = False, load_deps = False):
    """
    Resolve all dependencies a pom project.
    """
    if paths is None: paths = PomPaths()
    if initialProps is None: initialProps = PomProperties()
    if initialMgts is None: initialMgts = PomMgts()
    if computeMgts is None: computeMgts = PomMgts()
    if excls is None: excls = PomExclusions()

    if TRACER: TRACER.set_ctx("==> POM", pom.gav(), 'scope', pom.computed_scope, 'paths', dump_paths(paths))

    if TRACER and TRACER.trace_poms():
        TRACER.trace("")

    top_pom = paths.length == 0

    assert pom.groupId
    assert pom.artifactId
    assert pom.version

    # initial properties
    pom.computed_scope = scope
    pom.computed_properties = initialProps
    pom.computed_exclusions = excls

    # management that override dependency properties, in opposite to computed_managements that are defaults to empty dependencies.
    # initializing computed_managements with initialMgts allows to avoid doing it later
    pom.initial_managements = initialMgts
    pom.computed_managements = computeMgts

    # dependencies that are computed from dependencyManagement
    if top_pom:
        pom.added_dependencies = PomDeps()
        pom.computed_dependencies = PomMgts()
        pom.computed_type = 'pom'
        os.chdir(os.path.dirname(pom.file))

    # load all pom parents to resolve all properties
    load_pom_parents(pom, paths = paths, props = pom.computed_properties)

    # resolve profiles
    resolve_profiles(pom)

    # resolve all properties
    resolve_properties(pom)
    if TRACER:
        for prop in pom.computed_properties.values():
            if TRACER.trace_prop(prop.name):
                TRACER.trace("prop | property", pom.gav(), prop.name, prop.value)

    # load all dependencyManagement
    if load_mgts:
        load_managements(pom, paths = paths)

    # load all dependencies
    # by using solvers, dependencies are loaded by depth, in hope it'll
    # minimize the number of dependencies to reload
    solvers = []
    if load_deps:
        solvers.extend(load_dependencies(pom, paths = paths))

    if top_pom:
        for solver in solvers:
            solvers.extend(solver())
        solvers.clear()

    return solvers


def resolve_properties(pom: PomProject):
    """
    Resolve all properties from pom.
    It is assumed that all properties have already been loaded.
    """
    for prop in pom.computed_properties.values():
        prop.value = resolve_value(prop.value, pom.computed_properties, pom.builtins)


def resolve_profiles(pom: PomProject):
    # skip unsupported profiles
    if len(pom.profiles) == 0: return
    #
    profiles = []
    for profile in pom.profiles:
        if len(profile.dependencies) == 0 and len(profile.managements) == 0 and len(profile.properties) == 0 and len(profile.modules) == 0: continue
        if profile.active_by_default: continue
        if profile.jdk != '':
            if check_version(profile.jdk, JDK):
                profiles.append(profile)
                continue
        if profile.os_name != '' or profile.os_family != '' or profile.os_arch != '' or profile.os_version != '':
            if profile.os_name != '':
                if profile.os_name[0] == '!' and profile.os_name.lower() == OS_NAME: continue
                if profile.os_name[0] != '!' and profile.os_name.lower() != OS_NAME: continue
            if profile.os_family != '':
                if profile.os_family[0] == '!' and profile.os_family.lower() == OS_FAMILY: continue
                if profile.os_family[0] != '!' and profile.os_family.lower() != OS_FAMILY: continue
            if profile.os_arch != '':
                if profile.os_arch[0] == '!' and profile.os_arch.lower() == OS_ARCH: continue
                if profile.os_arch[0] != '!' and profile.os_arch.lower() != OS_ARCH: continue
            if profile.os_version != '':
                WARN(f"skip profile '{profile.id}' in pom '{pom.gav()}': unsupported os.version activation '{profile.os_version}'")
                continue
            profiles.append(profile)
            continue
        if profile.property_name != '':
            if profile.property_name[0] == '!':
                if profile.property_name[1:] not in pom.computed_properties:
                    continue
            else:
                if profile.property_value == '':
                    if profile.property_name not in pom.computed_properties:
                        continue
                else:
                    if profile.property_name not in pom.computed_properties:
                        continue
                    pv = resolve_value(profile.property_value, pom.computed_properties, pom.builtins)
                    cv = resolve_value(pom.computed_properties[profile.property_name].value, pom.computed_properties, pom.builtins)
                    if '$' in pv:
                        WARN(f"skip profile '{profile.id}' in pom '{pom.gav()}': unsupported '$' in activation '{pv}'")
                        continue
                    if '$' in cv:
                        WARN(f"skip profile '{profile.id}' in pom '{pom.gav()}': unsupported '$' in activation '{cv}'")
                        continue
                    if cv != pv:
                        continue
            profiles.append(profile)
            continue
        if profile.file_exists != '' or profile.file_missing != '':
            if '$' in profile.file_exists or '$' in profile.file_missing:
                WARN(f"skip profile '{profile.id}' in pom '{pom.gav()}': unsupported '$' in activation '{profile.file_exists}{profile.file_missing}'")
                continue
            if profile.file_exists != '' and not os.path.exists(profile.file_exists):
                continue
            if profile.file_missing != '' and os.path.exists(profile.file_missing):
                continue
            profiles.append(profile)
            continue
    # default profile
    if len(profiles) == 0:
        profiles = [ profile for profile in pom.profiles if profile.active_by_default ]
    # merge profiles
    for profile in profiles:
        # for profiles, the last wins, so we need to put them in front
        pom.dependencies = profile.dependencies + pom.dependencies
        pom.managements = profile.managements + pom.managements
        for prop in profile.properties.values():
            pom.computed_properties.set(prop.name, prop.value)


def check_version(version: str, target: str) -> bool:
    first = version[:1]
    last = version[-1:]
    if first not in '[(':
        version = f"[{version}"
        first = version[:1]
    if last not in '])':
        version = f"{version},)"
        last = version[-1:]
    # get minimal version and maximal version
    min_version, max_version = version[1:-1].split(',')
    min_version = min_version.strip()
    max_version = max_version.strip()
    min_version = Version(min_version) if min_version != '' else None
    max_version = Version(max_version) if max_version != '' else None
    targetV = Version(target)
    if (
        min_version is None or
        (first == '[' and targetV >= min_version) or
        (first == '(' and targetV > min_version)
    ) and (
        max_version is None or
        (last == ']' and targetV <= max_version) or
        (last == ')' and targetV < max_version)
    ):
        return True
    return False


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

    paths = paths.add(curr, 1)

    # load dependencies from parent, without using resolve_pom as all properties are already loaded
    if curr.parent is not None:
        curr.parent.pom.computed_type = 'parent'
        load_managements(pom, curr.parent.pom, paths = paths)

    # loop dependencies in pom order, as it can be manually changed
    for dep in curr.managements:
        dep = dep.copy()
        trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace("mgt | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(paths))

        # resolve artifact
        resolve_artifact(dep, pom.computed_properties, curr.builtins)
        if trace and TRACER: TRACER.trace("mgt |   resolv", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # fail on invalid scope
        if dep.scope not in KNOWN_SCOPES:
            raise Exception(f"Invalid scope '{dep.scope}' found in dependencyManagement {dep.fullname()} of pom {curr.gav()}")

        if dep.type == 'pom' and dep.scope == 'import':
            # load dependencies from this import with new empty properties
            dep_pom = load_pom_from_dependency(dep, curr.file)
            assert dep_pom
            dep_pom.computed_type = 'parent'
            resolve_pom(dep_pom, paths = paths, computeMgts = pom.computed_managements, load_mgts = True)
        else:
            # merge with existing dependencyManagement
            dep = resolve_management(pom, dep, paths)
            if trace and TRACER: TRACER.trace("mgt |   merged", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)


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


def load_dependencies(pom: PomProject, paths: PomPaths | None = None):
    """
    Load all dependencies from pom.
    It is assumed that all properties have already been loaded.

    1. Properties used for loading are the one from current pom only
    2. DependencyManagement used for loading are the one from root pom only
    3. DependencyManagement may overrides dependency version, see apply_managements
    4. Dependencies from parent are also loaded
    """
    if paths is None: paths = PomPaths()

    deps: PomDeps = []
    paths = paths.add(pom, 0 if pom.computed_type == 'parent' else 1) # pom11 => parent poms have priority over transitive dependencies, so they need to be loaded as same length as child
    dep_inits = new_initial_managements(pom.initial_managements, pom.computed_managements)
    transitive_only = paths.length > 1

    # load dependencies from parent, without using resolve_pom as all properties are already loaded
    # pom12 => even though parent is added before direct dependencies, they are in reality loaded after (as they are loaded from recursion), with the same paths length as the pom
    if pom.parent is not None:
        dep_pom = PomDependency()
        dep_pom.groupId = pom.parent.groupId
        dep_pom.artifactId = pom.parent.artifactId
        dep_pom.version = pom.parent.version
        dep_pom.scope = pom.computed_scope
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
        deps.append(dep_pom)

    # load dependencies in pom order, as it can be manually changed
    for dep in pom.dependencies:
        dep = dep.copy()
        trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace("dep | adding", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'paths', dump_paths(paths))
        
        # resolve artifact
        resolve_artifact(dep, pom.computed_properties, pom.builtins)
        if trace and TRACER: TRACER.trace("dep |   resolved", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # skip exclusions
        if dep.key_excl() in pom.computed_exclusions:
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
        transitive_scope = SCOPES[pom.computed_scope][dep.scope]
        is_transitive = transitive_scope is None
        if transitive_only and is_transitive:
            if trace and TRACER: TRACER.trace("dep |   skip (not transitive)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
            continue

        # optional check
        # it is assumed it must stay around transitivity check :-)
        if transitive_only and dep.optional == 'true':
            if trace and TRACER: TRACER.trace("dep |   skip (is optional)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
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
        if trace and TRACER: TRACER.trace("dep |   resolved", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # resolve version if it is a range
        dep.version = resolve_range_version(dep)
        if dep.optional == '': dep.optional = 'false'
        if dep.optional not in ['true', 'false']:
            raise Exception(f"Invalid optional {dep.optional} found in dependency {dep.fullname()} of pom {pom.gav()}")
        if trace and TRACER: TRACER.trace("dep |   fixed", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)

        # skip already loaded dependencies
        skip = False
        if dep.key_excl() in pom.computed_dependencies:
            loaded = pom.computed_dependencies[dep.key_excl()]
            # can skip if same scope
            if PRIORITY_SCOPES.index(dep.scope) == PRIORITY_SCOPES.index(loaded.scope):
                if paths.length >= loaded.paths.length:
                    if trace and TRACER: TRACER.trace("dep |   no recurse (already loaded)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
                    skip = True
            # can skip if new scope is less important
            elif PRIORITY_SCOPES.index(dep.scope) >= PRIORITY_SCOPES.index(loaded.scope):
                    if trace and TRACER: TRACER.trace("dep |   no recurse (already loaded)", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional)
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
                if paths.length < loaded.paths.length:
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
                if trace and TRACER and fixed: TRACER.trace("dep |   loaded updated", loaded.key_gat(), 'version', loaded.version, 'scope', loaded.scope, 'optional', loaded.optional, 'paths', dump_paths(loaded.paths))
            else:
                pom.computed_dependencies[dep.key_excl()] = dep.copy()

        # add to computed dependencies
        if trace and TRACER: TRACER.trace("dep |   added", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(paths))
        pom.added_dependencies.append(dep)

        # skip?
        if skip: continue

        # skip on non-supported types
        if dep.type in SKIP_TYPES2: continue

        # add to dependencies
        deps.append(dep)

    solvers = []
    for dep in deps:
        # prepare dependency for recursion
        trace = TRACER and TRACER.trace_dep(dep.key_trace()) and TRACER.trace("dep | recurse", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
        dep_pom = load_pom_from_dependency(dep, pom.file, allow_missing = True)
        if dep_pom is None:
            if TRACER and TRACER.trace_poms(): TRACER.trace("dep |   missing", dep.fullname2(), 'version', dep.version, 'scope', dep.scope, 'type', dep.type, 'paths', dump_paths(paths))
            dep.not_found = True
            continue

        # build new mgts, excls and scopes to initialize recursion
        dep_pom.added_dependencies = pom.added_dependencies
        dep_pom.computed_dependencies = pom.computed_dependencies
        dep_pom.computed_type = dep.type
        dep_excls = pom.computed_exclusions | { excl.key():excl for excl in dep.exclusions }
        dep_scope = dep.scope

        # recursion
        solver = new_solver(pom, dep, paths, dep_pom, dep_inits, dep_excls, dep_scope)
        solvers.append(solver)

    # return
    return solvers


def new_solver(pom: PomProject, dep: PomDependency, paths: PomPaths, dep_pom: PomProject, dep_inits: PomMgts, dep_excls: dict[str, PomExclusion], dep_scope: str):
    def fn():
        solvers = resolve_pom(dep_pom, paths = paths, initialMgts = dep_inits, excls = dep_excls, scope = dep_scope, load_mgts = True, load_deps = True)
        return solvers
    return fn


def new_initial_managements(initials: PomMgts, computed: PomMgts) -> PomMgts:
    """
    Create a new initial dependencyManagement from an initial and computed one.
    It is not needed to copy computed mgt as it is not modified later because it becomes an initial dependencyMangement.
    """
    new = computed.copy()
    for ini in initials.values():
        if ini.key_gat() in computed:
            mgt = computed[ini.key_gat()].copy()
            trace = TRACER and TRACER.trace_dep(mgt.key_trace())
            if trace and TRACER:
                TRACER.trace("ini | merging", ini.key_gat(), 'version', ini.version, 'scope', ini.scope, 'optional', ini.optional)
                TRACER.trace("ini |   applying forced from", ini.key_gat(), 'version', ini.version, 'scope', ini.scope, 'optional', ini.optional, 'paths', dump_paths(ini.paths))
            apply_forced_management(ini, mgt)
            if trace and TRACER:
                TRACER.trace("ini |   merged", mgt.key_gat(), 'version', mgt.version, 'scope', mgt.scope, 'optional', mgt.optional, 'paths', dump_paths(mgt.paths))
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
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace("dep |     applying default from", mgt.key_gat(), 'version', mgt.version, 'scope', mgt.scope, 'optional', mgt.optional, 'paths', dump_paths(mgt.paths))
        apply_default_management(mgt, dep)
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace("dep |     applied default", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(dep.paths))


def apply_initial_to_dependency(pom: PomProject, dep: PomDependency, paths: PomPaths):
    """
    Update dependency with initial values from dependencyManagement.
    """
    # apply initial_managements which contains imposed values
    if dep.key_gat() in pom.initial_managements:
        mgt = pom.initial_managements[dep.key_gat()]
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace("dep |     applying initial from", mgt.key_gat(), 'version', mgt.version, 'scope', mgt.scope, 'optional', mgt.optional, 'paths', dump_paths(mgt.paths))
        apply_forced_management(mgt, dep)
        if TRACER and TRACER.trace_dep(mgt.key_trace()): TRACER.trace("dep |     applied initial", dep.key_gat(), 'version', dep.version, 'scope', dep.scope, 'optional', dep.optional, 'paths', dump_paths(dep.paths))


def merge_management(old: PomDependency, new: PomDependency) -> PomDependency:
    """
    Return the dependencyManagement with the shorter path.
    """
    if new.paths.length < old.paths.length:
        return new
    return old


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
        dep.version = mgt.version
        dep.pathsVersion = mgt.pathsVersion
    if mgt.scope != '':
        dep.scope = mgt.scope
        dep.pathsScope = mgt.pathsScope
    if mgt.optional != '':
        dep.optional = mgt.optional
        dep.pathsOptional = mgt.pathsOptional
    if len(mgt.exclusions) > 0:
        dep.exclusions = mgt.exclusions
        dep.pathsExclusions = mgt.pathsExclusions


def dump_paths(paths: PomPaths):
    """
    Dump paths to a string.
    """
    if len(paths.paths) == 1:
        return '.'
    return f"{paths.length} / {' '.join([p.fullname() for p in paths.paths[1:]])}"


if __name__ == "__main__":
    pom1 = load_pom_from_file('tests/pom1.xml')
    assert pom1
    resolve_pom(pom1)
    for dep1 in pom1.computed_managements.values():
        print(dep1.fullname())
    # passed
    print("PASSED")
