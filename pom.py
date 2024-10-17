import re
from lxml import etree

POM_NAMESPACE = "http://maven.apache.org/POM/4.0.0"
POM = "{%s}" % (POM_NAMESPACE,)
POM_NAMESPACE_LEN = len(POM)

POM_PARSER = etree.XMLParser(
    recover=True,
    remove_comments=True,
    remove_pis=True,
    )


class Pom(object):
    def __init__(self, file):
        self.file = file
        self.xml = None
        self.infos = None
        self.name = None
        self.parent = None
        self.properties = {}
        self.dependencies = []
        self.dependencyManagement = []

    def __str__(self):
        return self.file

    def __repr__(self):
        return self.file

    def parse(self) -> 'Pom':
        self.xml = etree.parse(self.file, parser=POM_PARSER)
        # 
        self.infos = {
            'groupId': findtext(self.xml, 'groupId'),
            'artifactId': findtext(self.xml, 'artifactId'),
            'version': findtext(self.xml, 'version'),
            'name': findtext(self.xml, 'name'),
            'packaging': findtext(self.xml, 'packaging', 'jar'),
        }
        self.name = f"{self.infos['groupId']}:{self.infos['artifactId']}:{self.infos['version']}"
        # parent
        parent = None
        project_parent = find(self.xml, 'parent')
        if project_parent is not None:
            parent = {
                'groupId': findtext(project_parent, 'groupId'),
                'artifactId': findtext(project_parent, 'artifactId'),
                'version': findtext(project_parent, 'version'),
                'relativePath': findtext(project_parent, 'relativePath'),
            }
        self.parent = parent
        # properties
        properties = {}
        project_properties = find(self.xml, "properties")
        if project_properties is not None:
            for prop in project_properties.iterchildren():
                if prop.tag == POM + 'property':
                    name = prop.get('name')
                    value = prop.get('value')
                else:
                    name = prop.tag[POM_NAMESPACE_LEN:]
                    value = prop.text
                properties[name] = value
        self.properties = properties
        # dependencies
        dependencies = []
        for dependency in findall(self.xml, 'dependencies/dependency'):
            dep = {
                'groupId': findtext(dependency, 'groupId'),
                'artifactId': findtext(dependency, 'artifactId'),
                'version': findtext(dependency, 'version'),
                'type': findtext(dependency, 'type', 'jar'),
                'scope': findtext(dependency, 'scope'),
            }
            dep['source'] = self.name
            dep['sourceVersion'] = self.name if self.infos['version'] else None
            dependencies.append(dep)
        self.dependencies = dependencies
        # dependencyManagement
        dependencyManagement = []
        for dependency in findall(self.xml, 'dependencyManagement/dependencies/dependency'):
            dep = {
                'groupId': findtext(dependency, 'groupId'),
                'artifactId': findtext(dependency, 'artifactId'),
                'version': findtext(dependency, 'version'),
                'type': findtext(dependency, 'type', 'jar'),
                'scope': findtext(dependency, 'scope'),
            }
            dep['source'] = self.name
            dep['sourceVersion'] = self.name if self.infos['version'] else None
            dependencyManagement.append(dep)
        self.dependencyManagement = dependencyManagement
        #
        return self

def find(elem, tag: str):
    elem = elem.xml if isinstance(elem, Pom) else elem
    tag = tag.replace("/", "/" + POM)
    return elem.find(POM + tag)


def findall(elem, tag: str) -> list:
    elem = elem.xml if isinstance(elem, Pom) else elem
    tag = tag.replace("/", "/" + POM)
    return elem.findall(POM + tag)


def findtext(elem, tag: str, ifNone: str = None) -> str:
    elem = elem.xml if isinstance(elem, Pom) else elem
    tag = tag.replace("/", "/" + POM)
    value = elem.findtext(POM + tag)
    return value if value is not None else ifNone

def properties(poms: list) -> dict:
    """
    Return a dictionary of properties from a list of POMs.
    Properties are resolved from parent to child.
    """
    props = {}
    # add properties from each pom from top parent to current pom
    for p in reversed(poms):
        props.update(p.properties)
    # add parent built-in properties
    if len(poms) > 1:
        parent = poms[1]
        props['parent.groupId'] = parent.id['groupId']
        props['parent.artifactId'] = parent.id['artifactId']
        props['parent.version'] = parent.id['version']
        props['project.parent.groupId'] = parent.id['groupId']
        props['project.parent.artifactId'] = parent.id['artifactId']
        props['project.parent.version'] = parent.id['version']
    # add project built-in properties
    project = poms[0]
    props['artifactId'] = project.id['artifactId']
    props['groupId'] = project.id['groupId']
    props['version'] = project.id['version']
    props['project.artifactId'] = project.id['artifactId']
    props['project.groupId'] = project.id['groupId']
    props['project.version'] = project.id['version']
    props['pom.artifactId'] = project.id['artifactId']
    props['pom.groupId'] = project.id['groupId']
    props['pom.version'] = project.id['version']
    # resolve properties
    for key, value in props.items():
        props[key] = resolve(value, props)
    #
    return props

def resolve(value: str, props: dict) -> str:
    """
    Resolve properties in a string.
    Properties are defined as ${key} and are replaced by their value.
    """
    def resolve_match(match):
        key = match.group(1)
        return props.get(key, match.group(0))
    return re.sub(r'\$\{([^}]+)\}', resolve_match, value)

if __name__ == '__main__':
    artifact = Pom('pom.xml').parse()
    print(findtext(artifact, 'artifactId'))
