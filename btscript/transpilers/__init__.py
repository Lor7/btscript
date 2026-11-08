from .python import PyTranspiler, PyStubTranspiler
from .lua import LuaTranspiler, LuaStubTranspiler
from .rust import RustTranspiler, RustStubTranspiler
from .mermaid import MermaidTranspiler
from .json_tree import JSONTranspiler
from .xml_tree import XMLTranspiler
from .ascii_tree import AsciiTranspiler, render_ascii_tree

class Transpiler:
    TRANSPILERS = {
        "python": PyTranspiler,
        "lua": LuaTranspiler,
        "rust": RustTranspiler,
        "json": JSONTranspiler,
        "xml": XMLTranspiler,
        "mermaid": MermaidTranspiler,
        "ascii": AsciiTranspiler,
    }

    def __init__(self, ast, lang = "python", directive = None):
        self.ast = ast
        self.lang = lang
        self.directive = directive or {}

    def transpile(self) -> str:
        if self.lang not in self.TRANSPILERS:
            raise ValueError(f"Unsupported language: {self.lang}")

        transpiler_cls = self.TRANSPILERS[self.lang]
        if self.lang in ("python", "lua", "rust"):
            return transpiler_cls(self.ast, directive=self.directive).transpile()
        return transpiler_cls(self.ast).transpile()
