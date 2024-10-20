from pom_struct import PomProject, PomParent, PomDependency, PomExclusion, PomProperties, PomMgts, PomDeps
from lxml import etree

POM_NAMESPACE = "http://maven.apache.org/POM/4.0.0"
POM = "{%s}" % (POM_NAMESPACE,)
POM_NAMESPACE_LEN = len(POM)

POM_PARSER = etree.XMLParser(
    recover=True,
    remove_comments=True,
    remove_pis=True,
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
        if pom.groupId is None: pom.groupId = pom.parent.groupId
        if pom.version is None: pom.version = pom.parent.version

    # read properties
    pom.properties = PomProperties()
    pom.computed_properties = PomProperties()
    properties = find(doc, 'properties')
    if properties is not None:
        for prop in properties.iterchildren():
            if prop.tag == POM + 'property':
                unexpected_tags(pom, prop, '*', ['name','value'])
                name = prop.get('name')
                value = prop.get('value', '')
            else:
                name = prop.tag[POM_NAMESPACE_LEN:]
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
    pom.computed_managements = PomMgts()
    managements = find_all(doc, 'dependencyManagement/dependencies/dependency')
    for dep in managements:
        unexpected_tags(pom, dep, '*', ['groupId', 'artifactId', 'version', 'type', 'scope', 'exclusions', 'classifier'])
        dependency = PomDependency()
        dependency.groupId = find_text(dep, 'groupId')
        dependency.artifactId = find_text(dep, 'artifactId')
        dependency.version = find_text(dep, 'version')
        dependency.scope = find_text(dep, 'scope')
        dependency.type = find_text(dep, 'type')
        dependency.classifier = find_text(dep, 'classifier')
        dependency.relativePath = None
        dependency.exclusions = []
        pom.managements.append(dependency)
        # read exclusions
        exclusions = find_all(dep, 'exclusions/exclusion')
        for excl in exclusions:
            exclusion = PomExclusion()
            exclusion.groupId = find_text(excl, 'groupId')
            exclusion.artifactId = find_text(excl, 'artifactId')
            dependency.exclusions.append(exclusion)

    # read dependencies
    pom.dependencies = []
    pom.computed_dependencies = PomDeps()
    dependencies = find_all(doc, 'dependencies/dependency')
    for dep in dependencies:
        unexpected_tags(pom, dep, '*', ['groupId', 'artifactId', 'version', 'type', 'scope', 'exclusions', 'classifier'])
        dependency = PomDependency()
        dependency.groupId = find_text(dep, 'groupId')
        dependency.artifactId = find_text(dep, 'artifactId')
        dependency.version = find_text(dep, 'version')
        dependency.scope = find_text(dep, 'scope')
        dependency.type = find_text(dep, 'type')
        dependency.classifier = find_text(dep, 'classifier')
        dependency.relativePath = None
        dependency.exclusions = []
        pom.dependencies.append(dependency)
        # read exclusions
        exclusions = find_all(dep, 'exclusions/exclusion')
        for excl in exclusions:
            exclusion = PomExclusion()
            exclusion.groupId = find_text(excl, 'groupId')
            exclusion.artifactId = find_text(excl, 'artifactId')
            dependency.exclusions.append(exclusion)
    
    # return the pom object
    return pom


def find(elem, tag: str):
    tag = tag.replace("/", "/" + POM)
    return elem.find(POM + tag)


def find_all(elem, tag: str):
    tag = tag.replace("/", "/" + POM)
    return elem.findall(POM + tag)


def find_text(elem, tag: str, default: str = None) -> str:
    tag = tag.replace("/", "/" + POM)
    elem = elem.find(POM + tag)
    return elem.text if elem is not None else default


def find_tags(elem, tag: str):
    tag = tag.replace("/", "/" + POM)
    return [ e.tag.replace(POM,"") for e in elem.findall(POM + tag) ]


def unexpected_tags(pom: PomProject, elem, tag: str, allowed: list):
    # halt on non-expected tags, not groupId or artifactId
    tags = find_tags(elem, tag)
    tags = [ t for t in tags if t not in allowed ]
    if len(tags) > 0:
        raise Exception(f"Unexpected tags: {tags} in pom {pom.fullname()}\n{etree.tostring(elem)}")

if __name__ == "__main__":
    # verify reading pom.xml
    pom1 = read_pom('myartifact/pom.xml')
    assert pom1.fullname() == "mygroup:myartifact:${revision}"
    # passed
    print("PASSED")
