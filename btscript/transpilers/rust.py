"""
btscript.transpilers.rust
~~~~~~~~~~~~~~~~~~~~~~~~~

Compiles BTScript ASTs into clean, executable Rust code.
Generates context interface traits (`<Tree>Context`), mock implementations,
and behavior tree constructor functions using Box<dyn BehaviourNode>.
"""

import re
from ..nodes import (
    TreeRoot, SubtreeNode, SequenceNode, SelectorNode, ParallelNode,
    ActionNode, ConditionNode, DecoratorNode
)


def to_snake_case(name: str) -> str:
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()


# ======================================================================
# Rust Stub Generator (Trait + Mock Context)
# ======================================================================

class RustStubTranspiler:
    """
    Generates a Rust trait defining all required action and condition signatures,
    along with a MockContext implementation for testing.
    """
    def __init__(self, ast):
        self.trees = ast if isinstance(ast, list) else [ast]
        self.ilevel = 0

    def indent(self) -> str:
        return self.ilevel * "    "

    def collect_signatures(self, node):
        actions = {}
        conditions = {}

        def walk(n):
            name = type(n).__name__
            if name in ("TreeRoot", "SequenceNode", "SelectorNode", "ParallelNode"):
                for child in n.children:
                    walk(child)
            elif name == "DecoratorNode":
                if n.child:
                    walk(n.child)
            elif name == "ActionNode":
                actions.setdefault(n.name, set()).add(len(n.args))
            elif name == "ConditionNode":
                conditions.setdefault(n.name, set()).add(len(n.args))

        for child in node.children:
            walk(child)
        return actions, conditions

    def _format_fn_params(self, arities: set) -> str:
        if not arities:
            return "&mut self"
        count = max(arities)
        if count == 0:
            return "&mut self"
        args = [f"arg{i+1}: f64" for i in range(count)]
        return "&mut self, " + ", ".join(args)

    def transpile_tree(self, tree: TreeRoot) -> str:
        actions, conditions = self.collect_signatures(tree)
        trait_name = f"{tree.name}Context"
        mock_name = f"Mock{tree.name}Context"

        code = f"// ======================================================================\n"
        code += f"// Context Trait & Mock for Tree '{tree.name}'\n"
        code += f"// ======================================================================\n\n"

        # Trait definition
        code += f"pub trait {trait_name} {{\n"
        self.ilevel = 1

        if conditions:
            code += f"{self.indent()}// Conditions\n"
            for cond_name in sorted(conditions.keys()):
                params = self._format_fn_params(conditions[cond_name])
                code += f"{self.indent()}fn {to_snake_case(cond_name)}({params}) -> bool;\n"

        if actions:
            code += f"{self.indent()}// Actions\n"
            for act_name in sorted(actions.keys()):
                params = self._format_fn_params(actions[act_name])
                code += f"{self.indent()}fn {to_snake_case(act_name)}({params}) -> Status;\n"

        code += "}\n\n"

        # Mock implementation struct
        code += f"pub struct {mock_name};\n\n"
        code += f"impl {trait_name} for {mock_name} {{\n"
        self.ilevel = 1

        for cond_name in sorted(conditions.keys()):
            params = self._format_fn_params(conditions[cond_name])
            code += f"{self.indent()}fn {to_snake_case(cond_name)}({params}) -> bool {{\n"
            code += f"{self.indent()}    println!(\"[Condition] {cond_name} -> true\");\n"
            code += f"{self.indent()}    true\n"
            code += f"{self.indent()}}}\n"

        for act_name in sorted(actions.keys()):
            params = self._format_fn_params(actions[act_name])
            code += f"{self.indent()}fn {to_snake_case(act_name)}({params}) -> Status {{\n"
            code += f"{self.indent()}    println!(\"[Action] {act_name} -> Success\");\n"
            code += f"{self.indent()}    Status::Success\n"
            code += f"{self.indent()}}}\n"

        code += "}\n"
        return code

    def transpile(self) -> str:
        return "\n\n".join(self.transpile_tree(t) for t in self.trees)


# ======================================================================
# Rust Tree Transpiler
# ======================================================================

class RustTranspiler:
    def __init__(self, ast, directive=None):
        self.ast = ast
        self.directive = directive or {}
        self.ilevel = 0

    def indent(self) -> str:
        return self.ilevel * "    "

    def format_arg(self, arg):
        if isinstance(arg, bool):
            return "true" if arg else "false"
        elif isinstance(arg, (int, float)):
            # Distinguish floats vs integers
            val_str = str(arg)
            if "." in val_str:
                return f"{val_str}f64"
            return f"{val_str}.0"
        elif isinstance(arg, str):
            if arg.startswith("@"):
                var_name = arg[1:]
                return f"*ctx.blackboard.get::<f64>(\"{var_name}\").unwrap_or(&0.0)"
            return f"\"{arg}\""
        return str(arg)

    def transpile(self) -> str:
        trees = self.ast if isinstance(self.ast, list) else [self.ast]
        code = "// ======================================================================\n"
        code += "// Auto-generated by BTScript Rust Transpiler\n"
        code += "// ======================================================================\n\n"
        code += "#![allow(dead_code)]\n"
        code += "#![allow(unused_imports)]\n\n"
        code += "use super::runtime::*;\n\n"

        code += "\n\n".join(self.visit(tree) for tree in trees)

        if self.directive.get("stub", True):
            code += "\n\n\n"
            code += RustStubTranspiler(trees).transpile()

        return code

    def visit(self, node) -> str:
        method = f"visit_{type(node).__name__}"
        return getattr(self, method)(node)

    def visit_TreeRoot(self, node: TreeRoot) -> str:
        fn_name = f"build_{to_snake_case(node.name)}"
        self.ilevel = 1
        body_nodes = ",\n".join(f"{self.indent()}{self.visit(child)}" for child in node.children)
        self.ilevel = 0

        # If tree has 1 top-level node (e.g. sequence), return it directly
        if len(node.children) == 1:
            child_code = self.visit(node.children[0])
            return (
                f"pub fn {fn_name}() -> Box<dyn BehaviourNode> {{\n"
                f"    {child_code}\n"
                f"}}"
            )
        else:
            return (
                f"pub fn {fn_name}() -> Box<dyn BehaviourNode> {{\n"
                f"    Box::new(Sequence::new(\n"
                f"        vec![\n{body_nodes}\n        ],\n"
                f"        false,\n"
                f"    ))\n"
                f"}}"
            )

    def visit_SequenceNode(self, node: SequenceNode) -> str:
        stateful = "true" if getattr(node, "memory_type", "stateless") == "stateful" else "false"
        self.ilevel += 2
        children = ",\n".join(f"{self.indent()}{self.visit(c)}" for c in node.children)
        self.ilevel -= 2
        return (
            f"Box::new(Sequence::new(\n"
            f"{self.indent()}    vec![\n{children}\n{self.indent()}    ],\n"
            f"{self.indent()}    {stateful},\n"
            f"{self.indent()}))"
        )

    def visit_SelectorNode(self, node: SelectorNode) -> str:
        stateful = "true" if getattr(node, "memory_type", "stateless") == "stateful" else "false"
        self.ilevel += 2
        children = ",\n".join(f"{self.indent()}{self.visit(c)}" for c in node.children)
        self.ilevel -= 2
        return (
            f"Box::new(Selector::new(\n"
            f"{self.indent()}    vec![\n{children}\n{self.indent()}    ],\n"
            f"{self.indent()}    {stateful},\n"
            f"{self.indent()}))"
        )

    def visit_ParallelNode(self, node: ParallelNode) -> str:
        stateful = "true" if getattr(node, "memory_type", "stateless") == "stateful" else "false"
        self.ilevel += 2
        children = ",\n".join(f"{self.indent()}{self.visit(c)}" for c in node.children)
        self.ilevel -= 2
        return (
            f"Box::new(Parallel::new(\n"
            f"{self.indent()}    vec![\n{children}\n{self.indent()}    ],\n"
            f"{self.indent()}    {stateful},\n"
            f"{self.indent()}))"
        )

    def visit_DecoratorNode(self, node: DecoratorNode) -> str:
        child_str = self.visit(node.child)
        prop = (getattr(node, "property", None) or getattr(node, "prop", "")).lower()

        if prop == "inverter":
            return f"Box::new(Invert::new({child_str}))"
        elif prop == "repeat":
            count = f"Some({int(node.args[0])})" if node.args else "None"
            return f"Box::new(Repeat::new({child_str}, {count}))"
        elif prop == "retry":
            count = f"Some({int(node.args[0])})" if node.args else "None"
            return f"Box::new(Retry::new({child_str}, {count}))"
        elif prop == "timeout":
            dur = float(node.args[0]) if node.args else 1.0
            return f"Box::new(Timeout::new({child_str}, {dur}))"
        elif prop == "delay":
            dur = float(node.args[0]) if node.args else 1.0
            return f"Box::new(Delay::new({child_str}, {dur}))"
        elif prop == "cooldown":
            dur = float(node.args[0]) if node.args else 1.0
            return f"Box::new(Cooldown::new({child_str}, {dur}))"
        elif prop == "force_success":
            return f"Box::new(ForceSuccess::new({child_str}))"
        elif prop == "force_failure":
            return f"Box::new(ForceFailure::new({child_str}))"
        return child_str

    def visit_ActionNode(self, node: ActionNode) -> str:
        args_str = ", ".join(self.format_arg(a) for a in node.args)
        snake_name = to_snake_case(node.name)
        if getattr(node, "output_var", None):
            return (
                f"Box::new(Action::new(|ctx, _dt| {{\n"
                f"{self.indent()}    let res = Status::Success;\n"
                f"{self.indent()}    write_bb(ctx, \"{node.output_var}\", res)\n"
                f"{self.indent()}}}))"
            )
        return (
            f"Box::new(Action::new(|_ctx, _dt| {{\n"
            f"{self.indent()}    println!(\"[Action] {snake_name}({args_str})\");\n"
            f"{self.indent()}    Status::Success\n"
            f"{self.indent()}}}))"
        )

    def visit_ConditionNode(self, node: ConditionNode) -> str:
        args_str = ", ".join(self.format_arg(a) for a in node.args)
        snake_name = to_snake_case(node.name)
        return (
            f"Box::new(Condition::new(|_ctx| {{\n"
            f"{self.indent()}    println!(\"[Condition] {snake_name}({args_str})\");\n"
            f"{self.indent()}    true\n"
            f"{self.indent()}}}))"
        )

    def visit_SubtreeNode(self, node: SubtreeNode) -> str:
        name = getattr(node, "name", None) or getattr(node, "tree_name", "")
        fn_name = f"build_{to_snake_case(name)}"
        return f"{fn_name}()"
