"""
btscript.transpilers.python
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Compiles BTScript ASTs into clean, executable Python class hierarchies.
Generates context interface stubs (`TreeContext`), mock context factories,
blackboard accessors, and behavior tree constructor functions.
"""

from ..nodes import (
    TreeRoot, SubtreeNode, SequenceNode, SelectorNode, ParallelNode,
    ActionNode, ConditionNode, DecoratorNode
)


class PyStubTranspiler:
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

    def _format_params(self, arities: set) -> str:
        if len(arities) > 1:
            return "self, *args"
        count = next(iter(arities))
        if count == 0:
            return "self"
        args = [f"arg{i+1}" for i in range(count)]
        return "self, " + ", ".join(args)

    def transpile_tree(self, tree: TreeRoot) -> str:
        actions, conditions = self.collect_signatures(tree)
        class_name = f"{tree.name}ContextStub"

        self.ilevel = 0
        code = f"# Context Stub for Tree '{tree.name}'\n"
        code += f"from runtime import Status\n\n"
        code += f"class {class_name}:\n"
        self.ilevel = 1
        code += f"{self.indent()}\"\"\"\n"
        code += f"{self.indent()}Context interface for Tree '{tree.name}'.\n"
        code += f"{self.indent()}Supports method overriding, function pointer assignment, and constructor binding:\n"
        code += f"{self.indent()}    ctx = {class_name}()\n"
        code += f"{self.indent()}    ctx.actionName = my_func\n"
        code += f"{self.indent()}\"\"\"\n"
        code += f"{self.indent()}def __init__(self, **bindings):\n"
        self.ilevel = 2
        code += f"{self.indent()}for name, func in bindings.items():\n"
        self.ilevel = 3
        code += f"{self.indent()}setattr(self, name, func)\n\n"

        self.ilevel = 1
        code += f"{self.indent()}# --- CONDITIONS (Expected: bool) ---\n"
        for cond_name in sorted(conditions.keys()):
            params = self._format_params(conditions[cond_name])
            code += f"{self.indent()}def {cond_name}({params}) -> bool:\n"
            self.ilevel = 2
            code += f"{self.indent()}raise NotImplementedError(\"Context method '{cond_name}' not implemented or assigned.\")\n\n"
            self.ilevel = 1

        code += f"{self.indent()}# --- ACTIONS (Expected: Status or bool) ---\n"
        for act_name in sorted(actions.keys()):
            params = self._format_params(actions[act_name])
            code += f"{self.indent()}def {act_name}({params}) -> Status:\n"
            self.ilevel = 2
            code += f"{self.indent()}raise NotImplementedError(\"Context method '{act_name}' not implemented or assigned.\")\n\n"
            self.ilevel = 1

        code += f"{self.indent()}@classmethod\n"
        code += f"{self.indent()}def create_mock(cls, default_status=Status.SUCCESS):\n"
        self.ilevel = 2
        code += f"{self.indent()}\"\"\"Creates an in-memory mock context where conditions return True and actions return default_status.\"\"\"\n"
        code += f"{self.indent()}stub = cls()\n"
        for cond_name in sorted(conditions.keys()):
            code += f"{self.indent()}stub.{cond_name} = lambda *args: True\n"
        for act_name in sorted(actions.keys()):
            code += f"{self.indent()}stub.{act_name} = lambda *args: default_status\n"
        code += f"{self.indent()}return stub\n"

        return code

    def transpile(self) -> str:
        return "\n\n".join(self.transpile_tree(t) for t in self.trees)


class PyTranspiler:
    def __init__(self, ast, directive = None):
        self.ast = ast
        self.directive = directive or {}
        self.ilevel = 0
        self.imports_done = False
    
    def indent(self) -> str:
        return self.ilevel * "\t"
    
    def transpile(self) -> str:
        trees = self.ast if isinstance(self.ast, list) else [self.ast]
        code = "\n\n".join(self.visit(tree) for tree in trees)
        if self.directive.get("stub", True):
            code += "\n\n\n# ======================================================================\n"
            code += "# Context Stubs\n"
            code += "# ======================================================================\n\n"
            code += PyStubTranspiler(trees).transpile()
        return code

    def visit(self, node) -> str:
        method = f"visit_{type(node).__name__}"
        return getattr(self, method)(node)
    
    def visit_ActionNode(self, node: ActionNode) -> str:
        args_str = ", ".join(self.format_arg(a) for a in node.args)
        if getattr(node, "output_var", None):
            return f"Action(lambda ctx: write_bb(ctx, '{node.output_var}', ctx.{node.name}({args_str})))"    
        return f"Action(lambda ctx: ctx.{node.name}({args_str}))"
    
    def visit_ConditionNode(self, node: ConditionNode) -> str:
        args_str = ", ".join(self.format_arg(a) for a in node.args)
        return f"Condition(lambda ctx: ctx.{node.name}({args_str}))"

    def visitComposite(self, class_name: str, children, memory_type: str = "stateless") -> str:
        self.ilevel += 1
        child_strings = [f"{self.indent()}{self.visit(child)}" for child in children]
        child_formatted = ",\n".join(child_strings)
        self.ilevel -= 1
        mem_arg = f', memory="{memory_type}"' if memory_type == "stateful" else ""
        return f"{class_name}([\n{child_formatted}\n{self.indent()}]{mem_arg})"
    
    def visit_SequenceNode(self, node: SequenceNode) -> str:
        return self.visitComposite("Sequence", node.children, getattr(node, "memory_type", "stateless"))
    
    def visit_SelectorNode(self, node: SelectorNode) -> str:
        return self.visitComposite("Selector", node.children, getattr(node, "memory_type", "stateless"))
    
    def visit_ParallelNode(self, node: ParallelNode) -> str:
        return self.visitComposite("Parallel", node.children, getattr(node, "memory_type", "stateless"))

    def visit_DecoratorNode(self, node: DecoratorNode) -> str:
        child_str = self.visit(node.child)
        args_str = f", {node.args[0]}" if node.args else ""
        return f"Decorator('{node.property}', {child_str}{args_str})"    

    def visit_SubtreeNode(self, node: SubtreeNode) -> str:
        raw_args = getattr(node, "args", [])
        formatted_args = [self.format_arg(a) for a in raw_args]
        args_str = (", " + ", ".join(formatted_args)) if formatted_args else ""
        return f"{node.name}BehaviorTree(self.context{args_str})"
    
    def visit_TreeRoot(self, node: TreeRoot) -> str:
        params_list = getattr(node, "params", [])
        self.current_tree_params = set(p.split("=")[0].strip() for p in params_list)

        if not self.imports_done:
            self.imports_done = True
            code = f"# Auto generated code from BTScript\n"
            code += f"# Tree: {node.name}\n\n"
            code += f"from runtime import Sequence, Selector, Parallel, Action, Condition, Decorator, write_bb, get_bb\n\n"        
        else:
            code = f"# Tree: {node.name}\n\n"
        code += f"class {node.name}BehaviorTree:\n"
        self.ilevel = 1
        params_str = (", " + ", ".join(params_list)) if params_list else ""
        code += f"{self.indent()}def __init__(self, context{params_str}):\n"
        self.ilevel = 2
        code += f"{self.indent()}self.context = context\n"
        for p in params_list:
            p_name = p.split("=")[0].strip()
            code += f"{self.indent()}self.{p_name} = {p_name}\n"
        code += f"{self.indent()}self.root_nodes = []\n"
        if getattr(node, "blackboard", None):
            code += f"{self.indent()}if self.context is not None:\n"
            self.ilevel += 1
            code += f"{self.indent()}if not hasattr(self.context, 'blackboard') or self.context.blackboard is None:\n"
            self.ilevel += 1
            code += f"{self.indent()}self.context.blackboard = {{}}\n"
            self.ilevel -= 1
            entries = [f'"{k}": {self.format_arg(v)}' for k, v in node.blackboard.items()]
            defaults_str = "{" + ", ".join(entries) + "}"
            code += f"{self.indent()}defaults = {defaults_str}\n"
            code += f"{self.indent()}for k, v in defaults.items():\n"
            self.ilevel += 1
            code += f"{self.indent()}self.context.blackboard.setdefault(k, v)\n"
            self.ilevel -= 2
        code += "\n"
        self.ilevel = 1
        code += f"{self.indent()}def build(self):\n"
        self.ilevel = 2
        child_strings = [f"{self.indent()}{self.visit(child)}" for child in node.children]
        children_formatted = ",\n".join(child_strings)
        code += f"{self.indent()}self.root_nodes = [\n{children_formatted}\n{self.indent()}]\n"
        code += f"{self.indent()}return self.root_nodes\n\n"
        self.ilevel = 1
        code += f"{self.indent()}def tick(self, ctx=None, dt=None):\n"
        self.ilevel = 2
        code += f"{self.indent()}context = ctx if ctx is not None else self.context\n"
        code += f"{self.indent()}if not self.root_nodes:\n"
        self.ilevel = 3
        code += f"{self.indent()}self.build()\n"
        self.ilevel = 2
        code += f"{self.indent()}statuses = [node.tick(context, dt) for node in self.root_nodes]\n"
        code += f"{self.indent()}from runtime import Status\n"
        code += f"{self.indent()}if any(s == Status.FAILURE for s in statuses): return Status.FAILURE\n"
        code += f"{self.indent()}if any(s == Status.RUNNING for s in statuses): return Status.RUNNING\n"
        code += f"{self.indent()}return Status.SUCCESS\n"
        return code

    def format_arg(self, arg: str) -> str:
        if arg == "true": return "True"
        elif arg == "false": return "False"
        elif arg == "none": return "None"
        if arg.startswith("$"):
            return f'get_bb(ctx, "{arg[1:]}")'
        if hasattr(self, "current_tree_params") and arg in self.current_tree_params:
            return f"self.{arg}"
        return arg
