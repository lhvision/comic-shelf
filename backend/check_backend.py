"""Lightweight zero-dependency Python static checker for backend.

Verifies:
1. Syntax validity of all python files in backend/
2. Clean importability of all backend modules
3. Undefined variables and AST scope reference integrity
"""
from __future__ import annotations

import ast
import builtins
import py_compile
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

IMPLICIT_GLOBALS = {
    "__name__",
    "__file__",
    "__doc__",
    "__package__",
    "__loader__",
    "__spec__",
    "__annotations__",
    "__builtins__",
}


class ScopeVisitor(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.errors: list[str] = []
        self.scopes: list[set[str]] = [
            set(dir(builtins)) | IMPLICIT_GLOBALS
        ]

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            self.scopes[-1].add(a.asname or a.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for a in node.names:
            self.scopes[-1].add(a.asname or a.name)
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        lambda_scope = set()
        for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
            lambda_scope.add(arg.arg)
        if node.args.vararg:
            lambda_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            lambda_scope.add(node.args.kwarg.arg)
        self.scopes.append(lambda_scope)
        self.visit(node.body)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scopes[-1].add(node.name)
        for d in node.decorator_list:
            self.visit(d)
        if node.returns:
            self.visit(node.returns)
        for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
            if arg.annotation:
                self.visit(arg.annotation)

        func_scope = set()
        for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
            func_scope.add(arg.arg)
        if node.args.vararg:
            func_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            func_scope.add(node.args.kwarg.arg)

        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for t in child.targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            func_scope.add(n.id)
            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    func_scope.add(child.target.id)
            elif isinstance(child, ast.AugAssign):
                if isinstance(child.target, ast.Name):
                    func_scope.add(child.target.id)
            elif isinstance(child, ast.NamedExpr):
                if isinstance(child.target, ast.Name):
                    func_scope.add(child.target.id)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                func_scope.add(child.name)
            elif isinstance(child, ast.For):
                for n in ast.walk(child.target):
                    if isinstance(n, ast.Name):
                        func_scope.add(n.id)
            elif isinstance(child, ast.With):
                for it in child.items:
                    if it.optional_vars:
                        for n in ast.walk(it.optional_vars):
                            if isinstance(n, ast.Name):
                                func_scope.add(n.id)
            elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for gen in child.generators:
                    for n in ast.walk(gen.target):
                        if isinstance(n, ast.Name):
                            func_scope.add(n.id)
            elif hasattr(ast, "MatchAs") and isinstance(child, ast.MatchAs) and child.name:
                func_scope.add(child.name)
            elif hasattr(ast, "MatchStar") and isinstance(child, ast.MatchStar) and child.name:
                func_scope.add(child.name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
                func_scope.add(child.name)
            elif isinstance(child, ast.Import):
                for a in child.names:
                    func_scope.add(a.asname or a.name.split(".")[0])
            elif isinstance(child, ast.ImportFrom):
                for a in child.names:
                    func_scope.add(a.asname or a.name)

        if hasattr(node, "type_params") and node.type_params:
            for tp in node.type_params:
                if hasattr(tp, "name"):
                    func_scope.add(tp.name)

        self.scopes.append(func_scope)
        for stmt in node.body:
            self.visit(stmt)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes[-1].add(node.name)
        for b in node.bases:
            self.visit(b)
        class_scope = set()
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                class_scope.add(child.name)
            elif isinstance(child, ast.Assign):
                for t in child.targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            class_scope.add(n.id)
            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    class_scope.add(child.target.id)
        self.scopes.append(class_scope)
        for stmt in node.body:
            self.visit(stmt)
        self.scopes.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        for t in node.targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    self.scopes[-1].add(n.id)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.scopes[-1].add(node.target.id)
        if node.value:
            self.visit(node.value)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            name = node.id
            if not any(name in scope for scope in self.scopes):
                self.errors.append(f"Undefined symbol '{name}' at {self.filename}:{node.lineno}")


def check_syntax_and_imports() -> list[str]:
    errors: list[str] = []
    py_files = sorted(BACKEND_DIR.glob("**/*.py"))

    # 1. Bytecode compilation / syntax check
    for pf in py_files:
        try:
            py_compile.compile(str(pf), doraise=True)
        except Exception as e:
            errors.append(f"Syntax error in {pf.relative_to(PROJECT_ROOT)}: {e}")

    # 2. Module import checks
    modules = [
        "app.config",
        "app.models",
        "app.auth",
        "app.gate",
        "app.jobs",
        "app.storage",
        "app.providers.base",
        "app.providers.local",
        "app.providers.jm",
        "app.providers.registry",
        "app.imsearch",
        "app.main",
    ]

    for mod in modules:
        try:
            __import__(mod)
        except Exception as e:
            errors.append(f"Import error in {mod}: {e}")

    # 3. Scope & Undefined Variable Checking via AST
    app_files = sorted((BACKEND_DIR / "app").glob("**/*.py"))
    for af in app_files:
        try:
            tree = ast.parse(af.read_text(encoding="utf-8"), filename=str(af))
            v = ScopeVisitor(str(af.relative_to(PROJECT_ROOT)))
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        for n in ast.walk(t):
                            if isinstance(n, ast.Name):
                                v.scopes[0].add(n.id)
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        v.scopes[0].add(node.target.id)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    v.scopes[0].add(node.name)
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        v.scopes[0].add(a.asname or a.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    for a in node.names:
                        v.scopes[0].add(a.asname or a.name)
            v.visit(tree)
            if v.errors:
                errors.extend(v.errors)
        except Exception as e:
            errors.append(f"AST parse error in {af.relative_to(PROJECT_ROOT)}: {e}")

    return errors


def main() -> None:
    errors = check_syntax_and_imports()
    if errors:
        print(f"❌ Backend static check failed ({len(errors)} error(s)):")
        for err in errors:
            print(f"   • {err}")
        sys.exit(1)
    else:
        print("✅ Backend static check passed: 0 syntax, import, or undefined-symbol errors.")


if __name__ == "__main__":
    main()
