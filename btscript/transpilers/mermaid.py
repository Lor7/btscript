from ..nodes import TreeRoot, SubtreeNode, SequenceNode, SelectorNode, ParallelNode, ActionNode, ConditionNode, DecoratorNode

class MermaidTranspiler:
    def __init__(self, ast, main_tree_name: str = None):
        self.trees = ast if isinstance(ast, list) else [ast]
        self.trees_by_name = {t.name: t for t in self.trees}
        if main_tree_name and main_tree_name in self.trees_by_name:
            self.main_tree = self.trees_by_name[main_tree_name]
        else:
            self.main_tree = self.trees[-1] if self.trees else None
        self.counter = 0

    def next_id(self, prefix: str = "node") -> str:
        self.counter += 1
        return f"{prefix}_{self.counter}"

    def transpile(self) -> str:
        if not self.main_tree:
            return "graph TD\n"
        lines = ["graph TD"]
        lines.extend(self.visit_TreeRoot(self.main_tree))
        return "\n".join(lines)

    def visit(self, node):
        method = f"visit_{type(node).__name__}"
        return getattr(self, method)(node)

    def visit_TreeRoot(self, node: TreeRoot) -> list:
        lines = []
        root_id = self.next_id(f"tree_{node.name}")
        params_str = f"({', '.join(node.params)})" if getattr(node, "params", None) else ""
        bb_str = f"<br/>[bb: {', '.join(f'${k}={v.replace(chr(34), chr(39))}' for k, v in node.blackboard.items())}]" if getattr(node, "blackboard", None) else ""
        lines.append(f'    {root_id}(["Tree: {node.name}{params_str}{bb_str}"])')
        for child in node.children:
            cid, clines = self.visit(child)
            lines.extend(clines)
            lines.append(f"    {root_id} --> {cid}")
        return lines

    def _visit_composite(self, node, label: str) -> tuple:
        my_id = self.next_id("comp")
        state_tag = " (stateful)" if getattr(node, "is_stateful", False) else ""
        lines = [f'    {my_id}["{label}{state_tag}"]']
        for child in node.children:
            cid, clines = self.visit(child)
            lines.extend(clines)
            lines.append(f"    {my_id} --> {cid}")
        return my_id, lines

    def visit_SequenceNode(self, node: SequenceNode) -> tuple:
        return self._visit_composite(node, "-> Sequence")

    def visit_SelectorNode(self, node: SelectorNode) -> tuple:
        return self._visit_composite(node, "? Selector")

    def visit_ParallelNode(self, node: ParallelNode) -> tuple:
        return self._visit_composite(node, "=> Parallel")

    def visit_DecoratorNode(self, node: DecoratorNode) -> tuple:
        my_id = self.next_id("dec")
        arg_str = f"({', '.join(node.args)})" if node.args else ""
        label = f"Decorator: {node.property}{arg_str}"
        lines = [f'    {my_id}{{{{"{label}"}}}}']
        if node.child:
            cid, clines = self.visit(node.child)
            lines.extend(clines)
            lines.append(f"    {my_id} --> {cid}")
        return my_id, lines

    def visit_ActionNode(self, node: ActionNode) -> tuple:
        my_id = self.next_id("act")
        args_str = f"({', '.join(node.args)})" if node.args else "()"
        clean_args = args_str.replace('"', "'")
        out_str = f" ➔ ${node.output_var}" if getattr(node, "output_var", None) else ""
        lines = [f'    {my_id}["Action: {node.name}{clean_args}{out_str}"]']
        return my_id, lines

    def visit_ConditionNode(self, node: ConditionNode) -> tuple:
        my_id = self.next_id("cond")
        args_str = f"({', '.join(node.args)})" if node.args else "()"
        clean_args = args_str.replace('"', "'")
        lines = [f'    {my_id}("{node.name}{clean_args}?")']
        return my_id, lines

    def visit_SubtreeNode(self, node: SubtreeNode) -> tuple:
        target_tree = self.trees_by_name.get(node.name)
        args_str = f"({', '.join(node.args)})" if getattr(node, "args", None) else ""
        clean_args = args_str.replace('"', "'")
        if not target_tree:
            box_id = self.next_id("missing")
            return box_id, [f'    {box_id}[["Missing Subtree: {node.name}{clean_args}"]]']

        sg_id = self.next_id(f"subgraph_{node.name}")
        lines = []
        lines.append(f'    subgraph {sg_id} ["Subtree: {node.name}{clean_args}"]')

        child_entry_ids = []
        for child in target_tree.children:
            cid, clines = self.visit(child)
            for cline in clines:
                lines.append(f"    {cline}")
            child_entry_ids.append(cid)

        lines.append("    end")

        if len(child_entry_ids) == 1:
            entry_id = child_entry_ids[0]
        else:
            entry_id = self.next_id(f"entry_{node.name}")
            lines.insert(1, f'        {entry_id}(["{node.name} Root"])')
            for cid in child_entry_ids:
                lines.append(f"        {entry_id} --> {cid}")

        return entry_id, lines
