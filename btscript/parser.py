"""
btscript.parser
~~~~~~~~~~~~~~~

Recursive-descent AST parser for BTScript.
Handles compiler directives, tree structure extraction, syntactic sugar desugaring
(chained fallbacks, prefix modifiers, inline preconditions), and multi-file inclusion.
"""

import os
from .lexer import Lexer
from .tokens import Token, TokenType
from .nodes import (
    TreeRoot, SubtreeNode, SequenceNode, SelectorNode, ParallelNode,
    ActionNode, ConditionNode, DecoratorNode
)


class Parser:
    """Parses a BTScript source file into an Abstract Syntax Tree (AST)."""
    
    def __init__(self, file_path, imported_files=None):
        self.file_path = os.path.abspath(file_path)
        self.tree = None
        with open(file_path, 'r') as file:
            self.content = file.read()
        self.lexer = Lexer(self.content)
        self.tokens = self.lexer.tokenize()
        self.cursor = 0

        # Prevent circular file inclusions
        self.imported_files = imported_files if imported_files is not None else set()
        self.imported_files.add(self.file_path)
        self.imported_trees = []

        self.bread = {}
        self.bwrite = {}

    # ==================================================================
    # Token Stream Navigation
    # ==================================================================

    def current(self) -> Token:
        return self.tokens[self.cursor]

    def advance(self) -> None:
        self.cursor += 1

    def match(self, expected_type, expected_value=None) -> bool:
        tok = self.current()
        type_matches = (tok.type == expected_type or tok.type.value == expected_type)
        if not type_matches:
            return False
        if expected_value is not None:
            return tok.value == expected_value
        return True

    def format_error(self, token: Token, message: str) -> str:
        lines = self.content.splitlines()
        if 1 <= token.line <= len(lines):
            code_line = lines[token.line - 1]
        else:
            code_line = ""
        col = token.column
        length = token.length
        gutter = f"{token.line:4d} | "
        caret_indent = " " * (len(gutter) + col - 1)
        caret = "^" * max(1, length)
        errormsg = f"\n\033[1;31mError\033[0m in {self.file_path}:{token.line}:{col}:\n"
        errormsg += f"{gutter}{code_line}\n"
        errormsg += f"{caret_indent}\033[1;31m{caret}\033[0m\n"
        errormsg += f"\033[1m{message}\033[0m\n"
        return errormsg

    def error(self, token: Token, message: str):
        raise Exception(self.format_error(token, message))

    def consume(self, expected_type, expected_value=None) -> Token:
        tok = self.current()
        if not self.match(expected_type, expected_value):
            exp = expected_value if expected_value is not None else expected_type
            self.error(tok, f"Expected '{exp}', got '{tok.value}'")
        self.advance()
        return tok

    def parse_directives(self) -> dict:
        directives = {
            "check_arity": True,
            "check_types": True,
            "warnings": True,
            "werror": False,
            "stub": True,
            "lang": None,
            "imports": []
        }
        while self.match("@"):
            self.consume("@")
            cmd_tok = self.current()
            if cmd_tok.type not in (TokenType.IDENT, TokenType.KEYWORD):
                self.error(cmd_tok, f"Expected directive command after '@', got '{cmd_tok.value}'")
            self.advance()
            cmd = cmd_tok.value.lower()
            self.consume(":")
            
            target_tok = self.current()
            if target_tok.type not in (TokenType.STRING, TokenType.IDENT):
                self.error(target_tok, f"Expected file path or identifier after '@{cmd}:', got '{target_tok.value}'")
            self.advance()
            target = target_tok.value

            if cmd == "disable":
                if target in ("arity", "arities"):
                    directives["check_arity"] = False
                elif target in ("types", "type", "sig"):
                    directives["check_types"] = False
                elif target in ("warnings", "warning"):
                    directives["warnings"] = False
                elif target in ("werror", "warnings-as-errors"):
                    directives["werror"] = False
                elif target in ("stub", "stubs"):
                    directives["stub"] = False
                else:
                    self.error(target_tok, f"Unknown target '{target}' for '@disable'. Valid options: arity, types, warnings, werror, stub")
            elif cmd == "enable":
                if target in ("arity", "arities"):
                    directives["check_arity"] = True
                elif target in ("types", "type", "sig"):
                    directives["check_types"] = True
                elif target in ("warnings", "warning"):
                    directives["warnings"] = True
                elif target in ("werror", "warnings-as-errors"):
                    directives["werror"] = True
                elif target in ("stub", "stubs"):
                    directives["stub"] = True
                else:
                    self.error(target_tok, f"Unknown target '{target}' for '@enable'. Valid options: arity, types, warnings, werror, stub")
            elif cmd == "lang":
                valid_langs = {"python", "lua", "json", "xml", "mermaid"}
                if target.lower() not in valid_langs:
                    self.error(target_tok, f"Unsupported language '{target}' in '@lang'. Valid options: {', '.join(sorted(valid_langs))}")
                directives["lang"] = target.lower()
            elif cmd == "import":
                if not target.endswith(".tree"):
                    target += ".tree"
                import_file_path = os.path.abspath(os.path.join(os.path.dirname(self.file_path), target))
                directives["imports"].append(target)
                if not os.path.exists(import_file_path):
                    self.error(target_tok, f"Imported file '{target}' not found at '{import_file_path}'")
                if import_file_path not in self.imported_files:
                    sub_parser = Parser(import_file_path, imported_files=self.imported_files)
                    sub_trees, _ = sub_parser.parse_file()
                    self.imported_trees.extend(sub_trees)
            else:
                self.error(cmd_tok, f"Unknown directive '@{cmd}'. Valid directives: @enable, @disable, @lang, @import")
                
        return directives

    def parse_file(self):
        directives = self.parse_directives()
        trees = []
        while not self.match("EOF"):
            trees.append(self.parse_tree())
        self.consume("EOF")
        # Imported trees are registered alongside current file's trees
        all_trees = self.imported_trees + trees
        return all_trees, directives

    def parse_tree(self) -> TreeRoot:
        tree_tok = self.consume("KEYWORD", expected_value = "tree")
        name_tok = self.consume("IDENT")
        params = []
        if self.match("("):
            self.consume("(")
            while not self.match(")"):
                p_tok = self.consume("IDENT")
                param_str = p_tok.value
                if self.match("="):
                    self.consume("=")
                    val_tok = self.current()
                    if val_tok.type == TokenType.STRING or val_tok.value == "STRING":
                        param_str += f'="{val_tok.value}"'
                    else:
                        param_str += f"={val_tok.value}"
                    self.advance()
                params.append(param_str)
                if self.match(","):
                    self.consume(",")
                else:
                    break
            self.consume(")")
        self.consume("{")

        default_bb = {}
        if self.match("KEYWORD", expected_value = "blackboard"):
            self.consume("KEYWORD", expected_value = "blackboard")
            self.consume("{")
            while not self.match("}"):
                self.consume("$")
                var_tok = self.consume("IDENT")
                self.consume("=")
                is_negative = False
                if self.match("-"):
                    self.consume("-")
                    is_negative = True
                val_tok = self.current()
                if val_tok.type in (TokenType.NUMBER, TokenType.STRING, TokenType.BOOLEAN, TokenType.NONE):
                    if val_tok.type == TokenType.STRING:
                        val = f'"{val_tok.value}"'
                    elif is_negative and val_tok.type == TokenType.NUMBER:
                        val = f"-{val_tok.value}"
                    else:
                        val = val_tok.value
                    default_bb[var_tok.value] = val
                    self.bwrite[var_tok.value] = var_tok
                    self.advance()
                else:
                    self.error(val_tok, f"Expected literal value for blackboard variable, got '{val_tok.value}'")
                if self.match(","):
                    self.consume(",")
            self.consume("}")
        
        children = []
        while not self.match("}"):
            children.append(self.parse_node())
        self.consume("}")
        return TreeRoot(name = name_tok.value,
                        children = children,
                        params = params,
                        blackboard = default_bb,
                        token = name_tok,
                        source_file = self.file_path
                        )

    def parse_node(self):
        first_node = self.parse_single_node()
        if not self.match("|"):
            return first_node
        pipe_tok = self.current()
        branches = [first_node]
        while self.match("|"):
            self.consume("|")
            branches.append(self.parse_single_node())
        return SelectorNode(children = branches,
                            token = pipe_tok,
                            source_file = self.file_path,
                            memory_type = "stateless"
                            )

    def parse_single_node(self):
        memory_type = "stateless"
        if self.match("KEYWORD", expected_value = "stateful"):
            self.consume("KEYWORD", expected_value = "stateful")
            memory_type = "stateful"
        elif self.match("KEYWORD", expected_value = "stateless"):
            self.consume("KEYWORD", expected_value = "stateless")
            memory_type = "stateless"

        if self.match("KEYWORD", expected_value = "sequence"):
            return self.parse_composite(SequenceNode, memory_type)
        elif self.match("KEYWORD", expected_value = "selector"):
            return self.parse_composite(SelectorNode, memory_type)
        elif self.match("KEYWORD", expected_value = "parallel"):
            return self.parse_composite(ParallelNode, memory_type)
        elif memory_type == "stateful":
            self.error(self.current(), f"'stateful' can only precede composite nodes (sequence, selector, parallel), got '{self.current().value}'")
        elif self.match("KEYWORD", expected_value = "action"):
            return self.parse_leaf(ActionNode)
        elif self.match("KEYWORD", expected_value = "condition"):
            return self.parse_leaf(ConditionNode)
        elif self.match("KEYWORD", expected_value = "decorator"):
            return self.parse_decorator()
        elif self.match("KEYWORD", expected_value = "subtree"):
            return self.parse_subtree()
        elif self.current().type in ("!", "-", "+", "/", "\\") or \
             (self.current().type in (TokenType.IDENT, TokenType.KEYWORD) and self.current().value == "not"):
            # Sugar prefix placed before 'action:' or 'condition:'
            return self.parse_leaf(None)
        elif (self.current().type == TokenType.IDENT or self.current().type.value == "IDENT") and \
             self.cursor + 1 < len(self.tokens) and self.tokens[self.cursor + 1].value == "(":
            # Bare leaf call (e.g. step2() in a chain) defaults to ActionNode
            return self.parse_leaf(ActionNode)
        else:
            self.error(self.current(), f"Unexpected token '{self.current().value}' when parsing node")

    def parse_subtree(self) -> SubtreeNode:
        subtree_tok = self.consume("KEYWORD", expected_value = "subtree")
        self.consume(":")
        tree_name_tok = self.consume("IDENT")
        subtree_args = []
        if self.match("("):
            self.consume("(")
            while not self.match(")"):
                arg_tok = self.current()
                if self.match("$"):
                    self.consume("$")
                    var_tok = self.consume("IDENT")
                    subtree_args.append(f"${var_tok.value}")
                elif arg_tok.type in (TokenType.IDENT, TokenType.NUMBER, TokenType.STRING, TokenType.BOOLEAN, TokenType.KEYWORD) or \
                   arg_tok.type.value in ("IDENT", "NUMBER", "STRING", "BOOLEAN", "NONE"):
                    if arg_tok.type == TokenType.STRING or arg_tok.value == "STRING":
                        subtree_args.append(f'"{arg_tok.value}"')
                    else:
                        subtree_args.append(arg_tok.value)
                    self.advance()
                else:
                    self.error(arg_tok, f"Expected subtree argument, got '{arg_tok.value}'")
                if self.match(","):
                    self.consume(",")
                else:
                    break
            self.consume(")")
        return SubtreeNode(name = tree_name_tok.value,
                           args = subtree_args,
                           token = tree_name_tok,
                           source_file = self.file_path
                           )
    
    def parse_decorator(self) -> DecoratorNode:
        dec_tok = self.consume("KEYWORD", expected_value = "decorator")
        self.consume(":")
        property_tok = self.consume("IDENT")

        decorator_args = []
        if self.match("("):
            self.consume("(")
            decorator_args.append(self.consume("NUMBER").value)
            self.consume(")")
        self.consume("{")
        child_node = self.parse_node()
        self.consume("}")
        return DecoratorNode(property = property_tok.value,
                            child = child_node,
                            args  =  decorator_args,
                            token = property_tok,
                            source_file = self.file_path
                            )
    
    def parse_leaf(self, leaf_cls = None):
        # Collect prefix syntactic sugar modifiers (can appear before 'action' or after 'action:')
        modifiers = []
        def collect_modifiers():
            while True:
                if self.match("!"):
                    m_tok = self.consume("!")
                    modifiers.append(("inverter", None, m_tok))
                elif self.match("KEYWORD", expected_value = "not") or \
                    (self.current().type in [TokenType.IDENT, TokenType.KEYWORD] and self.current().value == "not"):
                    m_tok = self.current()
                    self.advance()
                    modifiers.append(("inverter", None, m_tok))
                elif self.match("/"):
                    m_tok = self.consume("/")
                    modifiers.append(("force_success", None, m_tok))
                elif self.match("\\"):
                    m_tok = self.consume("\\")
                    modifiers.append(("force_failure", None, m_tok))
                elif self.match("+"):
                    m_tok = self.consume("+")
                    modifiers.append(("force_success", None, m_tok))
                elif self.match("-"):
                    m_tok = self.consume("-")
                    if self.match("-"): # double minus: '--' for retry
                        self.consume("-")
                        count_tok = self.consume("NUMBER")
                        modifiers.append(("retry", count_tok.value, m_tok))
                    else: # single minus: '-' for repeat
                        count_tok = self.consume("NUMBER")
                        modifiers.append(("repeat", count_tok.value, m_tok))
                else:
                    break

        collect_modifiers()

        if leaf_cls is None:
            if self.match("KEYWORD", expected_value = "action"):
                leaf_cls = ActionNode
            elif self.match("KEYWORD", expected_value = "condition"):
                leaf_cls = ConditionNode
            else:
                self.error(self.current(), f"Expected 'action' or 'condition' after prefix modifier, got '{self.current().value}'")

            kw_tok = self.consume("KEYWORD")
            self.consume(":")
        else:
            if self.match("KEYWORD", expected_value = "action") or self.match("KEYWORD", expected_value = "condition"):
                kw_tok = self.consume("KEYWORD")
                self.consume(":")

        # Modifiers can also appear after the colon (e.g. action: !test())
        collect_modifiers()

        ident_tok = self.consume("IDENT")
        self.consume("(")
        args = []
        if not self.match(")"):
            while True:
                arg_tok = self.current()
                if self.match("$"):
                    self.consume("$")
                    var_tok = self.consume("IDENT")
                    var_name = var_tok.value
                    self.bread[var_name] = var_tok
                    args.append(f"${var_name}")
                elif arg_tok.type in [
                                    TokenType.IDENT,
                                    TokenType.NUMBER,
                                    TokenType.STRING,
                                    TokenType.BOOLEAN,
                                    TokenType.NONE
                                    ] or \
                arg_tok.type.value in [
                                    "IDENT",
                                    "NUMBER",
                                    "STRING",
                                    "BOOLEAN",
                                    "NONE",
                                    ]:
                    if arg_tok.type == TokenType.STRING or arg_tok.value == "STRING":
                        args.append(f'"{arg_tok.value}"')
                    else:
                        args.append(arg_tok.value)
                    self.advance()
                else:
                    self.error(arg_tok, f"Expected argument, got '{arg_tok.value}'")
                    
                if self.match(","):
                    self.consume(",")
                else:
                    break
        self.consume(")")

        # Check for blackboard write arrow (e.g. -> $target)
        output_var = None
        if self.match("->"):
            self.consume("->")
            self.consume("$")
            var_tok = self.consume("IDENT")
            output_var = var_tok.value
            self.bwrite[output_var] = var_tok

        # Instantiate leaf node (Action or Condition)
        current_node = leaf_cls(name = ident_tok.value,
                            args = args,
                            token = ident_tok,
                            source_file = self.file_path,
                            output_var = output_var
                            )

        # Wrap node inside accumulated prefix decorators from inside out
        for prop, count, m_tok in reversed(modifiers):
            d_args = [count] if count is not None else []
            current_node = DecoratorNode(property = prop,
                                        child = current_node,
                                        args = d_args,
                                        token = m_tok,
                                        source_file = self.file_path
                                        )

        return current_node

    def parse_composite(self, composite_cls, memory_type: str = "stateless"):
        kw_tok = self.consume("KEYWORD")
        children = []

        # Inline preconditions [cond1(), cond2()] desugar into leading child conditions
        if self.match("["):
            self.consume("[")
            while not self.match("]"):
                children.append(self.parse_leaf(leaf_cls = ConditionNode))
                if self.match(","):
                    self.consume(",")
            self.consume("]")
                
        # Parse nested child nodes within curly braces
        self.consume("{")
        while not self.match("}"):
            children.append(self.parse_node())
        self.consume("}")
        return composite_cls(children = children,
                            token = kw_tok,
                            source_file = self.file_path,
                            memory_type = memory_type
                            )