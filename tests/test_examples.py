"""
tests/test_examples.py
Verifies that all tutorial and walkthrough examples in examples/
parse, validate, and transpile without errors.
"""

from pathlib import Path
from btscript.parser import Parser
from btscript.validator import Validator
from btscript.transpilers import Transpiler


def test_all_examples_validate_and_transpile():
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    example_files = list(examples_dir.rglob("*.tree"))
    assert len(example_files) >= 6

    for tree_file in example_files:
        parser = Parser(str(tree_file))
        ast, directives = parser.parse_file()
        assert ast is not None

        validator = Validator(ast, directives)
        validator.validate()
        assert len(validator.errors) == 0

        # Transpile to Python, Lua, and Rust
        py_code = Transpiler(ast, lang="python", directive=directives).transpile()
        assert len(py_code) > 0

        lua_code = Transpiler(ast, lang="lua", directive=directives).transpile()
        assert len(lua_code) > 0

        rust_code = Transpiler(ast, lang="rust", directive=directives).transpile()
        assert len(rust_code) > 0
