"""
btscript.validator
~~~~~~~~~~~~~~~~~~

Semantic and dataflow validation for BTScript ASTs.

Responsibilities:
    - Structural integrity (composite child requirements, decorator validity)
    - Subtree cycle detection via depth-first graph traversal
    - Leaf arity validation & call-signature type inference
    - Dead-code analysis (unreachable siblings after force_success/force_failure)
    - Redundant decorator detection (e.g. double inversion)
    - Dataflow analysis (read-before-written warnings, unused variable warnings)
    - Rich source-mapped terminal diagnostics with caret underlines
"""

import os
from .nodes import (
    DecoratorNode, SequenceNode, SelectorNode, ParallelNode,
    ActionNode, ConditionNode, SubtreeNode, TreeRoot
)


class SemanticError(Exception):
    """Raised when semantic validation encounters fatal tree errors."""
    pass


class Validator:
    """Performs static analysis and semantic verification on parsed ASTs."""

    def __init__(self, ast, directive):
        self.ast = ast
        self.errors = []
        self.warnings = []

        # Signatures tracking: leaf_name -> argument count & inferred types
        self.signatures = {}
        self.sig_types = {}
        self.directive = directive
        self.known_tree_names = set()
        self._file_cache = {}

        # Subtree cycle detection call stack
        self.tree_call_graph = list()

        # Dataflow tracking
        self.tree_written_vars = {}
        self.tree_read_vars = set()

    def _get_file_line(self, file_path: str, line_no: int) -> str:
        if not file_path or not os.path.exists(file_path):
            return ""
        if file_path not in self._file_cache:
            try:
                with open(file_path, "r") as f:
                    self._file_cache[file_path] = f.read().splitlines()
            except Exception:
                return ""
        lines = self._file_cache[file_path]
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1]
        return ""

    def format_diagnostic(self, node, message: str, level: str = "Error") -> str:
        token = getattr(node, "token", None)
        source_file = getattr(node, "source_file", None)
        color = "\033[1;31m" if level == "Error" else "\033[1;33m"
        title = f"{level}" if level != "Error" else "Semantic Error"
        if token and source_file:
            line_no = token.line
            col = token.column
            length = getattr(token, "length", 1)
            code_line = self._get_file_line(source_file, line_no)
            gutter = f"{line_no:4d} | "
            caret_indent = " " * (len(gutter) + col - 1)
            caret = "^" * max(1, length)
            diag_msg = f"\n{color}{title}\033[0m in {source_file}:{line_no}:{col}:\n"
            diag_msg += f"{gutter}{code_line}\n"
            diag_msg += f"{caret_indent}{color}{caret}\033[0m\n"
            diag_msg += f"\033[1m{message}\033[0m"
            return diag_msg
        return f"{color}{title}:\033[0m {message}"

    def report_error(self, node, message: str):
        self.errors.append(self.format_diagnostic(node, message, level="Error"))
    
    def report_warning(self, node, message: str):
        warnings_enabled = self.directive.get("warnings", True) if self.directive else True
        if not warnings_enabled:
            return
        werror_enabled = self.directive.get("werror", False) if self.directive else False
        if werror_enabled:
            self.report_error(node, f"(treated as error) {message}")
        else:
            self.warnings.append(self.format_diagnostic(node, message, level="Warning"))

    def infer_types(self, arg : str) -> str:
        if arg.startswith('"') and arg.endswith('"'):
            return "STRING"
        if arg in ["none", "null", "nill", "undefined", "default"]:
            return "NONE"
        if arg in ["true", "false"]:
            return "BOOLEAN"
        if arg.startswith("$"):
            return "VARIABLE"
        try:
            float(arg)
            return "NUMBER"
        except ValueError:
            pass
        return "IDENT"

    def validate(self):
        trees = self.ast if isinstance(self.ast, list) else [self.ast]
        self.trees_by_name = {tree.name: tree for tree in trees}
        # Check duplicate tree names
        for tree in trees:
            if tree.name in self.known_tree_names:
                self.report_error(tree, f"Duplicate tree declaration '{tree.name}'. Tree names must be unique.")
            else:
                self.known_tree_names.add(tree.name)

        for tree in trees:
            self.tree_call_graph = [tree.name]
            self.visit(tree)
            self.tree_call_graph.clear()

        if self.errors:
            raise SemanticError("\n".join(self.errors))
    
    def visit(self, node):
        method = f"check_{type(node).__name__}"
        getattr(self, method, lambda n: None)(node)
    
    def check_TreeRoot(self, node):
        if not node.children:
            self.report_error(node, f"Tree '{node.name}' has no root nodes")
        
        params = [p.split("=")[0].strip() for p in getattr(node, "params", [])]
        defaults = list(getattr(node, "blackboard", {}).keys())
        available_vars = set(params + defaults)

        self.tree_written_vars = {p: node for p in (params + defaults)}
        self.tree_read_vars = set()

        for child in node.children:
            self._check_dataflow(child, available_vars)
            self.visit(child)

        for var_name, def_node in self.tree_written_vars.items():
            if var_name not in self.tree_read_vars:
                self.report_warning(def_node, f"Variable '{var_name}' is declared/written but never read (unused)")

    def check_DecoratorNode(self, node):
        if not node.child:
            self.report_error(node, f"Decorator with property '{node.property}' has no child node")
        valid_decorators = {"inverter", "retry", "repeat", "force_success", "force_failure", "timeout", "delay", "cooldown"}
        if node.property not in valid_decorators:
            self.report_error(node, f"Decorator has unknown property: '{node.property}'")
        if node.child:
            if node.property == "inverter" and isinstance(node.child, DecoratorNode):
                if node.child.property == "inverter":
                    self.report_warning(node, "Double inversion is redundant")
                elif node.child.property == "force_success":
                    self.report_warning(node, "Inverting 'force_success' is equal to 'force_failure'")
                elif node.child.property == "force_failure":
                    self.report_warning(node, "Inverting 'force_failure' is equal to 'force_success'")
            self.visit(node.child)

    def check_SequenceNode(self, node):
        if not node.children:
            self.report_error(node, "SequenceNode cannot be empty")
        for i, child in enumerate(node.children):
            if (i < len(node.children) - 1) and isinstance(child, DecoratorNode) and child.property == "force_failure":
                dead_names = [getattr(c, "name", type(c).__name__) for c in node.children[i + 1:]]
                self.report_warning(child, f"Unreachable nodes in Sequence after 'force_failure': {', '.join(dead_names)}")
            self.visit(child)

    def check_SelectorNode(self, node):
        if not node.children:
            self.report_error(node, "SelectorNode cannot be empty")
        for i, child in enumerate(node.children):
            if (i < len(node.children) - 1) and isinstance(child, DecoratorNode) and child.property == "force_success":
                dead_names = [getattr(c, "name", type(c).__name__) for c in node.children[i + 1:]]
                self.report_warning(child, f"Unreachable nodes in Selector after 'force_success': {', '.join(dead_names)}")
            self.visit(child)

    def check_ParallelNode(self, node):
        if not node.children:
            self.report_error(node, "ParallelNode cannot be empty")
        for child in node.children:
            self.visit(child)

    def _check_leaf(self, node_type_name: str, node):
        # Structural checks (node name, existence) always run.
        # Directives only toggle arity and signature type checks.
        arg_count = len(node.args)
        actual_types = [self.infer_types(arg) for arg in node.args]

        allow_overloading = self.directive.get("check_arity", True) if self.directive else True
        enforce_types = self.directive.get("check_types", True) if self.directive else True

        # Store first seen arity for this leaf name
        if node.name not in self.signatures:
            self.signatures[node.name] = arg_count
            self.sig_types[node.name] = {}

        # --- RULE 1: ARITY CHECKING ---
        # With @disable: arity, overloading is forbidden: all calls must use the exact same argument count.
        # With @enable: arity (default), calls can overload with different argument counts.
        if not allow_overloading:
            expected_count = self.signatures[node.name]
            if arg_count != expected_count:
                self.report_error(
                    node,
                    f"{node_type_name} '{node.name}' called with {arg_count} argument(s), "
                    f"but was defined with {expected_count} argument(s) (overloading is disabled)"
                )
                return

        # --- RULE 2: TYPE SIGNATURE INFERENCE ---
        # With @enable: types (default), calls sharing the same argument count must pass matching types
        # (NUMBER, STRING, BOOLEAN). Blackboard variables ($var) and identifiers bypass literal checks.
        # With @disable: types, type mismatches are ignored.
        if enforce_types:
            if arg_count in self.sig_types[node.name]:
                expected_types = self.sig_types[node.name][arg_count]
                for idx, (expected, actual) in enumerate(zip(expected_types, actual_types)):
                    # Allow variables and identifiers to match any expected type
                    if expected not in ("IDENT", "VARIABLE") and actual not in ("IDENT", "VARIABLE") and expected != actual:
                        self.report_error(
                            node,
                            f"{node_type_name} '{node.name}' (arity {arg_count}) argument #{idx + 1} type mismatch: "
                            f"expected {expected}, got {actual}"
                        )
            else:
                # Record this overload's parameter types
                self.sig_types[node.name][arg_count] = actual_types
        else:
            self.sig_types[node.name][arg_count] = actual_types

    def check_ActionNode(self, node):
        self._check_leaf("Action", node)

    def check_ConditionNode(self, node):
        self._check_leaf("Condition", node)

    def check_SubtreeNode(self, node):
        # 1. Verify target subtree exists in known trees
        if node.name not in self.known_tree_names:
            self.report_error(
                node,
                f"Unknown subtree '{node.name}'. Perhaps you forgot to import it?"
            )
            return

        # 2. Cycle detection: check if this subtree is already in our call stack
        if node.name in self.tree_call_graph:
            cycle_path = " -> ".join(self.tree_call_graph + [node.name])
            self.report_error(node, f"Circular subtree invocation detected: {cycle_path}")
            return

        # 3. Parameter arity verification (required vs optional with defaults)
        target_tree = self.trees_by_name.get(node.name)
        if target_tree:
            target_params = getattr(target_tree, "params", [])
            required_params = [p for p in target_params if "=" not in p]
            call_args = getattr(node, "args", [])
            if len(call_args) < len(required_params) or len(call_args) > len(target_params):
                expected_str = f"{len(target_params)}" if len(required_params) == len(target_params) else f"{len(required_params)} to {len(target_params)}"
                self.report_error(
                    node,
                    f"Subtree '{node.name}' expects {expected_str} argument(s), but got {len(call_args)}"
                )
                return

            # 4. Push call frame, traverse target tree, then pop frame
            self.tree_call_graph.append(node.name)
            for child in target_tree.children:
                self.visit(child)
            self.tree_call_graph.pop()

    def _check_dataflow(self, node, available_vars: set):
        # Pass scope down through decorators
        if isinstance(node, DecoratorNode):
            if node.child:
                self._check_dataflow(node.child, available_vars)

        # Sequence dataflow: writes from earlier steps are available to later steps
        elif isinstance(node, SequenceNode):
            for child in node.children:
                self._check_dataflow(child, available_vars)

        # Selector and Parallel branches fork scope independently (isolated branches)
        elif isinstance(node, (SelectorNode, ParallelNode)):
            for child in node.children:
                self._check_dataflow(child, set(available_vars))

        # Leaf tasks: track read and written variables
        elif isinstance(node, (ActionNode, ConditionNode)):
            for arg in node.args:
                if arg.startswith("$"):
                    var_name = arg[1:]
                    self.tree_read_vars.add(var_name)
                    # Warn if read before being initialized or declared
                    if var_name not in available_vars:
                        self.report_warning(node, f"Blackboard variable '${var_name}' is read before being written")
                elif arg in self.tree_written_vars:
                    self.tree_read_vars.add(arg)

            # Register output variable written to blackboard
            if getattr(node, "output_var", None):
                var_name = node.output_var
                available_vars.add(var_name)
                self.tree_written_vars[var_name] = node

        # Subtree invocation arguments dataflow
        elif isinstance(node, SubtreeNode):
            for arg in getattr(node, "args", []):
                if arg.startswith("$"):
                    var_name = arg[1:]
                    self.tree_read_vars.add(var_name)
                    if var_name not in available_vars:
                        self.report_warning(node, f"Blackboard variable '${var_name}' is read before being written")
                elif arg in self.tree_written_vars:
                    self.tree_read_vars.add(arg)
