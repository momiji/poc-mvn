import argparse, os, sys

# parse argumnes
parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--color', choices=['auto', 'never', 'always'], default='auto', help='Color output: auto, never, or always')
parser.add_argument('-b', '--basic', action="store_true", help='For basic tree output')
parser.add_argument('-s', '--sections', default='collect', help='Print only sections: project|proj, properties|props, managements|mgts, dependencies|deps, collect|coll, tree (comma separated)')
parser.add_argument('-m', '--modules', help="Print only modules in format 'module,module,...'")
parser.add_argument('-p', '--trace-poms', action="store_true", help='Trace poms')
parser.add_argument('-d', '--trace-deps', help='Trace dependencies in format "groupId:artifactId,groupId:artifactId,..."')
parser.add_argument('--trace-props', help='Trace properties in format "name,name,..."')
parser.add_argument('--trace-ranges', action="store_true", help='Trace ranges computation')
parser.add_argument('-v', '--verbose', action="store_true", help='Trace verbose mode')
parser.add_argument('file', nargs='?', default='pom.xml', type=str, help='pom.xml file location')

args = parser.parse_args()

color = os.isatty(1) if args.color == 'auto' else True if args.color == 'always' else False
sections = [ s.strip() for s in args.sections.split(',') ] if args.sections else None
modules = [ m.strip() for m in args.modules.split(',') ] if args.modules else None

# tracer
trace = False

import pom_tracer
tracer = pom_tracer.Tracer().set_debug(args.verbose)
if args.trace_poms:
    tracer.set_poms(True)
    trace = True
if args.trace_deps:
    for dep in args.trace_deps.split(','):
        if dep.strip():
            tracer.add_dep(dep)
            trace = True
if args.trace_props:
    for prop in args.trace_props.split(','):
        if prop.strip():
            tracer.add_prop(prop)
            trace = True
if args.trace_ranges:
    tracer.set_ranges(True)
    trace = True

# imports
from pom_loader import load_pom_from_file, register_pom_locations
from pom_solver import resolve_pom
from pom_printer import print_pom
from pom_struct import PomProperties

# it is needed to manually register all pom not located in M2 repository
# so they can be found even if their properties are not resolved
register_pom_locations(args.file)

# load pom and resolve it
def print_files(file, module = None):
    pom = load_pom_from_file(file)
    assert pom
    resolve_pom(pom, load_mgts = True, load_deps = True) #, initialProps = initialProps)
    if modules is None or module:
        print_pom(pom, color = color, basic = args.basic, sections = sections)

    for module in pom.modules:
        if modules is None or module in modules:
            module_file = os.path.join(os.path.dirname(file), module, 'pom.xml')
            print_files(module_file, module)

print_files(args.file)
