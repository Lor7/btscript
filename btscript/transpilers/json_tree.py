import json

class JSONTranspiler:
    def __init__(self, ast):
        self.trees = ast if isinstance(ast, list) else [ast]

    def transpile(self) -> str:
        data = {
            "trees": [self.visit(t) for t in self.trees]
        }
        return json.dumps(data, indent=2)

    def visit(self, node):
        method = f"visit_{type(node).__name__}"
        return getattr(self, method)(node)

    def visit_TreeRoot(self, node):
        res = {
            "name": node.name,
            "children": [self.visit(c) for c in node.children]
        }
        if getattr(node, "params", None):
            res["params"] = node.params
        if getattr(node, "blackboard", None):
            res["blackboard"] = node.blackboard
        return res

    def visit_SequenceNode(self, node):
        return {"type": "Stateful Sequence" if node.is_stateful else "Stateless Sequence",
                "children": [self.visit(c) for c in node.children]
                }

    def visit_SelectorNode(self, node):
        return {"type": "Stateful Selector" if node.is_stateful else "Stateless Selector",
                "children": [self.visit(c) for c in node.children]}

    def visit_ParallelNode(self, node):
        return {"type": "Stateful Parallel" if node.is_stateful else "Stateless Parallel",
                "children": [self.visit(c) for c in node.children]}

    def visit_DecoratorNode(self, node):
        return {
            "type": "Decorator",
            "property": node.property,
            "args": node.args,
            "child": self.visit(node.child) if node.child else None
        }

    def visit_ActionNode(self, node):
        res = {"type": "Action", "name": node.name, "args": node.args}
        if getattr(node, "output_var", None):
            res["output_var"] = node.output_var
        return res

    def visit_ConditionNode(self, node):
        return {"type": "Condition", "name": node.name, "args": node.args}

    def visit_SubtreeNode(self, node):
        return {"type": "Subtree", "name": node.name, "args": node.args}
