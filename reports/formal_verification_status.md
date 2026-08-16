# 形式化验证环境状态

## 探针结果

当前 Windows + WSL2 Ubuntu 环境已确认：

- Python 3.14.3 可用
- GCC 15.2.0 可用
- Windows 原生 PATH 中没有 Clang、Frama-C、veri-clang、Alt-Ergo 和 Z3
- WSL2 Ubuntu 中已安装 Z3 4.8.12
- WSL2 opam switch `5.1.1` 中已安装 Frama-C 33.0 和 Alt-Ergo 2.4.3

## 当前结论

已在 WSL2 中成功运行 Frama-C/WP 黄金样例 `Mbpp_432.c`。命令使用 Z3 prover，结果为 `4 / 5` 个目标证明，其中 1 个是 `__FC_assert` 相关的 Z3 `Unknown`，不是 Frama-C 环境缺失。当前状态为 `frama_c_wp_verified_in_wsl`。

## 解除阻塞条件

下一步需要建立 Windows 脚本到 WSL 的统一调用入口，并补充 `veri-clang`。在此之前，形式化验证命令应通过 `wsl -d Ubuntu -- ...` 执行，不能直接假设 Windows PATH 中存在 `frama-c` 或 `z3`。
