import logging, pathlib, os
from artifact_pom import ArtifactPom
from easydict import EasyDict as edict

color = True

ALL_SCOPES = { 'compile':'compile', 'runtime':'runtime','test':'test' }
ALL_SCOPES_KEYS = list(ALL_SCOPES.keys())

COMPILE_SCOPES = { 'compile':'compile', 'runtime':'runtime' }
RUNTIME_SCOPES = { 'compile':'runtime', 'runtime':'runtime' }
TEST_SCOPES = { 'test':'test', 'compile':'test', 'runtime':'test' }

NEW_SCOPES = { 'compile':COMPILE_SCOPES, 'runtime':RUNTIME_SCOPES, 'test':TEST_SCOPES }
SKIP_SCOPES = ['runtime']

locations = {}
loaded_poms = {}
logging.basicConfig(level=logging.WARNING)

def register_location(file):
    pom = load_pom_file(file)
    props = load_properties(pom)
    resolve_properties(pom, props)
    resolve_version(pom.infos, props)
    locations[pom.infos.fullname] = file

def load_pom_file(file, paths = [], allow_skip = False):
    if os.path.exists(file):
        return ArtifactPom.parse(file)
    if allow_skip: return None
    raise Exception(f"missing pom file: {file} from {' > '.join(paths)}")
    # if file in loaded_poms:
    #     return loaded_poms[file]
    # logging.info(f"Parsing pom {file}")
    # loaded_pom = ArtifactPom.parse(file)
    # loaded_poms[file] = loaded_pom
    # return loaded_pom

def load_pom_dep(dep, base, paths, allow_skip = False):
    file = find_pom_file(dep, base)
    return load_pom_file(file, paths, allow_skip = allow_skip)

def find_pom_file(dep, base):
    # try to load relativePath, maven silently ignore missing files
    if dep.relativePath != None and dep.relativePath != "":
        file = os.path.join(os.path.dirname(base), dep.relativePath)
        if os.path.exists(file):
            return file
    if dep.fullname in locations:
        file = locations[dep.fullname]
    else:
        file = os.path.join(pathlib.Path.home(), '.m2/repository', dep.groupId.replace(".", "/"), dep.artifactId, dep.version, f"{dep.artifactId}-{dep.version}.pom")
    return file

def resolve_version(obj, props: dict = None):
    obj.groupId = ArtifactPom.resolve(obj.groupId, props)
    obj.artifactId = ArtifactPom.resolve(obj.artifactId, props)
    obj.version = ArtifactPom.resolve(obj.version, props)
    obj.key = f"{obj.groupId}:{obj.artifactId}"
    obj.fullname = f"{obj.groupId}:{obj.artifactId}:{obj.version}"

def resolve_properties(pom, props):
    for value in props.values():
        value.value = ArtifactPom.resolve(value.value, props)

def load_properties(pom, props = {}, paths = []) -> dict:
    # this loads properties from the pom and its parent
    # this is following RULE 1: project properties > parent properties
    paths = paths + [pom.infos.fullname]
    # project properties
    for key, value in pom.properties.items():
        if key not in props:
            props[key] = value
            props[key].paths = paths
    # resolve properties partially
    resolve_properties(pom, props)
    # parent properties
    if pom.parent is not None:
        # note: parent pom version cannot contain variables
        resolve_version(pom.parent, props)
        # load parent properties
        parent_pom = load_pom_dep(pom.parent, pom.file, paths)
        load_properties(parent_pom, props, paths)
    # resolve project version in case it was using a parent property
    # resolve_properties(pom, props)
    resolve_version(pom.infos, props)
    #
    return props

def load_dependencyManagement(pom, ctx, props = {}, paths = []):
    # incoming properties are used to resolve version in this pom
    # however, they are not used in dependencyManagement is may contain
    # this is following rULE 1 for parent and RULE 2 for dependencies
    project_props = load_properties(pom, props.copy(), paths)
    # project_props = load_properties(pom, {}, path)
    forward_props = {}
    # resolve project version
    resolve_version(pom.infos, project_props)
    logging.debug(f"Loading dependencyManagement for {pom.infos.fullname}")
    paths = paths + [pom.infos.fullname]
    # direct dependencies
    for dep in pom.dependencyManagement:
        if dep.type == 'pom' and dep.scope == 'import':
            continue
        # dep = clone(dep)
        resolve_version(dep, project_props)
        if dep.key in ctx.map: continue
        dep.paths = paths
        ctx.map[dep.key] = dep
        ctx.mgts.append(dep)
        logging.debug(f"  added {dep.fullname}")
    # imported dependencies
    for dep in pom.dependencyManagement:
        if dep.type != 'pom' or dep.scope != 'import':
            continue
        # dep = edict(dep.copy())
        resolve_version(dep, project_props)
        if dep.key in ctx.map: continue
        dep.paths = paths
        ctx.map[dep.key] = dep
        ctx.mgts.append(dep)
        # enter the imported pom
        dep_pom = load_pom_dep(dep, pom.file, paths)
        logging.debug(f"  importing {dep.fullname}")
        load_dependencyManagement(dep_pom, ctx, props = forward_props, paths = paths)
    # parent dependency
    if pom.parent is not None:
        # note: parent pom version cannot contain variables
        parent_pom = load_pom_dep(pom.parent, pom.file, paths)
        logging.debug(f"  loading parent {pom.parent.fullname}")
        load_dependencyManagement(parent_pom, ctx, props = project_props, paths = paths)

def load_dependencies(pom, ctx, props = {}, paths = [], excls = [], allowed_scopes = {}):
    # incoming properties are used to resolve version in this pom
    # however, they are not used in dependencyManagement is may contain
    # this is following RULE 2
    project_props = load_properties(pom, props.copy())
    forward_props = {}
    # resolve dependency version
    resolve_version(pom.infos, project_props)
    logging.debug(f"Loading dependencies for {pom.infos.fullname}")
    paths = paths + [pom.infos.fullname]
    # direct dependencies
    for dep in pom.dependencies:
        # ignore dependency if in exclusion list
        if dep.key in excls:
            continue
        # ignoer dependency if scope is not allowed
        if dep.scope not in ALL_SCOPES_KEYS:
            raise Exception(f"Invalid scope {dep.scope} for {dep.groupId}:{dep.artifactId} at {paths}")
        if dep.scope not in allowed_scopes.keys():
            continue
        dep.scope = allowed_scopes[dep.scope]
        # process dependency
        if dep.key in ctx.map:
            # note: version should be already resolved
            mgt = ctx.map[dep.key]
            dep.version = mgt.version
            resolve_version(dep, project_props)
            pathsVersion = mgt.paths
            # add exclusions
            dep.exclusions.extend(mgt.exclusions)
        else:
            # resolve version
            pathsVersion = paths
            resolve_version(dep, project_props)
        dep.paths = paths
        dep.pathsVersion = pathsVersion
        ctx.deps.append(dep)

def load(pom, paths = [], excls = [], allowed_scopes = ALL_SCOPES, mgts = [], map = {}):
    # compute all properties sorted by key
    props = load_properties(pom, paths = paths)

    logging.info(f"Loading pom {pom.infos.fullname} for {paths} with scopes={allowed_scopes}")

    # create context
    ctx = edict(mgts = mgts.copy(), map = map.copy(), deps = [])

    # compute dependencies from root and all parents
    # project priority > import priority > parent priority
    logging.info("Computing dependencyManagement")
    load_dependencyManagement(pom, ctx, paths = paths)

    # compute dependencies from root and all parents
    logging.info("Computing dependencies")
    load_dependencies(pom, ctx, paths = paths, excls = excls, allowed_scopes = allowed_scopes)

    # loop on all dependencies
    for dep in ctx.deps[:]:
        dep_paths = paths + [pom.infos.fullname]
        dep_pom = load_pom_dep(dep, pom.file, dep_paths, allow_skip = dep.scope in SKIP_SCOPES)
        if dep_pom is None: continue
        dep_excls = excls + [excl.key for excl in dep.exclusions]
        dep_scopes = NEW_SCOPES[dep.scope]
        dep_ctx = load(dep_pom, paths = dep_paths, excls = dep_excls, allowed_scopes = dep_scopes, mgts = ctx.mgts, map = ctx.map)
        ctx.deps.extend(dep_ctx.deps)

    # return context
    ctx.props = props
    return ctx

def dump(pom, ctx, show_props = False, show_mgts = False, show_deps = False):
    print("#" * 80)
    print(f"# {pom.infos.fullname}")
    print("#" * 80)
    print()

    # print all properties sorted by key
    if show_props:
        a = '\033[1;33m' if color else ''
        c = '\033[1;32m' if color else ''
        e = '\033[m' if color else ''
        print("properties:")
        print()
        for key in sorted(ctx.props.keys()):
            value = ctx.props[key].value.replace("\n", "\\n")
            path = " > ".join(ctx.props[key].paths[1:])
            print(f"  {a}{key}{e}: {c}{value}{e}          # {path}")
        print()

    # print all dependencyManagement, sorted by groupId, artifactId, version
    if show_mgts:
        a = '\033[1;33m' if color else ''
        c = '\033[1;32m' if color else ''
        e = '\033[m' if color else ''
        print("dependenciesManagement:")
        print()
        for dep in sorted(ctx.mgts, key=lambda dep: (dep.groupId, dep.artifactId, dep.version)):
            texts = [ f"{a}{dep.groupId}:{dep.artifactId}{e}", f"  {c}{dep.version}{e}" ]
            paths = [ " > ".join(dep.paths[1:]), " > ".join(dep.paths[1:])]
            length = max([len(text) for text in texts])
            length = max(length, 80)
            for text, path in zip(texts, paths):
                print(f"  {text.ljust(length)}    # {path}")
        print()

    # print all dependencies
    if show_deps:
        a = ''
        c = ''
        e = ''
        print("dependencies:")
        print()
        previous = None
        for dep in sorted(ctx.deps, key=lambda dep: (dep.groupId, dep.artifactId, len(dep.paths), dep.version)):
            if color:
                a = '\033[1;33m'
                c = '\033[0;32m' if previous == f"{dep.groupId}:{dep.artifactId}" else '\033[1;32m'
                e = '\033[m'
            texts = [ f"{a}{dep.groupId}:{dep.artifactId}{e}", f"  {c}{dep.version}{e} ({dep.scope})" ]
            paths = [ " > ".join(dep.paths[1:]), "- " + " > ".join(dep.pathsVersion[1:])]
            if previous == f"{dep.groupId}:{dep.artifactId}":
                texts = texts[1:]
                paths = paths[1:]
            length = max([len(text) for text in texts])
            length = max(length, 80)
            for text, path in zip(texts, paths):
                print(f"  {text.ljust(length)}    # {path}")
            previous = f"{dep.groupId}:{dep.artifactId}"
        print()

# todo : cache des pom chargés! par pour le moment car il y a pas de clone de pom
# todo : exclusions sur dependencies et dependencyManagement

# starting pom
root_pom_file = 'myartifact/pom.xml'

# register root and modules locations
register_location(root_pom_file)
root_pom = load_pom_file(root_pom_file)

for module in root_pom.modules:
    module_pom_file = os.path.join(os.path.dirname(root_pom_file), module, 'pom.xml')
    register_location(module_pom_file)

# load root and modules poms
root_pom = load_pom_file(root_pom_file)
ctx = load(root_pom)

dump(root_pom, ctx, show_props = True, show_mgts = True, show_deps = True)
