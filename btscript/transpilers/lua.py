"""
btscript.transpilers.lua
~~~~~~~~~~~~~~~~~~~~~~~~

Compiles BTScript ASTs into clean, modular Lua code compatible with Lua 5.1+,
LuaJIT, Defold, and LÖVE2D. Generates metatable-based context stubs,
mock factories, and tree factory functions.
"""

from ..nodes import (
    TreeRoot, SubtreeNode, SequenceNode, SelectorNode, ParallelNode,
    ActionNode, ConditionNode, DecoratorNode
)


class LuaStubTranspiler:
    def __init__(self, ast):
        self.trees = ast if isinstance(ast, list) else [ast]
        self.ilevel = 0

    def indent(self) -> str:
        return self.ilevel * "\t"

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
            return "..."
        count = next(iter(arities))
        if count == 0:
            return ""
        args = [f"arg{i+1}" for i in range(count)]
        return ", ".join(args)

    def transpile_tree(self, tree: TreeRoot) -> str:
        actions, conditions = self.collect_signatures(tree)
        class_name = f"{tree.name}ContextStub"

        self.ilevel = 0
        code = f"-- Context Stub for Tree '{tree.name}'\n"
        code += f"local {class_name} = {{}}\n"
        code += f"{class_name}.__index = {class_name}\n\n"
        code += f"function {class_name}.new(bindings)\n"
        self.ilevel = 1
        code += f"{self.indent()}local self = setmetatable({{}}, {class_name})\n"
        code += f"{self.indent()}if bindings then\n"
        self.ilevel = 2
        code += f"{self.indent()}for k, v in pairs(bindings) do\n"
        self.ilevel = 3
        code += f"{self.indent()}self[k] = v\n"
        self.ilevel = 2
        code += f"{self.indent()}end\n"
        self.ilevel = 1
        code += f"{self.indent()}end\n"
        code += f"{self.indent()}return self\n"
        self.ilevel = 0
        code += f"end\n\n"

        code += f"-- --- CONDITIONS ---\n"
        for cond_name in sorted(conditions.keys()):
            params = self._format_params(conditions[cond_name])
            code += f"function {class_name}:{cond_name}({params})\n"
            self.ilevel = 1
            code += f"{self.indent()}error(\"Context method '{cond_name}' not implemented or assigned.\")\n"
            self.ilevel = 0
            code += f"end\n\n"

        code += f"-- --- ACTIONS ---\n"
        for act_name in sorted(actions.keys()):
            params = self._format_params(actions[act_name])
            code += f"function {class_name}:{act_name}({params})\n"
            self.ilevel = 1
            code += f"{self.indent()}error(\"Context method '{act_name}' not implemented or assigned.\")\n"
            self.ilevel = 0
            code += f"end\n\n"

        code += f"function {class_name}.new_mock()\n"
        self.ilevel = 1
        code += f"{self.indent()}local mock = {class_name}.new()\n"
        for cond_name in sorted(conditions.keys()):
            code += f"{self.indent()}mock.{cond_name} = function(...) return true end\n"
        for act_name in sorted(actions.keys()):
            code += f"{self.indent()}mock.{act_name} = function(...) return 'SUCCESS' end\n"
        code += f"{self.indent()}return mock\n"
        self.ilevel = 0
        code += f"end\n"

        return code

    def transpile(self) -> str:
        trees = self.trees
        code = "-- Auto generated Context Stubs from BTScript\n\n"
        code += "\n\n".join(self.transpile_tree(t) for t in trees)
        code += "\n\n"
        if len(trees) == 1:
            code += f"return {trees[0].name}ContextStub\n"
        else:
            code += f"return setmetatable({{\n"
            for t in trees:
                code += f"\t{t.name}ContextStub = {t.name}ContextStub,\n"
            code += f"}}, {{\n\t__index = {trees[-1].name}ContextStub\n}})\n"
        return code


class LuaTranspiler:
    def __init__(self, ast, directive = None):
        self.ast = ast
        self.directive = directive or {}
        self.ilevel = 0
        self.imports_done = False

    def indent(self) -> str:
        return self.ilevel * "\t"
    
    def transpile(self) -> str:
        trees = self.ast if isinstance(self.ast, list) else [self.ast]
        if not self.imports_done:
            self.imports_done = True
            code = "-- Auto generated code from BTScript\n\n"
            code += "local BT = require('runtime')\n"
            code += "local Sequence, Selector, Parallel, Action, Condition, Decorator, write_bb, get_bb = BT.Sequence, BT.Selector, BT.Parallel, BT.Action, BT.Condition, BT.Decorator, BT.write_bb, BT.get_bb\n\n"
        else:
            code = ""
        code += "\n\n".join(self.visit_TreeRoot(tree) for tree in trees)
        code += "\n\n"

        include_stub = self.directive.get("stub", True)
        if include_stub:
            code += "-- ======================================================================\n"
            code += "-- Context Stubs\n"
            code += "-- ======================================================================\n\n"
            stub_transpiler = LuaStubTranspiler(trees)
            code += "\n\n".join(stub_transpiler.transpile_tree(t) for t in trees)
            code += "\n\n"

        code += "return setmetatable({\n"
        for t in trees:
            code += f"\t{t.name}BehaviorTree = {t.name}BehaviorTree,\n"
            if include_stub:
                code += f"\t{t.name}ContextStub = {t.name}ContextStub,\n"
        code += f"}}, {{\n\t__index = {trees[-1].name}BehaviorTree\n}})\n"
        return code

    def visit(self, node) -> str:
        method = f"visit_{type(node).__name__}"
        return getattr(self, method)(node)
    
    def visit_ActionNode(self, node: ActionNode) -> str:
        args_str = ", ".join(self.format_arg(a) for a in node.args)
        if getattr(node, "output_var", None):
            return f"Action(function (ctx) return write_bb(ctx, '{node.output_var}', ctx:{node.name}({args_str})) end)"
        return f"Action(function (ctx) return ctx:{node.name}({args_str}) end)"
    
    def visit_ConditionNode(self, node: ConditionNode) -> str:
        args_str = ", ".join(self.format_arg(a) for a in node.args)
        return f"Condition(function (ctx) return ctx:{node.name}({args_str}) end)"

    def visitComposite(self, class_name: str, children, memory_type: str = "stateless") -> str:
        self.ilevel += 1
        child_strings = [f"{self.indent()}{self.visit(child)}" for child in children]
        child_formatted = ",\n".join(child_strings)
        self.ilevel -= 1
        mem_arg = f', "{memory_type}"' if memory_type == "stateful" else ""
        return f"{class_name}({{\n{child_formatted}\n{self.indent()}}}{mem_arg})"
    
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
        return f"{node.name}BehaviorTree.new(self.context{args_str})"

    def visit_TreeRoot(self, node: TreeRoot) -> str:
        params_list = getattr(node, "params", [])
        self.current_tree_params = set(p.split("=")[0].strip() for p in params_list)
        params_names = [p.split("=")[0].strip() for p in params_list]
        params_str = (", " + ", ".join(params_names)) if params_names else ""

        code = f"-- Tree: {node.name}\n"
        code += f"local {node.name}BehaviorTree = {{}}\n"
        code += f"{node.name}BehaviorTree.__index = {node.name}BehaviorTree\n\n"
        code += f"function {node.name}BehaviorTree.new(context{params_str})\n"
        code += f"\tlocal self = setmetatable({{}}, {node.name}BehaviorTree)\n"
        code += f"\tself.context = context\n"
        for p in params_list:
            if "=" in p:
                p_name, def_val = p.split("=", 1)
                p_name = p_name.strip()
                def_lua = self.format_arg(def_val.strip())
                code += f"\tif {p_name} ~= nil then self.{p_name} = {p_name} else self.{p_name} = {def_lua} end\n"
            else:
                p_name = p.strip()
                code += f"\tself.{p_name} = {p_name}\n"
        if getattr(node, "blackboard", None):
            code += f"\tif self.context then\n"
            code += f"\t\tif not self.context.blackboard then self.context.blackboard = {{}} end\n"
            entries = [f'["{k}"] = {self.format_arg(v)}' for k, v in node.blackboard.items() if self.format_arg(v) != "nil"]
            if entries:
                defaults_str = "{" + ", ".join(entries) + "}"
                code += f"\t\tlocal defaults = {defaults_str}\n"
                code += f"\t\tfor k, v in pairs(defaults) do\n"
                code += f"\t\t\tif self.context.blackboard[k] == nil then self.context.blackboard[k] = v end\n"
                code += f"\t\tend\n"
            code += f"\tend\n"
        code += f"\tself.root_nodes = {{}}\n"
        code += f"\treturn self\n"
        code += f"end\n\n"
        code += f"function {node.name}BehaviorTree:build()\n"
        self.ilevel = 1
        child_strings = [f"{self.indent()}{self.visit(child)}" for child in node.children]
        children_formatted = ",\n".join(child_strings)
        code += f"{self.indent()}self.root_nodes = {{\n{children_formatted}\n{self.indent()}}}\n"
        code += f"{self.indent()}return self.root_nodes\n"
        code += f"end\n\n"
        code += f"function {node.name}BehaviorTree:tick(ctx, dt)\n"
        code += f"\tlocal context = ctx or self.context\n"
        code += f"\tif #self.root_nodes == 0 then\n"
        code += f"\t\tself:build()\n"
        code += f"\tend\n"
        code += f"\tlocal any_running = false\n"
        code += f"\tfor i, node in ipairs(self.root_nodes) do\n"
        code += f"\t\tlocal s = node:tick(context, dt)\n"
        code += f"\t\tif s == BT.Status.FAILURE then return BT.Status.FAILURE end\n"
        code += f"\t\tif s == BT.Status.RUNNING then any_running = true end\n"
        code += f"\tend\n"
        code += f"\tif any_running then return BT.Status.RUNNING end\n"
        code += f"\treturn BT.Status.SUCCESS\n"
        code += f"end"
        return code

    def format_arg(self, arg: str) -> str:
        if arg == "none": return "nil"
        if arg.startswith("$"):
            return f'get_bb(ctx, "{arg[1:]}")'
        if hasattr(self, "current_tree_params") and arg in self.current_tree_params:
            return f"self.{arg}"
        return arg
