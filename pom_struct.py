from copy import deepcopy

class PomProject:
    """
    Represents a Maven project.
    """
    file: str
    groupId: str
    artifactId: str
    version: str
    name: str
    packaging: str
    parent: 'PomParent'
    properties: 'PomProperties'
    builtins: 'PomProperties'
    managements: list['PomDependency']
    dependencies: list['PomDependency']
    # computed
    computed_properties: 'PomProperties'
    computed_managements: 'PomMgts'
    computed_dependencies: 'PomDeps'

    def clone(self) -> 'PomProject':
        return deepcopy(self)

    def fullname(self):
        return f"{self.groupId}:{self.artifactId}:{self.version}"

    def key_ga(self):
        return f"{self.groupId}:{self.artifactId}"

    def __repr__(self):
        return self.fullname()
    

class PomParent:
    """
    Represents a Maven parent.
    """
    groupId: str
    artifactId: str
    version: str
    relativePath: str
    pom: PomProject

    def fullname(self):
        return f"{self.groupId}:{self.artifactId}:{self.version}"


class PomProperty:
    """
    Represents a Maven properties.
    """
    name: str
    value: str | None
    paths: list[PomProject] = []

    def __repr__(self) -> str:
        return f"{self.name}={self.value}"


class PomProperties(dict[str, PomProperty]):
    """
    Represents a Maven properties.
    """
    def add(self, name: str, value: str, paths: list[PomProject] = None):
        """
        Add a property value, only if not already exists.
        """
        if name in self:
            return
        self.set(name, value, paths)

    def set(self, name: str, value: str, paths: list[PomProject] = None):
        """
        Add or Update a property value if already exists.
        """
        prop = PomProperty()
        prop.name = name
        prop.value = value
        prop.paths = paths
        self[name] = prop


class PomExclusion:
    """
    Represents a Maven dependency exclusion.
    """
    groupId: str
    artifactId: str

    def fullname(self):
        return f"{self.groupId}:{self.artifactId}"

    def key(self):
        return f"{self.groupId}:{self.artifactId}"


class PomDependency:
    """
    Represents a Maven dependency.
    """
    groupId: str
    artifactId: str
    version: str
    scope: str
    type: str
    classifier: str
    paths: list[PomProject]
    pathsVersion: list[PomProject]
    exclusions: list[PomExclusion]
    # unused properties
    relativePath: str

    def fullname(self):
        return f"{self.groupId}:{self.artifactId}:{self.version}"

    def key_ga(self):
        return f"{self.groupId}:{self.artifactId}"

PomInfos = PomProject | PomParent | PomDependency
PomMgts = dict[str, PomDependency]
PomDeps = list[PomDependency]
PomPaths = list[PomProject]

if __name__ == "__main__":
    # verify that the object is deep cloned
    project1 = PomProject()
    project1.groupId = "com.example1"
    project1.parent = PomParent()
    project1.parent.groupId = "com.example1.parent"
    project2 = project1.clone()
    project2.groupId = "com.example2"
    project2.parent.groupId = "com.example2.parent"
    assert project1.groupId == "com.example1"
    assert project2.groupId == "com.example2"
    assert project1.parent.groupId == "com.example1.parent"
    assert project2.parent.groupId == "com.example2.parent"
    # passed
    print("PASSED")
