import os

TRACER: 'Tracer | None' = None

class Tracer:
    def __init__(self):
        self.line = 0
        self._poms = False
        self._ranges = False
        self._debug = False
        self._deps = []
        self._deps_all = False
        self._props = []
        self._props_all = False
        self._ctx = None

        self.set_color(os.isatty(1))
    
    def add_dep(self, dep) -> 'Tracer':
        self._deps.append(dep)
        if dep == '*': self._deps_all = True
        return self

    def add_prop(self, prop) -> 'Tracer':
        self._props.append(prop)
        if prop == '*': self._props_all = True
        return self
    
    def set_poms(self, poms) -> 'Tracer':
        self._poms = poms
        return self

    def set_ranges(self, ranges) -> 'Tracer':
        self._ranges = ranges
        return self

    def set_debug(self, debug) -> 'Tracer':
        self._debug = debug
        return self

    def set_color(self, color) -> 'Tracer':
        self._color = color
        self._nocolor = lambda x: str(x)
        self._c_name = self._nocolor if not self._color else lambda x: f"\033[1;33m{x}\033[0m"
        self._c_att = self._nocolor #if not self._color else lambda x: f"\033[1;32m{x}\033[0m"
        self._c_val = self._nocolor if not self._color else lambda x: f"\033[1;33m{x}\033[0m"
        return self

    def trace_poms(self) -> bool:
        return self._poms

    def trace_dep(self, ga) -> bool:
        return self._deps_all or ga in self._deps

    def trace_prop(self, prop) -> bool:
        return self._props_all or prop in self._props
    
    def trace_range(self, ga) -> bool:
        return self._ranges or ga in self._deps
    
    def trace(self, text: str, *args) -> bool:
        if self._ctx is not None:
            print()
            print(f"{self.line}: {self._ctx}")
            self._ctx = None
            self.line += 1
        if text != '':
            print(f"{self.line}: {self.format(text, *args)}")
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

    def set_ctx(self, text: str, *args):
        self._ctx = self.format(text, *args)
