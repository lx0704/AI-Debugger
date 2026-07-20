import ast, pathlib

class MethodIndex:
    def __init__(self):
        self.index = {}  # (filename, line) -> method_key

    def add_file(self, filename: str, source: str):
        tree = ast.parse(source)
        _attach_parents(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = _qualname(node)
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                for ln in range(start, end+1):
                    self.index[(filename, ln)] = f"{filename}:{qual}"

def _attach_parents(tree):
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "parent", parent)

def _qualname(node):
    names = [node.name]
    p = getattr(node, "parent", None)
    while p:
        if isinstance(p, ast.ClassDef):
            names.append(p.name)
        p = getattr(p, "parent", None)
    return ".".join(reversed(names))
