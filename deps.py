import argparse, os

SECTIONS = 'project,proj,properties,props,managements,mgts,dependencies,deps,coll,collect,tree,all,none'.split(',')

# parse argumnes
parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--color', choices=['auto', 'never', 'always'], default='auto', help='Color output: auto, never, or always')
parser.add_argument('-b', '--basic', action="store_true", help='For basic tree output')
parser.add_argument('-D', '--define', action="append", help='Define properties in format "name=value"')
parser.add_argument('-f', '--file', default='pom.xml', type=str, help='pom.xml file location')
parser.add_argument('-pl', '--projects', help="Print only projects in format 'module,module,...'")
parser.add_argument('-q', '--quiet', action="store_true", help="Disable warnings")
parser.add_argument('-s', '--sections', default='dependencies', help='Print only sections: project|proj, properties|props, managements|mgts, dependencies|deps, collect|coll, tree, all, none')
parser.add_argument('--deps', help='Trace dependencies in format "groupId:artifactId,groupId:artifactId,..."')
parser.add_argument('--poms', action="store_true", help='Trace poms')
parser.add_argument('--props', help='Trace properties in format "name,name,..."')
parser.add_argument('--ranges', action="store_true", help='Trace ranges computation')
parser.add_argument('--jdk', default='21.0.2', help='JDK version')
parser.add_argument('-w', '--width', type=int, default=120, help='Width of the first colomn')

args = parser.parse_args()

color = os.isatty(1) if args.color == 'auto' else True if args.color == 'always' else False
sections = [ s.strip() for s in args.sections.split(',') ] if args.sections else [ 'all' ]
sections = SECTIONS if 'all' in sections else sections
projects = [ m.strip() for m in args.projects.split(',') ] if args.projects else None
width = args.width
file = os.path.isdir(args.file) and os.path.join(args.file, 'pom.xml') or args.file
defines = args.define or []

# check supported sections
for section in sections:
    if section not in SECTIONS:
        raise Exception(f"Unsupported section: '{section}'")

# check for traced dependencies
if args.deps:
    for dependency in args.deps.split(','):
        dependency = dependency.strip()
        if ':' not in dependency and dependency != '*':
            raise Exception(f"Invalid dependency format: '{dependency}', expected 'groupid:artifactid'")

# tracer
import pom_tracer
trace = False
tracer = pom_tracer.Tracer().set_debug(True).set_color(color)
if args.poms:
    tracer.set_poms(True)
    trace = True
if args.deps:
    for dep in args.deps.split(','):
        if dep.strip():
            name = ':'.join(dep.split(':',2)[0:2]) if dep != '*' else '*'
            tracer.add_dep(name)
            trace = True
if args.props:
    for prop in args.props.split(','):
        if prop.strip():
            tracer.add_prop(prop)
            trace = True
if args.ranges:
    tracer.set_ranges(True)
    trace = True
if trace:
    pom_tracer.TRACER = tracer

if args.quiet:
    pom_tracer.WARN = lambda _: None

# imports
from pom_loader import load_pom_from_file, register_pom_locations
from pom_solver import resolve_pom
from pom_printer import print_pom
from pom_struct import PomProperties
import pom_solver
pom_solver.JDK = args.jdk

def separator(s):
    # print separator
    print("#" * (width + 3))
    print(f"# {s} ".ljust(width + 2, " ") + "#")
    print("#" * (width + 3))


# define properties
initialProps = PomProperties()
for define in defines:
    name, value = define.split('=', 2)
    initialProps.set(name, value)

# it is needed to manually register all pom not located in M2 repository
# so they can be found even if their properties are not resolved
register_pom_locations(file, initialProps=initialProps.copy())

# load pom and resolve it
def print_files(file):
    pom = load_pom_from_file(file)
    assert pom
    if projects is None or pom.artifactId in projects:
        separator(pom.fullname())
        resolve_pom(pom, initialProps=initialProps.copy(), load_mgts = True, load_deps = True) #, initialProps = initialProps)
        print_pom(pom, color = color, basic = args.basic, sections = sections, indent = width)

    for module in pom.modules:
        module_file = os.path.join(os.path.dirname(file), module, 'pom.xml')
        print_files(module_file)

print_files(file)
