import os
from pom_loader import load_pom_from_file
from pom_solver import resolve_pom, ORDERED_SCOPES
from pom_struct import PomProject, PomDependency


def print_pom(pom: PomProject, indent: int = 120, color: bool = os.isatty(1)):
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
    print("Properties:")
    for prop in sorted(pom.computed_properties.values(), key=lambda p: p.name):
        paths = dump_paths(prop.paths)
        print_comment(indent2, f"    {c_name(prop.name)}: {c_val(prop.value)}", paths)

    print()
    print("Dependency Management:")
    for dep in sorted(pom.computed_managements.values(), key=lambda d: (d.groupId, d.artifactId, d.scope)):
        paths = dump_paths(dep.paths)
        print_comment(indent2, f"    {c_name(dep.key_ga())}:{c_val(dep.version)}", paths)

    print()
    print("Dependencies:")
    previous = ''
    dep_cols = []
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


    print()
    print("Collected Dependencies:")
    for dep in dep_cols:
        paths = dump_paths(dep.paths)
        print_comment(indent2, f"    {c_name(dep.key_ga())}:{c_val(dep.version)}:{dep.scope}", paths, 'dep: ')

    print()
    print("Tree Dependencies:")
    dep_tree = dep_cols
    def tree_loop(start, header=''):
        size = len(start)
        deps = [d for d in dep_tree if len(d.paths) == size and d.paths[0:size] == start]
        for i, dep in enumerate(deps):
            h = header + '\\- ' if i + 1 == len(deps) else header + '+- '
            paths = dump_paths(dep.pathsVersion)
            print_comment(indent2, f"    {h}{c_name(dep.key_ga())}:{c_val(dep.version)}:{dep.scope}", paths, 'ver: ')
            childs = [d.paths[size] for d in dep_tree if len(d.paths) == size + 1 and d.paths[0:size] == start and d.paths[size].fullname() == dep.fullname()]
            childs = list(dict.fromkeys(childs))
            for  child in childs:
                h = header + '   ' if i + 1 == len(deps) else header + '|  '
                tree_loop(start + [child], h)

    print_comment(indent2, f"    {c_name(pom.key_ga())}:{c_val(pom.version)}")
    deps = [d.paths[0] for d in dep_tree if len(d.paths) == 1]
    deps = list(dict.fromkeys(deps))
    for dep in deps:
        tree_loop([ dep ])


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
    print_pom(pom1, color = True)
