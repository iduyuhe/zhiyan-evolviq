#!/usr/bin/env python3
"""依赖回归护栏：扫描 src/ 的 import，与 pyproject.toml 声明比对。

目的：捕获「代码直接 import 了某个第三方包，但 pyproject 未声明」的漏列
（如 apscheduler 漏列导致容器启动即崩的事故）。

规则：
- 用 ast 解析 import，取顶层包名。
- 排除：标准库（sys.stdlib_module_names）、项目内包（runtime/common/gateways/src）。
- normalize：lower + '-'/'_' 统一，再比对 pyproject 依赖。
- 输出两类：
   * [MISSING] 直接 import 但 pyproject 未声明 —— 需补依赖（护栏重点）。
   * [INDIRECT] 仅间接依赖（如 starlette 由 fastapi 带入）被直接 import —— 提示，不报错。

退出码：发现 MISSING 返回 1，否则 0（便于接入 CI/pre-commit）。
"""
import ast
import os
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
PYPROJECT = os.path.join(ROOT, "pyproject.toml")

# 项目内顶层包（相对导入或非第三方）
PROJECT_PKGS = {"runtime", "common", "gateways", "src", "scripts"}

# 间接依赖但其 import 名合法，需放行（避免误报）
INDIRECT_OK = {"starlette", "greenlet", "anyio", "typing_extensions", "pydantic_core"}

# 模块名 → pyproject 包名（normalize 后）别名映射：弥补「包名与 import 模块名不一致」的误报。
# 例如 PyPI 包 paho-mqtt 提供的模块是 paho；pillow→PIL；pyyaml→yaml。
ALIASES = {
    "paho": "paho_mqtt",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
}


def norm(name: str) -> str:
    return name.lower().replace("-", "_")


def load_declared() -> set:
    with open(PYPROJECT, "rb") as f:
        data = tomllib.load(f)
    deps = data.get("project", {}).get("dependencies", [])
    declared = set()
    for d in deps:
        # 去掉 extras（如 uvicorn[standard]）、环境标记与版本约束，取包名
        pkg = d.split(";")[0].split("[")[0]
        pkg = pkg.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("^")[0].strip()
        declared.add(norm(pkg))
    return declared


def collect_imports() -> set:
    imported = set()
    for dirpath, _, files in os.walk(SRC):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imported.add(a.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        continue  # 相对导入
                    if node.module:
                        imported.add(node.module.split(".")[0])
    return imported


def main():
    declared = load_declared()
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    imported = collect_imports()

    third_party = {
        p for p in imported
        if p not in stdlib and p not in PROJECT_PKGS
    }

    missing = sorted(p for p in third_party if ALIASES.get(p, norm(p)) not in declared and p not in INDIRECT_OK)
    indirect = sorted(p for p in third_party if p in INDIRECT_OK)

    print("=== 依赖回归护栏检查 ===")
    print(f"已声明依赖数: {len(declared)}")
    print(f"src 第三方 import 数: {len(third_party)}")
    if missing:
        print(f"\n[MISSING] 直接 import 但 pyproject 未声明（需补依赖）：")
        for p in missing:
            print(f"  - {p}")
    else:
        print("\n[OK] 无漏列依赖。")
    if indirect:
        print(f"\n[INDIRECT] 间接依赖被直接 import（已放行，仅提示）：")
        for p in indirect:
            print(f"  - {p}")

    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
