# 形式化验证环境状态

## 探针结果

当前 Windows + WSL2 Ubuntu 环境已确认：

- Python 3.14.3 可用
- GCC 15.2.0 可用
- Windows 原生 PATH 中没有 Clang、Frama-C、veri-clang、Alt-Ergo 和 Z3
- WSL2 Ubuntu 中已安装 Z3 4.8.12
- WSL2 opam switch `5.1.1` 中已安装 Frama-C 33.0 和 Alt-Ergo 2.4.3

## 当前结论

已在 WSL2 中成功运行 Frama-C/WP 黄金样例 `Mbpp_432.c`。命令使用 Z3 prover，结果为 `4 / 5` 个目标证明，其中 1 个是 `__FC_assert` 相关的 Z3 `Unknown`，不是 Frama-C 环境缺失。随后对其余 45 个可执行样例完成批量验证，45 个均生成了可解析证明结果，但均为部分证明。

## 解除阻塞条件

批量入口已建立为 `scripts/run_framac_batch.py`，结果见 `reports/framac_batch_report.md`、`reports/framac_remaining_results.jsonl` 和 `reports/framac_summary.json`。下一步应建立 Windows 脚本到 WSL 的统一调用入口，并为生成的列表辅助函数补充 ACSL contracts；形式化验证命令仍应通过 `wsl -d Ubuntu -- ...` 执行。
