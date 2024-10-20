import os
from pom_loader import load_pom_from_file
from pom_solver import resolve_pom, ORDERED_SCOPES
from pom_struct import PomProject, PomDependency


def print_pom(pom: PomProject, indent: int = 120, color: bool = os.isatty(1), basic: bool = False):
    """
    Print the pom project.
    It is assumed that all properties, dependencyManagement and dependencies have already been loaded.
    """
    nocolor = lambda x: x
    c_name = nocolor if not color else lambda x: f"\033[1;33m{x}\033[0m"
    c_val = nocolor if not color else lambda x: f"\033[1;32m{x}\033[0m"
    c_indent = 11 if color else 0
    indent1 = indent + c_indent
    indent2 = indent + 2 * c_indent

    print(f"Project: {pom.fullname()}")

    print()
    print(f"Properties ({len(pom.computed_properties)}):")
    for prop in sorted(pom.computed_properties.values(), key=lambda p: p.name):
        paths = dump_paths(prop.paths)
        print_comment(indent2, f"    {c_name(prop.name)}: {c_val(prop.value)}", paths)

    print()
    print(f"Dependency Management ({len(pom.computed_managements)}):")
    for dep in sorted(pom.computed_managements.values(), key=lambda d: (d.groupId, d.artifactId, d.scope)):
        paths = dump_paths(dep.paths)
        print_comment(indent2, f"    {c_name(dep.key_ga())}:{c_val(dep.version)}", paths)

    print()
    print(f"Dependencies ({len(pom.computed_dependencies)}):")
    previous = ''
    dep_cols = []
    dep_parents = {}
    dep_col = PomDependency()
    dep_col_order = 0
    for dep in sorted(pom.computed_dependencies, key=lambda d: (d.groupId, d.artifactId)):
        if previous == '' or previous != dep.key_ga():
            previous = dep.key_ga()
            dep_col = PomDependency()
            dep_col.groupId = dep.groupId
            dep_col.artifactId = dep.artifactId
            dep_col.version = dep.version
            dep_col.scope = dep.scope
            dep_col.paths = dep.paths
            dep_col.pathsVersion = dep.pathsVersion
            dep_cols.append(dep_col)
            dep_col_order = ORDERED_SCOPES.index(dep.scope)

            print_comment(indent1, f"    {c_name(dep.key_ga())}")
        else:
            dep_order = ORDERED_SCOPES.index(dep.scope)
            if dep_order < dep_col_order:
                dep_col.scope = dep.scope

        paths = dump_paths(dep.paths)
        print_comment(indent1, f"        {c_val(dep.version)}:{dep.scope}", paths, 'dep: ')
        paths = dump_paths(dep.pathsVersion)
        print_comment(indent, "", paths, 'ver: ')

        if dep.fullname() not in dep_parents:
            dep_parents[dep.fullname()] = [ dep.paths[-1].fullname() ]
        else:
            dep_parents[dep.fullname()].append(dep.paths[-1].fullname())


    print()
    print(f"Collected Dependencies ({len(dep_cols)}):")
    for dep in dep_cols:
        paths = dump_paths(dep.paths)
        print_comment(indent2, f"    {c_name(dep.key_ga())}:{c_val(dep.version)}:{dep.scope}", paths, 'dep: ')

    print()
    dep_elems = dep_cols[:]
    dep_root = (pom, [])
    dep_nodes = { pom.fullname(): dep_root }
    for dep in dep_elems:
        parents = dep_parents[dep.fullname()]
        found = False
        for parent in parents:
            if parent in dep_nodes:
                dep_nodes[parent][1].append(dep)
                dep_nodes[dep.fullname()] = (dep, [])
                found = True
                break
        if not found:
            dep_elems.append(dep)

    print(f"Tree Dependencies ({len(dep_nodes) - 1}):")
    elbow = "\\- " if basic else "└─ "
    pipe = "|  " if basic else "│  "
    tee = "+- " if basic else "├─ "
    blank = "   "
    def tree_loop(start, header=''):
        childs = dep_nodes[start][1]
        size = len(childs)
        for i, node in enumerate(childs):
            h = header + elbow if i + 1 == size else header + tee
            dep = node
            paths = dump_paths(dep.pathsVersion)
            print_comment(indent2, f"    {h}{c_name(dep.key_ga())}:{c_val(dep.version)}:{dep.scope}", paths, 'ver: ')
            h = header + blank if i + 1 == size else header + pipe
            tree_loop(dep.fullname(), h)

    print_comment(indent2, f"    {c_name(pom.key_ga())}:{c_val(pom.version)}")
    tree_loop(pom.fullname())


def cname(name: str) -> str:
    return f"${{{name}}}"


def print_comment(indent: int, text: str, comment: str = '', prefix: str = ''):
    if len(comment) == 0:
        print(text)
    else:
        print(f"{text.ljust(indent)}  # {prefix}{comment}")


def dump_paths(paths: list[PomProject]):
    """
    Dump paths to a string.
    """
    if len(paths) == 1:
        return '.'
    return ' -> '.join([p.fullname() for p in paths[1:]])


if __name__ == '__main__':
    pom1 = load_pom_from_file('myartifact/pom.xml')
    resolve_pom(pom1, load_mgts = True, load_deps = True)
    print_pom(pom1)
