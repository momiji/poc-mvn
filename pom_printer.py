import os
from pom_loader import load_pom_from_file
from pom_solver import resolve_pom, ORDERED_SCOPES
from pom_struct import PomProject, PomDependency

SECTIONS = ['project', 'properties', 'managements', 'dependencies', 'collect', 'tree']
SECTIONS_ALIAS = { 'proj': 'project', 'props': 'properties', 'mgts': 'managements', 'deps': 'dependencies', 'coll': 'collect' }


def print_pom(pom: PomProject, indent: int = 120, color = os.isatty(1), basic = False, sections: list[str] | None = None):
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

    # compute sections to print
    if sections is None: sections = SECTIONS
    for section in sections:
        if section in SECTIONS_ALIAS:
            sections.append(SECTIONS_ALIAS[section])
    
    # print separator
    print("#" * indent)
    print(f"# {pom.fullname2()} ".ljust(indent - 1, " ") + "#")
    print("#" * indent)

    if 'project' in sections:
        print()
        print(f"Project: {c_name(pom.key_gap())}:{c_val(pom.version)}")

    if 'properties' in sections:
        print()
        print(f"Properties ({len(pom.computed_properties)}):")
        for prop in sorted(pom.computed_properties.values(), key=lambda p: p.name):
            paths = dump_paths(prop.paths)
            print_comment(indent2, f"    {c_name(prop.name)}: {c_val(prop.value)}", paths)

    if 'managements' in sections:
        print()
        print(f"Dependency Management ({len(pom.computed_managements)}):")
        for dep in sorted(pom.computed_managements.values(), key=lambda d: (d.groupId, d.artifactId, d.scope)):
            paths = dump_paths(dep.paths)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}", paths)

    if 'dependencies' in sections or 'collect' in sections or 'tree' in sections:
        print_deps = 'dependencies' in sections
        print_coll = 'collect' in sections
        print_tree = 'tree' in sections
        if print_deps:
            print()
            print(f"Dependencies ({len(pom.computed_dependencies)}):")
        previous = ''
        dep_cols = []
        dep_parents = {}
        dep_col = PomDependency()
        dep_col_order = 0
        for dep in sorted(pom.computed_dependencies, key=lambda d: (d.groupId, d.artifactId)):
            if dep.type == 'parent': continue
            if previous == '' or previous != dep.key_gat():
                previous = dep.key_gat()
                dep_col = PomDependency()
                dep_col.groupId = dep.groupId
                dep_col.artifactId = dep.artifactId
                dep_col.version = dep.version
                dep_col.type = dep.type
                dep_col.scope = dep.scope
                dep_col.paths = dep.paths
                dep_col.pathsVersion = dep.pathsVersion
                dep_cols.append(dep_col)
                dep_col_order = ORDERED_SCOPES.index(dep.scope)

                if print_deps:
                    print_comment(indent1, f"    {c_name(dep.key_gat())}")
            else:
                dep_order = ORDERED_SCOPES.index(dep.scope)
                if dep_order < dep_col_order:
                    dep_col.scope = dep.scope

            if print_deps:
                paths = dump_paths(dep.paths)
                print_comment(indent1, f"        {c_val(dep.version)}:{dep.scope}", paths, 'dep: ')
                paths = dump_paths(dep.pathsVersion)
                print_comment(indent, "", paths, 'ver: ')

            if dep.fullname() not in dep_parents:
                dep_parents[dep.fullname()] = [ dep.paths[-1].fullname() ]
            else:
                dep_parents[dep.fullname()].append(dep.paths[-1].fullname())

        if print_coll:
            print()
            print(f"Collected Dependencies ({len(dep_cols)}):")
            for dep in dep_cols:
                paths = dump_paths(dep.paths)
                print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}", paths, 'dep: ')

        if print_tree:
            print()
            dep_elems = dep_cols[:]
            dep_root = (pom, [])
            dep_nodes = { pom.fullname(): dep_root }

            # create graph
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
            
            # remove 'parent' types
            def remove_type(node, parent):
                dep = node[0]
                childs = node[1]
                if dep.type == 'parent' and parent is not None:
                    parent.extend(childs)
                    del dep_nodes[dep.fullname()]
                else:
                    parent = childs
                for child in childs:
                    remove_type(child, parent)

            # print tree
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
                    print_comment(indent2, f"    {h}{c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}", paths, 'ver: ')
                    h = header + blank if i + 1 == size else header + pipe
                    tree_loop(dep.fullname(), h)

            print_comment(indent2, f"    {c_name(pom.key_ga())}:{c_val(pom.version)}")
            tree_loop(pom.fullname())


def cname(name: str) -> str:
    return f"${{{name}}}"


def print_comment(indent: int, text: str, comment = '', prefix =''):
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
    return ' -> '.join([p.fullname2() for p in paths[1:]])


if __name__ == '__main__':
    pom1 = load_pom_from_file('myartifact/pom.xml')
    assert pom1
    resolve_pom(pom1, load_mgts = True, load_deps = True)
    print_pom(pom1)
