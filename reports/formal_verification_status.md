# 形式化验证环境状态

## 探针结果

当前 Windows 环境已确认：

- Python 3.14.3 可用
- GCC 15.2.0 可用
- Clang 不在 PATH 中
- Frama-C 不在 PATH 中
- veri-clang 不在 PATH 中
- Alt-Ergo 不在 PATH 中
- Z3 不在 PATH 中

## 当前结论

目前只能完成 Python-to-C 转换、GCC 编译和运行时回归，不能声称已经完成 AutoSpec/Frama-C 形式化验证。Frama-C/WP 黄金样例暂时无法执行，状态记为 `blocked_by_missing_tools`。

## 解除阻塞条件

需要先配置 Frama-C、veri-clang 和至少一个 WP prover，并确认这些命令可以从当前终端直接调用。环境恢复后，先运行无 LLM 依赖的 Frama-C/WP 黄金样例，再执行 AutoSpec 样例回归。
