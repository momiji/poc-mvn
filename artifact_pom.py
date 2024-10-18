import re
from easydict import EasyDict as edict
from lxml import etree

POM_NAMESPACE = "http://maven.apache.org/POM/4.0.0"
POM = "{%s}" % (POM_NAMESPACE,)
POM_NAMESPACE_LEN = len(POM)

POM_PARSER = etree.XMLParser(
    recover=True,
    remove_comments=True,
    remove_pis=True,
)


class ArtifactPom(object):
    def __init__(self, file):
        self.file = file
        self.xml = None
        self.infos = None
        self.name = None
        self.parent = None
        self.properties = {}
        self.dependencies = []
        self.dependencyManagement = []
        self.modules = []

    def __str__(self):
        return self.file

    def __repr__(self):
        return self.file
    
    def parse(file: str) -> 'ArtifactPom':
        self = ArtifactPom(file)
        self.xml = etree.parse(self.file, parser=POM_PARSER)
        # infos
        infos = edict()
        infos.groupId = ArtifactPom.findtext(self.xml, 'groupId')
        infos.artifactId = ArtifactPom.findtext(self.xml, 'artifactId')
        infos.version = ArtifactPom.findtext(self.xml, 'version')
        infos.name = ArtifactPom.findtext(self.xml, 'name')
        infos.packaging = ArtifactPom.findtext(self.xml, 'packaging', 'jar')
        # set fullname although version it is not resolved yet
        infos.fullname = f"{infos.groupId}:{infos.artifactId}:{infos.version}"
        self.infos = infos
        # parent
        parent = None
        project_parent = ArtifactPom.find(self.xml, 'parent')
        if project_parent is not None:
            parent = edict()
            parent.groupId = ArtifactPom.findtext(project_parent, 'groupId')
            parent.artifactId = ArtifactPom.findtext(project_parent, 'artifactId')
            parent.version = ArtifactPom.findtext(project_parent, 'version')
            parent.relativePath = ArtifactPom.findtext(project_parent, 'relativePath')
            infos.groupId = parent.groupId if infos.groupId is None else infos.groupId
            infos.version = parent.version if infos.version is None else infos.version
        self.parent = parent
        # properties
        properties = {}
        project_properties = ArtifactPom.find(self.xml, "properties")
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
        # dependencyManagement
        dependencyManagement = []
        for dependency in ArtifactPom.findall(self.xml, 'dependencyManagement/dependencies/dependency'):
            dep = edict()
            dep.groupId = ArtifactPom.findtext(dependency, 'groupId')
            dep.artifactId = ArtifactPom.findtext(dependency, 'artifactId')
            dep.version = ArtifactPom.findtext(dependency, 'version')
            dep.relativePath = None
            dep.type = ArtifactPom.findtext(dependency, 'type', 'jar')
            dep.scope = ArtifactPom.findtext(dependency, 'scope', 'compile')
            dep.key = f"{dep.groupId}:{dep.artifactId}"
            dep.name = f"{dep.groupId}:{dep.artifactId}:{dep.version}"
            # exclusions
            dep_exclusions = ArtifactPom.findall(dependency, 'exclusions/exclusion')
            exclusions = []
            for exclusion in dep_exclusions:
                self.unexpected_tags(exclusion, '*', ['groupId', 'artifactId'])
                excl = edict()
                excl.groupId = ArtifactPom.findtext(exclusion, 'groupId')
                excl.artifactId = ArtifactPom.findtext(exclusion, 'artifactId')
                exclusions.append(excl)
            dep.exclusions = exclusions
            # dep.sourceFile = self.name
            # dep.sourceVersion = self.name if infos.version else None
            dependencyManagement.append(dep)
        self.dependencyManagement = dependencyManagement
        # dependencies
        dependencies = []
        for dependency in ArtifactPom.findall(self.xml, 'dependencies/dependency'):
            dep = edict()
            dep.groupId = ArtifactPom.findtext(dependency, 'groupId')
            dep.artifactId = ArtifactPom.findtext(dependency, 'artifactId')
            dep.version = ArtifactPom.findtext(dependency, 'version')
            dep.relativePath = None
            dep.type = ArtifactPom.findtext(dependency, 'type', 'jar')
            dep.scope = ArtifactPom.findtext(dependency, 'scope', 'compile')
            dep.key = f"{dep.groupId}:{dep.artifactId}"
            dep.name = f"{dep.groupId}:{dep.artifactId}:{dep.version}"
            dep_exclusions = ArtifactPom.findall(dependency, 'exclusions/exclusion')
            # exclusions
            exclusions = []
            for exclusion in dep_exclusions:
                self.unexpected_tags(exclusion, '*', ['groupId', 'artifactId'])
                excl = edict()
                excl.groupId = ArtifactPom.findtext(exclusion, 'groupId')
                excl.artifactId = ArtifactPom.findtext(exclusion, 'artifactId')
                exclusions.append(excl)
            dep.exclusions = exclusions
            # dep.sourceFile = self.name
            # dep.sourceVersion = self.name
            dependencies.append(dep)
        self.dependencies = dependencies
        # modules
        modules = []
        for module in ArtifactPom.findall(self.xml, 'modules/module'):
            modules.append(module.text)
        self.modules = modules
        #
        return self

    def find(elem, tag: str):
        elem = elem.xml if isinstance(elem, ArtifactPom) else elem
        tag = tag.replace("/", "/" + POM)
        return elem.find(POM + tag)


    def findall(elem, tag: str) -> list:
        elem = elem.xml if isinstance(elem, ArtifactPom) else elem
        tag = tag.replace("/", "/" + POM)
        return elem.findall(POM + tag)


    def findtext(elem, tag: str, ifNone: str = None) -> str:
        elem = elem.xml if isinstance(elem, ArtifactPom) else elem
        tag = tag.replace("/", "/" + POM)
        value = elem.findtext(POM + tag)
        return value if value is not None else ifNone
    
    def findtags(elem, tag: str) -> list:
        elem = elem.xml if isinstance(elem, ArtifactPom) else elem
        tag = tag.replace("/", "/" + POM)
        return [ e.tag.replace(POM,"") for e in elem.findall(POM + tag) ]
    
    def unexpected_tags(self, elem, tag: str, allowed: list):
        # halt on non-expected tags, not groupId or artifactId
        tags = ArtifactPom.findtags(elem, tag)
        tags = [ t for t in tags if t not in allowed ]
        if len(tags) > 0:
            print(f"Unexpected tags: {tags} in pom {self.infos.fullname}\n{etree.tostring(elem)}")

    def builtin_properties(self, props: dict):
        # add parent built-in properties
        if self.parent is not None:
            props['parent.groupId'] = self.parent.groupId
            props['parent.artifactId'] = self.parent.artifactId
            props['parent.version'] = self.parent.version
            props['project.parent.groupId'] = self.parent.groupId
            props['project.parent.artifactId'] = self.parent.artifactId
            props['project.parent.version'] = self.parent.version
        # add project built-in properties
        props['artifactId'] = self.infos.artifactId
        props['groupId'] = self.infos.groupId
        props['version'] = self.infos.version
        props['project.artifactId'] = self.infos.artifactId
        props['project.groupId'] = self.infos.groupId
        props['project.version'] = self.infos.version
        props['pom.artifactId'] = self.infos.artifactId
        props['pom.groupId'] = self.infos.groupId
        props['pom.version'] = self.infos.version

    def resolve(value: str, props: dict = None) -> str:
        """
        Resolve properties in a string.
        Properties are defined as ${key} and are replaced by their value.
        """
        if props is None or value is None: return value
        def resolve_match(match):
            key = match.group(1)
            return props.get(key, match.group(0))
        return re.sub(r'\$\{([^}]+)\}', resolve_match, value)

if __name__ == '__main__':
    artifact = ArtifactPom.parse('pom.xml')
    print(ArtifactPom.findtext(artifact, 'artifactId'))
