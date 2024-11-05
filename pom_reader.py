from pom_struct import PomProject, PomParent, PomDependency, PomExclusion, PomProperties, PomProfile, PomDeps
from lxml import etree

POM_PARSER = etree.XMLParser(
    recover = True,
    remove_comments = True,
    remove_pis = True,
    ns_clean = True,
)


def read_pom(file: str) -> PomProject:
    """
    Read a pom.xml file and return a PomProject object.

    The returned object contains all the pom information, without any external state information.
    It can then be cloned to provide additional information, like paths[].
    """
    pom = PomProject()
    pom.file = file

    # read file
    with open(file, 'rb') as f:
        xml = f.read()
    doc = etree.fromstring(xml, parser=POM_PARSER)
    ns = doc.nsmap.get(None, '')
    ns = '{%s}' % ns if ns else ''

    # read project
    pom.groupId = find_text(doc, 'groupId')
    pom.artifactId = find_text(doc, 'artifactId')
    pom.version = find_text(doc, 'version')
    pom.name = find_text(doc, 'name')
    pom.packaging = find_text(doc, 'packaging', 'jar')

    # read parent
    pom.parent = None
    parent = find(doc, 'parent')
    if parent is not None:
        unexpected_tags(pom, parent, '*', ['groupId', 'artifactId', 'version', 'relativePath'])
        pom.parent = PomParent()
        pom.parent.groupId = find_text(parent, 'groupId')
        pom.parent.artifactId = find_text(parent, 'artifactId')
        pom.parent.version = find_text(parent, 'version')
        pom.parent.relativePath = find_text(parent, 'relativePath')

        # fix missing project properties
        if pom.groupId == '': pom.groupId = pom.parent.groupId
        if pom.version == '': pom.version = pom.parent.version

    # read properties
    pom.properties = PomProperties()
    properties = find(doc, 'properties')
    if properties is not None:
        for prop in properties.iterchildren():
            if prop.tag == ns + 'property':
                unexpected_tags(pom, prop, '*', ['name','value'])
                name = prop.get('name')
                value = prop.get('value', '')
            else:
                name = prop.tag[len(ns):]
                value = prop.text or ''
            pom.properties.set(name, value)
    
    # add built-in properties
    pom.builtins = PomProperties()

    pom.builtins.set('artifactId', pom.artifactId)
    pom.builtins.set('groupId', pom.groupId)
    pom.builtins.set('version', pom.version)
    pom.builtins.set('project.artifactId', pom.artifactId)
    pom.builtins.set('project.groupId', pom.groupId)
    pom.builtins.set('project.version', pom.version)
    pom.builtins.set('pom.artifactId', pom.artifactId)
    pom.builtins.set('pom.groupId', pom.groupId)
    pom.builtins.set('pom.version', pom.version)

    if pom.parent is not None:
        pom.builtins.set('parent.artifactId', pom.parent.artifactId)
        pom.builtins.set('parent.groupId', pom.parent.groupId)
        pom.builtins.set('parent.version', pom.parent.version)
        pom.builtins.set('project.parent.artifactId', pom.parent.artifactId)
        pom.builtins.set('project.parent.groupId', pom.parent.groupId)
        pom.builtins.set('project.parent.version', pom.parent.version)
    
    # read dependencyManagement
    pom.managements = []
    managements = find_all(doc, 'dependencyManagement/dependencies/dependency')
    for dep in managements:
        pom.managements.append(get_dependency(pom, dep))

    # read dependencies
    pom.dependencies = []
    dependencies = find_all(doc, 'dependencies/dependency')
    for dep in dependencies:
        pom.dependencies.append(get_dependency(pom, dep))
    
    # read modules
    pom.modules = []
    modules = find_all(doc, 'modules/module')
    for module in modules:
        pom.modules.append(module.text)
    
    # read profiles
    pom.profiles = []
    profiles = find_all(doc, 'profiles/profile')
    for profile in profiles:
        unexpected_tags(pom, profile, '*', ['id', 'activation', 'dependencies', 'dependencyManagement', 'properties', 'build', 'repositories', 'pluginRepositories', 'modules', 'file', 'distributionManagement', 'reporting'])
        pro = PomProfile()
        pro.id = find_text(profile, 'id', '')
        activation = find(profile, 'activation')
        if activation is not None:
            unexpected_tags(pom, activation, '*', ['activeByDefault', 'jdk', 'property', 'os', 'file'])
            pro.active_by_default = find_text(activation, 'activeByDefault', 'false') == 'true'
            if find(activation, 'jdk') is not None:
                pro.jdk = find_text(activation, 'jdk')
            if find(activation, 'property') is not None:
                unexpected_tags(pom, activation, 'property/*', ['name', 'value'])
                pro.property_name = find_text(activation, 'property/name')
                pro.property_value = find_text(activation, 'property/value')
            if find(activation, 'os') is not None:
                unexpected_tags(pom, activation, 'os/*', ['name', 'family', 'arch', 'version'])
                pro.os_name = find_text(activation, 'os/name')
                pro.os_family = find_text(activation, 'os/family')
                pro.os_arch = find_text(activation, 'os/arch')
                pro.os_version = find_text(activation, 'os/version')
            if find(activation, 'file') is not None:
                unexpected_tags(pom, activation, 'file/*', ['exists', 'missing'])
                pro.file_exists = find_text(activation, 'file/exists')
                pro.file_missing = find_text(activation, 'file/missing')
        
        pro.dependencies = PomDeps()
        dependencies = find_all(profile, 'dependencies/dependency')
        for dep in dependencies:
            pro.dependencies.append(get_dependency(pom, dep))
        
        pro.managements = PomDeps()
        managements = find_all(profile, 'dependencyManagement/dependencies/dependency')
        for dep in managements:
            pro.managements.append(get_dependency(pom, dep))
        
        pro.properties = PomProperties()
        properties = find(profile, 'properties')
        if properties is not None:
            for prop in properties.iterchildren():
                if prop.tag == ns + 'property':
                    unexpected_tags(pom, prop, '*', ['name','value'])
                    name = prop.get('name')
                    value = prop.get('value', '')
                else:
                    name = prop.tag[len(ns):]
                    value = prop.text or ''
                pro.properties.set(name, value)
        
        pro.modules = []
        modules = find_all(profile, 'modules/module')
        for module in modules:
            pro.modules.append(module.text)
        
        pom.profiles.append(pro)


    # return the pom object
    return pom

def get_dependency(pom: PomProject, dep) -> PomDependency:
    unexpected_tags(pom, dep, '*', ['groupId', 'artifactId', 'version', 'type', 'scope', 'exclusions', 'classifier', 'optional', 'systemPath'])
    dependency = PomDependency()
    dependency.groupId = find_text(dep, 'groupId')
    dependency.artifactId = find_text(dep, 'artifactId')
    dependency.version = find_text(dep, 'version')
    dependency.scope = find_text(dep, 'scope')
    dependency.type = find_text(dep, 'type', 'jar')
    dependency.classifier = find_text(dep, 'classifier')
    dependency.optional = find_text(dep, 'optional')
    dependency.relativePath = ''
    dependency.not_found = False
    dependency.exclusions = []
    # read exclusions
    exclusions = find_all(dep, 'exclusions/exclusion')
    for excl in exclusions:
        exclusion = PomExclusion()
        exclusion.groupId = find_text(excl, 'groupId')
        exclusion.artifactId = find_text(excl, 'artifactId')
        dependency.exclusions.append(exclusion)
    return dependency

def find(elem, tag: str):
    ns = elem.nsmap.get(None, '')
    ns = '{%s}' % ns if ns else ''
    tag = tag.replace("/", "/" + ns)
    return elem.find(ns + tag)


def find_all(elem, tag: str):
    ns = elem.nsmap.get(None, '')
    ns = '{%s}' % ns if ns else ''
    tag = tag.replace("/", "/" + ns)
    return elem.findall(ns + tag)


def find_text(elem, tag: str, default = '') -> str:
    ns = elem.nsmap.get(None, '')
    ns = '{%s}' % ns if ns else ''
    tag = tag.replace("/", "/" + ns)
    elem = elem.find(ns + tag)
    if elem is None or elem.text is None: return default
    return elem.text


def find_tags(elem, tag: str):
    ns = elem.nsmap.get(None, '')
    ns = '{%s}' % ns if ns else ''
    tag = tag.replace("/", "/" + ns)
    return [ e.tag.replace(ns,"") for e in elem.findall(ns + tag) ]


def unexpected_tags(pom: PomProject, elem, tag: str, allowed: list):
    # halt on non-expected tags, not groupId or artifactId
    tags = find_tags(elem, tag)
    tags = [ t for t in tags if t not in allowed ]
    if len(tags) > 0:
        raise Exception(f"Unexpected tags: {tags} in pom {pom.gav()}\n{etree.tostring(elem)}")

if __name__ == "__main__":
    # verify reading pom.xml
    pom1 = read_pom('tests/pom1.xml')
    assert pom1.gav() == "mygroup:myartifact:${revision}"
    # read old pom format
    pom2 = read_pom('commons-configuration-1.6.pom')
    assert pom2.gav() == "commons-configuration:commons-configuration:1.6"
    # passed
    print("PASSED")
