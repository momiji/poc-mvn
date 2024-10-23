import os
from pom_loader import load_pom_from_file
from pom_solver import resolve_pom
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
    
    if 'project' in sections:
        print(f"Project: {c_name(pom.key_gap())}:{c_val(pom.version)}")
        print()

    if 'properties' in sections:
        print(f"Properties ({len(pom.computed_properties)}):")
        print()
        for prop in sorted(pom.computed_properties.values(), key=lambda p: p.name):
            paths = dump_paths(prop.paths)
            print_comment(indent2, f"    {c_name(prop.name)}: {c_val(prop.value)}", paths)
        print()

    if 'managements' in sections:
        print(f"Dependency Management ({len(pom.computed_managements)}):")
        for dep in sorted(pom.computed_managements.values(), key=lambda d: (d.groupId, d.artifactId, d.scope)):
            paths = dump_paths(dep.paths)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}", paths)
        print()

    if 'dependencies' in sections:
        print(f"All non-unique Dependencies ({len(pom.added_dependencies)}):")
        print()
        for dep in sorted(pom.added_dependencies, key=lambda d: (d.groupId, d.artifactId)):
            if dep.type == 'parent': continue
            paths = dump_paths(dep.paths)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'dep: ')
            paths = dump_paths(dep.pathsVersion)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'ver: ')
            paths = dump_paths(dep.pathsScope)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'scp: ')
            paths = dump_paths(dep.pathsExclusions)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'exc: ')
            print()

    if 'collect' in sections:
        print(f"Collected Dependencies ({len(pom.computed_dependencies)}):")
        print()
        for dep in sorted(pom.computed_dependencies.values(), key=lambda d: (d.groupId, d.artifactId)):
            if dep.type == 'parent': continue
            paths = dump_paths(dep.paths)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'dep: ')
            paths = dump_paths(dep.pathsVersion)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'ver: ')
            paths = dump_paths(dep.pathsScope)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'scp: ')
            paths = dump_paths(dep.pathsExclusions)
            print_comment(indent2, f"    {c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'exc: ')
            print()

    if 'tree' in sections:
        dep_elems: list[PomDependency] = list(pom.computed_dependencies.values())
        dep_pom = PomDependency()
        dep_pom.groupId = pom.groupId
        dep_pom.artifactId = pom.artifactId
        dep_pom.version = pom.version
        dep_root = (dep_pom, [])
        dep_nodes = { pom.key_excl(): dep_root }
        dep_parents = {}
        for dep in sorted(dep_elems, key=lambda d: (d.groupId, d.artifactId)):
            if dep.key_excl() not in dep_parents:
                dep_parents[dep.key_excl()] = [ dep.paths[-1].key_excl() ]
            else:
                dep_parents[dep.key_excl()].append(dep.paths[-1].key_excl())

        # create graph
        for dep in dep_elems:
            parents = dep_parents[dep.key_excl()]
            found = False
            for parent in parents:
                if parent in dep_nodes:
                    dep_nodes[parent][1].append(dep)
                    dep_nodes[dep.key_excl()] = (dep, [])
                    found = True
                    break
            if not found:
                dep_elems.append(dep)

        # remove 'parent' types
        def remove_parents(node, parent):
            dep = node[0]
            childs = node[1]
            if parent is not None and dep.type == 'parent':
                parent[1].extend(childs)
                childs = []
                del dep_nodes[dep.key_excl()]
            else:
                parent = node
            for child in childs:
                node = dep_nodes[child.key_excl()]
                remove_parents(node, parent)
        remove_parents(dep_root, None)

        # print tree
        print(f"Tree Dependencies ({len(dep_nodes) - 1}):")
        print()
        elbow = "\\- " if basic else "└─ "
        pipe = "|  " if basic else "│  "
        tee = "+- " if basic else "├─ "
        blank = "   "
        def tree_loop(start, header=''):
            childs = dep_nodes[start.key_excl()][1]
            childs = [ d for d in childs if d.key_excl() in dep_nodes ]
            size = len(childs)
            for i, node in enumerate(childs):
                h = header + elbow if i + 1 == size else header + tee
                dep = node
                paths = dump_paths(dep.pathsVersion)
                print_comment(indent2, f"    {h}{c_name(dep.key_gat())}:{c_val(dep.version)}:{dep.scope}{' not found' if dep.not_found else ''}", paths, 'ver: ')
                h = header + blank if i + 1 == size else header + pipe
                tree_loop(dep, h)

        print_comment(indent2, f"    {c_name(pom.key_ga())}:{c_val(pom.version)}")
        tree_loop(pom)

        print()


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
