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
    managements: 'PomDeps'
    dependencies: 'PomDeps'
    modules: list[str]
    profiles: 'PomProfiles'
    # computed
    computed_properties: 'PomProperties'
    initial_managements: 'PomMgts'
    computed_managements: 'PomMgts'
    added_dependencies: 'PomDeps'
    computed_dependencies: 'PomMgts'
    computed_scope: str
    computed_exclusions: 'PomExclusions'
    computed_type: str

    def copy(self) -> 'PomProject':
        pom = PomProject()
        pom.file = self.file
        pom.groupId = self.groupId
        pom.artifactId = self.artifactId
        pom.version = self.version
        pom.name = self.name
        pom.packaging = self.packaging
        pom.parent = self.parent.copy() if self.parent else None
        pom.properties = deepcopy(self.properties)
        pom.builtins = self.builtins            # not modified in loader and solver
        pom.managements = self.managements      # not modified in loader and solver, as load_managements is always copying it
        pom.dependencies = self.dependencies    # not modified in loader and solver, as load_dependencies is always copying it
        pom.modules = self.modules              # not modified in loader and solver
        pom.computed_scope = 'all'
        pom.computed_type = 'pom'
        pom.profiles = self.profiles            # not modified in loader and solver
        return pom

    def gav(self):
        return f"{self.groupId}:{self.artifactId}:{self.version}"

    def fullname(self):
        if self.computed_type == 'pom' or self.computed_type == 'parent':
            return f"{self.groupId}:{self.artifactId}:{self.packaging}:{self.version}"
        else:
            return f"{self.groupId}:{self.artifactId}:{self.packaging}:{self.version}:{self.computed_scope}"

    def key_gap(self):
        return f"{self.groupId}:{self.artifactId}:{self.packaging}"

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
    # computed
    pom: PomProject

    def copy(self) -> 'PomParent':
        pom = PomParent()
        pom.groupId = self.groupId
        pom.artifactId = self.artifactId
        pom.version = self.version
        pom.relativePath = self.relativePath
        return pom

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
    paths: 'PomPaths'

    def __repr__(self) -> str:
        return f"PomProperty({self.name}={self.value})"


class PomProperties(dict[str, PomProperty]):
    """
    Represents a Maven properties.
    """
    def addIfMissing(self, name: str, value: str, paths: 'PomPaths | None' = None):
        """
        Set a property value only if it does not already exists.
        """
        if name in self:
            return
        self.set(name, value, paths)

    def set(self, name: str, value: str, paths: 'PomPaths | None' = None):
        """
        Set a property value even if it already exists.
        """
        prop = PomProperty()
        prop.name = name
        prop.value = value
        prop.paths = paths or PomPaths()
        self[name] = prop
    
    def copy(self) -> 'PomProperties':
        return copy(self)
    
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
    paths: 'PomPaths'
    exclusions: list[PomExclusion]
    # unused properties
    relativePath: str
    # hidden properties
    not_found: bool
    # paths for properties
    pathsVersion: 'PomPaths'
    pathsScope: 'PomPaths'
    pathsOptional: 'PomPaths'
    pathsExclusions: 'PomPaths'

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
        return f"PomDependency({self.groupId}:{self.artifactId}:{self.type}:{self.version})[{self.paths.length}]"


class PomPaths:
    """
    Represents a Maven dependency path.
    """
    paths: list[PomProject]
    length: int

    def __init__(self):
        self.paths = []
        self.length = 0

    def add(self, pom: PomProject, incr: int):
        paths = PomPaths()
        paths.paths = self.paths + [ pom ]
        paths.length = self.length + incr
        return paths


class PomProfile:
    """
    Represents a Maven profile.
    """
    id: str
    active_by_default = False
    property_name = ''
    property_value = ''
    jdk = ''
    os_name = ''
    os_family = ''
    os_arch = ''
    os_version = ''
    file_exists = ''
    file_missing = ''
    properties: 'PomProperties'
    managements: 'PomDeps'
    dependencies: 'PomDeps'
    modules: list[str]


PomInfos = PomProject | PomParent | PomDependency
PomMgts = dict[str, PomDependency]
PomDeps = list[PomDependency]
PomExclusions = dict[str, PomExclusion]
PomProfiles = list[PomProfile]

if __name__ == "__main__":
    # verify that the object is deep cloned
    project1 = PomProject()
    project1.groupId = "com.example1"
    project1.parent = PomParent()
    project1.parent.groupId = "com.example1.parent"
    project2 = project1.copy()
    project2.groupId = "com.example2"
    assert project2.parent
    project2.parent.groupId = "com.example2.parent"
    assert project1.groupId == "com.example1"
    assert project2.groupId == "com.example2"
    assert project1.parent.groupId == "com.example1.parent"
    assert project2.parent.groupId == "com.example2.parent"
    # passed
    print("PASSED")
