import argparse, os, sys
import pom_tracer

pom_tracer.TRACER = pom_tracer.Tracer()
pom_tracer.TRACER = None
pom_tracer.TRACER2 = pom_tracer.Tracer2().set_poms(True).set_mgts(True).set_debug(True)
# pom_tracer.TRACER2.add_dep("joda-time:joda-time")
# pom_tracer.TRACER2.add_dep("org.testng:testng")
# pom_tracer.TRACER2.add_prop("jodatime.version")
# pom_tracer.TRACER2.add_dep("io.grpc:grpc-core")
# pom_tracer.TRACER2.add_dep("io.grpc:grpc-api")
# pom_tracer.TRACER2.add_dep("org.junit.jupiter:junit-jupiter-migrationsupport")
# pom_tracer.TRACER2.add_dep("com.amazonaws:aws-java-sdk-core")
# pom_tracer.TRACER2 = None

from pom_tracer import TRACER
from pom_loader import load_pom_from_file, register_pom_location
from pom_solver import resolve_pom
from pom_printer import print_pom
from pom_struct import PomProperties

# parse argumnes
parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--color', action="store_true", default=os.isatty(1), help='Force color output')
parser.add_argument('--basic', action="store_true", help='For basic tree output')
parser.add_argument('--sections', help='Print only sections: project|proj, properties|props, managements|mgts, dependencies|deps, collect|coll, tree (comma separated)')
parser.add_argument('file', nargs='?', default='pom.xml', type=str, help='pom.xml file location')
args = parser.parse_args()

args.file = '/home/a443939/work/raven2/bug-json-parser/Jarvis/crr/pom.xml'
args.sections = 'coll'

# args.file = 'myartifact/pom.xml'

print(args)

# tracer
if TRACER: TRACER.trace("start")

# dep = PomDependency()
# dep.groupId = 'com.amazonaws'
# dep.artifactId = 'aws-java-sdk-s3control'
# dep.version = '1.12.10'
# dep.relativePath = ''
# pom = load_pom_from_dependency(dep, "/")
# resolve_pom(pom, load_mgts = True, load_deps = True)
# print_pom(pom, color = args.color, basic = args.basic, sections = args.sections.split(',') if args.sections else None)

# sys.exit(0)

try:
    # register pom file and its modules
    register_pom_location(args.file)

    # load pom and resolve it
    def print_files(file, initialProps: PomProperties | None = None):
        pom = load_pom_from_file(file)
        assert pom
        resolve_pom(pom, load_mgts = True, load_deps = True) #, initialProps = initialProps)
        print_pom(pom, color = args.color, basic = args.basic, sections = args.sections.split(',') if args.sections else None)

        for module in pom.modules:
            module_file = os.path.join(os.path.dirname(file), module, 'pom.xml')
            print("print_files", module_file)
            print_files(module_file, pom.computed_properties)
            return

    print_files(args.file)
except:
    if TRACER: TRACER.trace("exception")
    if TRACER: TRACER.show_traces()
    raise

if TRACER: TRACER.trace("end")
