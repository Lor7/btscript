"""
BTScript - A lightweight Behavior Tree DSL.

Author: Lorenzo (Lor7)
License: MIT
"""

__author__ = "Lorenzo (Lor7)"
__license__ = "MIT"
__version__ = "0.1.0"

from .tokens import Token, TokenType
from .nodes import (
    ASTNode,
    TreeRoot,
    SequenceNode,
    SelectorNode,
    ParallelNode,
    ActionNode,
    ConditionNode,
    DecoratorNode,
    SubtreeNode,
)
from .lexer import Lexer, LexError
from .parser import Parser, ParseError
from .validator import Validator, SemanticError
from .transpilers import (
    Transpiler,
    PyTranspiler,
    PyStubTranspiler,
    LuaTranspiler,
    LuaStubTranspiler,
    MermaidTranspiler,
    JSONTranspiler,
    XMLTranspiler,
    AsciiTranspiler,
    render_ascii_tree,
)
from .runtimes.python.runtime import (
    Status,
    Node,
    Sequence,
    Selector,
    Parallel,
    Action,
    Condition,
    Decorator,
    Subtree,
    write_bb,
    get_bb,
)

__version__ = "0.1.0"
__all__ = [
    "Token",
    "TokenType",
    "ASTNode",
    "TreeRoot",
    "SequenceNode",
    "SelectorNode",
    "ParallelNode",
    "ActionNode",
    "ConditionNode",
    "DecoratorNode",
    "SubtreeNode",
    "Lexer",
    "LexError",
    "Parser",
    "ParseError",
    "Validator",
    "SemanticError",
    "Transpiler",
    "PyTranspiler",
    "PyStubTranspiler",
    "LuaTranspiler",
    "LuaStubTranspiler",
    "MermaidTranspiler",
    "JSONTranspiler",
    "XMLTranspiler",
    "AsciiTranspiler",
    "render_ascii_tree",
    "Status",
    "Node",
    "Sequence",
    "Selector",
    "Parallel",
    "Action",
    "Condition",
    "Decorator",
    "Subtree",
    "write_bb",
    "get_bb",
]
