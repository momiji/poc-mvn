import logging, pathlib, os, sys
from artifact_pom import ArtifactPom
from easydict import EasyDict as edict

locations = {}
loaded_poms = {}
logging.basicConfig(level=logging.WARNING)

def register_location(file):
    pom = load_pom_file(file)
    props = load_properties(pom)
    resolve_properties(pom, props)
    resolve_version(pom.infos, props)
    locations[pom.infos.fullname] = file

def load_pom_file(file, path = []):
    if os.path.exists(file):
        return ArtifactPom.parse(file)
    print(f"missing pom file: {file}    # {" > ".join(path)}")
    return None
    # if file in loaded_poms:
    #     return loaded_poms[file]
    # logging.info(f"Parsing pom {file}")
    # loaded_pom = ArtifactPom.parse(file)
    # loaded_poms[file] = loaded_pom
    # return loaded_pom

def load_pom_dep(dep, base, path):
    file = find_pom_file(dep, base)
    return load_pom_file(file, path)

def find_pom_file(dep, base):
    if dep.relativePath != None and dep.relativePath != "":
        file = os.path.join(os.path.dirname(base), dep.relativePath)
    elif dep.fullname in locations:
        file = locations[dep.fullname]
    else:
        file = os.path.join(pathlib.Path.home(), '.m2/repository', dep.groupId.replace(".", "/"), dep.artifactId, dep.version, f"{dep.artifactId}-{dep.version}.pom")
    return file

def resolve_version(obj, props: dict = None):
    obj.groupId = ArtifactPom.resolve(obj.groupId, props)
    obj.artifactId = ArtifactPom.resolve(obj.artifactId, props)
    obj.version = ArtifactPom.resolve(obj.version, props)
    obj.fullname = f"{obj.groupId}:{obj.artifactId}:{obj.version}"

def resolve_properties(pom, props):
    pom.builtin_properties(props)
    for key, value in props.items():
        props[key] = ArtifactPom.resolve(value, props)

def load_properties(pom, props = {}, path = []):
    path = path + [pom.infos.fullname]
    # project properties
    for key, value in pom.properties.items():
        if key not in props:
            props[key] = value
    # resolve properties partially
    resolve_properties(pom, props)
    # parent properties
    if pom.parent is not None:
        # note: parent pom version cannot contain variables
        resolve_version(pom.parent, props)
        # load parent properties
        parent_pom = load_pom_dep(pom.parent, pom.file, path)
        load_properties(parent_pom, props, path)
    # resolve project version in case it was using a parent property
    resolve_properties(pom, props)
    resolve_version(pom.infos, props)
    #
    return props

def load_dependencyManagement(pom, ctx, path = []):
    if pom is None: return
    # this pom can have it's own properties and parent, so we need to load them
    # however we don't want to override the properties of the parent
    keep_props = ctx.props.copy()
    load_properties(pom, ctx.props)
    # resolve project version
    resolve_version(pom.infos, ctx.props)
    logging.debug(f"Loading dependencyManagement for {pom.infos.fullname}")
    path = path + [pom.infos.fullname]
    # direct dependencies
    for dep in pom.dependencyManagement:
        if dep.type == 'pom' and dep.scope == 'import':
            continue
        if dep.key in ctx.map:
            continue
        # dep = clone(dep)
        resolve_version(dep, ctx.props)
        dep.paths = path
        ctx.map[dep.key] = dep
        ctx.mgts.append(dep)
    # imported dependencies
    for dep in pom.dependencyManagement:
        if dep.type != 'pom' or dep.scope != 'import':
            continue
        if dep.key in ctx.map:
            continue
        # dep = edict(dep.copy())
        resolve_version(dep, ctx.props)
        dep.paths = path
        ctx.map[dep.key] = dep
        ctx.mgts.append(dep)
        dep_pom = load_pom_dep(dep, pom.file, path)
        load_dependencyManagement(dep_pom, ctx, path)
    # parent dependency
    if pom.parent is not None:
        # note: parent pom version cannot contain variables
        parent_pom = load_pom_dep(pom.parent, pom.file, path)
        load_dependencyManagement(parent_pom, ctx, path)
    # restore properties
    ctx.props = keep_props

def load_dependencies(pom, ctx, path = []):
    # this pom can have it's own properties and parent, so we need to load them
    # however we don't want to override the properties of the parent
    keep_props = ctx.props.copy()
    keep_excls = ctx.excls.copy()
    load_properties(pom, ctx.props)
    # resolve dependency version
    resolve_version(pom.infos, ctx.props)
    logging.debug(f"Loading dependencies for {pom.infos.fullname}")
    path = path + [pom.infos.fullname]
    pathVersion = path
    # direct dependencies
    for dep in pom.dependencies:
        if dep.version is None:
            # get version from dependencyManagement
            if dep.key in ctx.map:
                # note: version should be already resolved
                dep.version = ctx.map[dep.key].version
                resolve_version(dep, ctx.props)
                pathVersion = ctx.map[dep.key].paths
            else:
                raise Exception(f"Could not resolve version for {dep.groupId}:{dep.artifactId} at {path}")
        else:
            resolve_version(dep, ctx.props)
        dep.paths = path
        dep.pathsVersion = pathVersion
        ctx.deps.append(dep)
    # restore keeps
    ctx.props = keep_props
    ctx.excls = keep_excls

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

# print all properties sorted by key
props = load_properties(root_pom)
print("properties:")
for key in sorted(props.keys()):
    value = props[key].replace("\n", "\\n")
    print(f"  {key}: {value}")
print()

# context
ctx = edict(mgts = [], map = {}, props = props, deps = [], excls = {})

# compute dependencies from root and all parents
# project priority > import priority > parent priority
logging.info("Computing dependencyManagement")
load_dependencyManagement(root_pom, ctx)

# print all dependencyManagement, sorted by groupId, artifactId, version
print("dependencyManagement:")
for dep in sorted(ctx.mgts, key=lambda dep: (dep.groupId, dep.artifactId, dep.version)):
    texts = [ f"- groupId: {dep.groupId}", f"  artifactId: {dep.artifactId}", f"  version: {dep.version}" ]
    paths = [ " > ".join(dep.paths), " > ".join(dep.paths), " > ".join(dep.paths)]
    length = max([len(text) for text in texts])
    length = max(length, 80)
    for text, path in zip(texts, paths):
        print(f"  {text.ljust(length)}    # {path}")
print()

# compute dependencies from root and all parents
logging.info("Computing dependencies")
load_dependencies(root_pom, ctx)

# print all dependencies
print("dependency:")
for dep in ctx.deps:
    texts = [ f"- groupId: {dep.groupId}", f"  artifactId: {dep.artifactId}", f"  version: {dep.version}" ]
    paths = [ " > ".join(dep.paths), " > ".join(dep.paths), " > ".join(dep.pathsVersion)]
    length = max([len(text) for text in texts])
    length = max(length, 80)
    for text, path in zip(texts, paths):
        print(f"  {text.ljust(length)}    # {path}")
print()
