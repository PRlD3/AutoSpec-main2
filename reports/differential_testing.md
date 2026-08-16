# Python/C 差分测试报告

## 测试范围

使用 `scripts/differential_test.py` 对当前 47 个已生成 C 文件执行差分回归。每条 MBPP 记录的测试断言分别在选中的 Python 实现和重新生成的 C harness 中执行，按任务和测试编号对齐结果。

## 统计结果

- 测试任务：47
- 测试用例：141
- Python/C 结果一致：139
- Python/C 结果不一致：2
- 一致率：`139/141 = 98.6%`

## 不一致样例

### Mbpp_138

- `test_0`：Python 和 C 均未满足 `is_Sum_Of_Powers_Of_Two(10) == True`
- `test_2`：Python 和 C 均未满足 `is_Sum_Of_Powers_Of_Two(14) == True`
- 分类：`source_invalid`
- 这两项不是 Python/C 转换差异，而是源实现与数据集测试期望不一致。

### Mbpp_432

- 已修复浮点返回值和 `/` 运算生成逻辑。
- `median_trapezium(6,9,4)` 现在生成 `double` 返回值并通过 `7.5` 断言。
- 独立 C 编译与运行验证通过。

## 结论

当前差分框架已经能够独立执行 Python 和 C 两端，并暴露固定 MBPP 断言之外的转换语义问题。浮点返回值修复后，139 条测试一致；剩余 2 条均属于 `Mbpp_138` 的源实现无效分类。

逐用例结果见 `output/differential_results.jsonl`，汇总数据见 `reports/differential_summary.json`。
