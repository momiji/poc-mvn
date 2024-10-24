import argparse, os

# parse argumnes
parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--color', choices=['auto', 'never', 'always'], default='auto', help='Color output: auto, never, or always')
parser.add_argument('-b', '--basic', action="store_true", help='For basic tree output')
parser.add_argument('-s', '--sections', default='dependencies', help='Print only sections: project|proj, properties|props, managements|mgts, dependencies|deps, collect|coll, tree, all, none')
parser.add_argument('-m', '--modules', help="Print only modules in format 'module,module,...'")
parser.add_argument('--trace-poms', action="store_true", help='Trace poms')
parser.add_argument('-d', '--trace-deps', help='Trace dependencies in format "groupId:artifactId,groupId:artifactId,..."')
parser.add_argument('-p', '--trace-props', help='Trace properties in format "name,name,..."')
parser.add_argument('-r', '--trace-ranges', action="store_true", help='Trace ranges computation')
parser.add_argument('-v', '--verbose', action="store_true", help='Trace verbose mode')
parser.add_argument('file', nargs='?', default='pom.xml', type=str, help='pom.xml file location')
parser.add_argument('-w', '--width', type=int, default=150, help='Width of the first colomn')

args = parser.parse_args()

color = os.isatty(1) if args.color == 'auto' else True if args.color == 'always' else False
sections = [ s.strip() for s in args.sections.split(',') ] if args.sections else [ 'all' ]
modules = [ m.strip() for m in args.modules.split(',') ] if args.modules else None
width = args.width

# check supported sections
SECTIONS = 'project,proj,properties,props,managements,mgts,dependencies,deps,coll,collect,tree,all,none'.split(',')
for section in sections:
    if section not in SECTIONS:
        raise Exception(f"Unsupported section: '{section}'")

# check for traced dependencies
if args.trace_deps:
    for dependency in args.trace_deps.split(','):
        dependency = dependency.strip()
        if ':' not in dependency and dependency != '*':
            raise Exception(f"Invalid dependency format: '{dependency}', expected 'groupid:artifactid'")

# tracer
import pom_tracer
trace = False
tracer = pom_tracer.Tracer().set_debug(args.verbose).set_color(color)
if args.trace_poms:
    tracer.set_poms(True)
    trace = True
if args.trace_deps:
    for dep in args.trace_deps.split(','):
        if dep.strip():
            name = ':'.join(dep.split(':',2)[0:2]) if dep != '*' else '*'
            tracer.add_dep(name)
            trace = True
if args.trace_props:
    for prop in args.trace_props.split(','):
        if prop.strip():
            tracer.add_prop(prop)
            trace = True
if args.trace_ranges:
    tracer.set_ranges(True)
    trace = True
if trace:
    pom_tracer.TRACER = tracer

# imports
from pom_loader import load_pom_from_file, register_pom_locations
from pom_solver import resolve_pom
from pom_printer import print_pom

def separator(s):
    # print separator
    print("#" * width)
    print(f"# {s} ".ljust(width - 1, " ") + "#")
    print("#" * width)
    print()


# it is needed to manually register all pom not located in M2 repository
# so they can be found even if their properties are not resolved
register_pom_locations(args.file)

# load pom and resolve it
def print_files(file):
    pom = load_pom_from_file(file)
    assert pom
    if modules is None or pom.artifactId in modules:
        separator(pom.fullname2())
        resolve_pom(pom, load_mgts = True, load_deps = True) #, initialProps = initialProps)
        print_pom(pom, color = color, basic = args.basic, sections = sections, indent = width)

    for module in pom.modules:
        module_file = os.path.join(os.path.dirname(file), module, 'pom.xml')
        print_files(module_file)

print_files(args.file)
