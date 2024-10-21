import os

TRACER: 'Tracer | None' = None

class Tracer:
    def __init__(self):
        self._traces = []
        # top only prperties
        self._current = self
        self._paths = []

    def trace(self, text):
        self._current._traces.append(text)

    def trace_parent(self, text):
        self._paths[-1]._traces.append(text)

    def enter(self, text = None):
        if text:
            self.trace(format)
        t = Tracer()
        self._paths.append(self._current)
        self._current = t
    
    def exit(self, text = None):
        if text:
            self.trace(format)
        self._current = self._paths.pop()

    def show_traces(self, indent = 0):
        indent = 0
        for p in self._paths + [self._current]:
            for t in p._traces:
                print(f"{'  ' * indent} {t}")
            indent += 1

TRACER2: 'Tracer2 | None' = None

class Tracer2:
    def __init__(self):
        self.line = 0
        self._indent = 0
        self._poms = False
        self._mgts = False
        self._ranges = False
        self._debug = False
        self._deps = []
        self._props = []

        self._color = os.isatty(1) or True
        self._nocolor = lambda x: str(x)
        self._c_name = self._nocolor if not self._color else lambda x: f"\033[1;33m{x}\033[0m"
        self._c_att = self._nocolor #if not self._color else lambda x: f"\033[1;32m{x}\033[0m"
        self._c_val = self._nocolor if not self._color else lambda x: f"\033[1;33m{x}\033[0m"

    def add_dep(self, dep):
        self._deps.append(dep)
        return self

    def add_prop(self, prop):
        self._props.append(prop)
        return self
    
    def set_poms(self, poms):
        self._poms = poms
        return self

    def set_mgts(self, mgts):
        self._mgts = mgts
        return self
    
    def set_ranges(self, ranges):
        self._ranges = ranges
        return self

    def set_debug(self, debug):
        self._debug = debug
        return self

    def trace_poms(self) -> bool:
        return self._poms

    def trace_dep(self, ga) -> bool:
        return self._mgts or ga in self._deps

    def trace_prop(self, prop) -> bool:
        return prop in self._props
    
    def trace_range(self, ga) -> bool:
        return self._ranges or ga in self._deps
    
    def enter(self, text: str | None = None, *args: str) -> bool:
        if text: self.trace(text, *args)
        self._indent += 1
        return True

    def exit(self, text: str | None = None, *args: str):
        self._indent -= 1
        if text: self.trace(text, *args)

    def trace(self, text: str, *args) -> bool:
        print(f"{self.line}: {'  ' * self._indent}{self.format(text, *args)}")
        self.line += 1
        return True
    
    def trace2(self, text: str, *args) -> bool:
        if not self._debug: return True
        print(f"{self.line}: {'  ' * self._indent}{self.format(text, *args)}")
        self.line += 1
        return True
    
    def format(self, text: str, *args) -> str:
        t = []
        if len(args) > 0 and args[0] != '':
            t.append(' ')
            t.append(self._c_name(args[0]))
        c = [ self._c_att, self._c_val ]
        s = [ ' ', ': ']
        p = 0
        for a in args[1:]:
            t.append(s[p])
            t.append(c[p](a))
            p = p + 1
            if p == len(c): p = 0
        return text + ':' + ''.join(t)
