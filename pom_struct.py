from copy import copy, deepcopy

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
    parent: 'PomParent | None'
    properties: 'PomProperties'
    builtins: 'PomProperties'
    managements: list['PomDependency']
    dependencies: list['PomDependency']
    modules: list[str]
    # computed
    computed_properties: 'PomProperties'
    initial_managements: 'PomMgts'
    computed_managements: 'PomMgts'
    computed_dependencies: 'PomDeps'

    def clone(self) -> 'PomProject':
        return deepcopy(self)

    def fullname(self):
        return f"{self.groupId}:{self.artifactId}:{self.version}"

    def key_ga(self):
        return f"{self.groupId}:{self.artifactId}"

    def key_excl(self):
        return f"{self.groupId}:{self.artifactId}"

    def __repr__(self):
        return f"PomProject({self.fullname()})"
    

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

    def __repr__(self) -> str:
        return f"PomParent({self.fullname()})"


class PomProperty:
    """
    Represents a Maven properties.
    """
    name: str
    value: str
    paths: list[PomProject]

    def __repr__(self) -> str:
        return f"PomProperty({self.name}={self.value})"


class PomProperties(dict[str, PomProperty]):
    """
    Represents a Maven properties.
    """
    def addIfMissing(self, name: str, value: str, paths: list[PomProject] | None = None):
        """
        Set a property value only if it does not already exists.
        """
        if name in self:
            return
        self.set(name, value, paths)

    def set(self, name: str, value: str, paths: list[PomProject] | None = None):
        """
        Set a property value even if it already exists.
        """
        prop = PomProperty()
        prop.name = name
        prop.value = value
        prop.paths = paths or []
        self[name] = prop
    
    def __repr__(self) -> str:
        return f"PomProperties({len(self)})"


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
    
    def __repr__(self) -> str:
        return f"PomExclusion({self.fullname()})"


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
    optional: str
    paths: list[PomProject]
    pathsVersion: list[PomProject]
    pathsScope: list[PomProject]
    pathsOptional: list[PomProject]
    pathsExclusions: list[PomProject]
    exclusions: list[PomExclusion]
    # unused properties
    relativePath: str
    # hidden properties
    not_found: bool

    def fullname(self):
        return f"{self.groupId}:{self.artifactId}:{self.version}"

    def fullname2(self):
        return f"{self.groupId}:{self.artifactId}:{self.type}:{self.version}"

    def key_excl(self):
        return f"{self.groupId}:{self.artifactId}"
    
    def key_gat(self):
        return f"{self.groupId}:{self.artifactId}:{self.type}"
    
    def key_trace(self):
        return f"{self.groupId}:{self.artifactId}"
    
    def copy(self) -> 'PomDependency':
        return copy(self)
    
    def __repr__(self) -> str:
        return f"PomDependency({self.groupId}:{self.artifactId}:{self.type}:{self.version})[{len(self.paths) if 'paths' in self.__dict__ else 0}]"


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
    assert project2.parent
    project2.parent.groupId = "com.example2.parent"
    assert project1.groupId == "com.example1"
    assert project2.groupId == "com.example2"
    assert project1.parent.groupId == "com.example1.parent"
    assert project2.parent.groupId == "com.example2.parent"
    # passed
    print("PASSED")
