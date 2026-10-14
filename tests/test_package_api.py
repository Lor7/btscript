import pytest
import btscript
from btscript import (
    Lexer, LexError, Parser, ParseError, Validator, SemanticError,
    Transpiler, PyTranspiler, LuaTranspiler,
    JSONTranspiler, XMLTranspiler, MermaidTranspiler, AsciiTranspiler,
    Status, TreeRoot, SequenceNode, ActionNode
)

def test_btscript_package_exports():
    assert btscript.__version__ == "0.1.0"
    assert Lexer is not None
    assert LexError is not None
    assert Parser is not None
    assert ParseError is not None
    assert Validator is not None
    assert SemanticError is not None
    assert Transpiler is not None
    assert Status.SUCCESS.value == "SUCCESS"

def test_btscript_e2e_via_package(tmp_path):
    tree_file = tmp_path / "test.tree"
    tree_file.write_text("""
    tree Main {
        sequence {
            action: doWork()
        }
    }
    """)

    p = Parser(str(tree_file))
    ast, directives = p.parse_file()
    assert len(ast) == 1
    assert ast[0].name == "Main"

    v = Validator(ast, directives)
    v.validate()
    assert len(v.errors) == 0

    t = Transpiler(ast, "python", directives)
    code = t.transpile()
    assert "class MainBehaviorTree:" in code
    assert "Auto generated code from BTScript" in code
