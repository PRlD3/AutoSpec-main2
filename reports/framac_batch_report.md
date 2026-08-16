# Frama-C/WP 批量验证报告

## 验证范围

- 输入目录：`output/final_float_regression`
- 验证器：Frama-C 33.0
- 推理器：Z3 4.8.12
- 执行环境：WSL2 Ubuntu，opam switch `5.1.1`
- 命令：`frama-c -wp -wp-prover z3 -wp-timeout 10 <file>.c`
- 已单独验证的黄金样例：`Mbpp_432.c`
- 已排除的源实现无效样例：`Mbpp_138.c`

## 结果

本轮实际验证 45 个剩余 C 文件。项目当前共有 47 个生成文件，因此在排除 `Mbpp_432` 和 `Mbpp_138` 后，剩余数量是 45 个，而不是 43 个。

| 状态 | 数量 |
|---|---:|
| 完全证明 | 0 |
| 部分证明 | 45 |
| 工具失败 | 0 |
| 超时退出 | 0 |
| 无可解析结果 | 0 |

每个样例均成功启动 Frama-C/WP 并生成 `Proved goals: x / y`，但都存在至少一个未证明目标，因此本轮没有样例达到形式化验证完全通过标准。

## 证明目标分布

- `4/5`：27 个
- `3/5`：4 个
- `7/13`：2 个
- `10/16`：2 个
- 其他目标规模：10 个

未证明目标主要来自以下类型：

- `main` 中 `assert` 的非空指针前置条件
- `malloc`、`realloc` 和内存模型相关假设
- 递归函数终止性
- 缺少循环不变量、decreases 或 assigns 规格
- Z3 在当前超时设置下返回 `Timeout` 或 `Unknown`

## 机器可读结果

- 逐文件结果：`reports/framac_remaining_results.jsonl`
- 汇总结果：`reports/framac_summary.json`
- 批处理入口：[run_framac_batch.py](../scripts/run_framac_batch.py)

## 结论

Frama-C/WP 与 Z3 的批量调用链已经验证可用，45 个样例均能完成解析和证明目标生成。当前瓶颈不是工具启动失败，而是生成 C 代码缺少 ACSL 规格以及列表辅助函数的内存安全条件，下一步应优先为辅助函数和主函数补充可证明的 contracts，并单独处理递归终止性。
