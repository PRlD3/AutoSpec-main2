# MBPP Python-to-C 最终回归报告

## 统计口径

本报告基于最新实现选择逻辑和最新生成结果。`Mbpp_138` 已从转换器质量统计中单独归类为 `source_invalid`，因为其候选 Python 实现均未通过数据集测试。

## 总体结果

| 阶段 | 数量 | 说明 |
|---|---:|---|
| MBPP 总记录 | 399 | 数据集全部记录 |
| 源实现有效 | 398 | 总记录减去 `source_invalid` |
| 源实现无效 | 1 | `Mbpp_138` |
| C 生成成功 | 47 | 源实现有效记录中的可转换子集 |
| 转换阶段拒绝 | 351 | 源实现有效但当前 Python 子集不支持 |
| GCC 编译成功 | 47 | 生成文件全部通过 C11 编译 |
| GCC 编译失败 | 0 | 无已生成但不可编译文件 |
| 运行时测试通过 | 46 | `main` 中的断言全部通过 |
| 运行时测试失败 | 0 | 源无效样例不纳入运行时失败 |

## 比率

- 源实现有效率：`398/399 = 99.7%`
- 转换成功率（源实现有效样例）：`47/398 = 11.8%`
- GCC 成功率（已生成文件）：`47/47 = 100%`
- 运行通过率（已执行且源实现有效）：`46/46 = 100%`
- 运行通过率（全部生成文件）：`46/47 = 97.9%`

## 源实现无效样例

### Mbpp_138

测试要求：

```python
assert is_Sum_Of_Powers_Of_Two(10) == True
assert is_Sum_Of_Powers_Of_Two(7) == False
assert is_Sum_Of_Powers_Of_Two(14) == True
```

数据集中的 `no_tests`、`with_tests` 和 `latest_generation` 候选均未通过验证。以 `10` 为例，候选实现实际返回 `False`，而测试期望为 `True`。该记录归类为 `source_invalid`，不归因于 C 转换器。

## 转换阶段拒绝

当前转换器对不支持的 Python 语义进行显式拒绝，不生成不可编译 C 文件。典型类别包括：

- 列表真值判断、列表比较和列表拼接
- 字符串、集合、字典及正则表达式语义
- 未实现的库函数和方法调用
- 不支持的复合表达式、语句和数据结构

失败明细见 `reports/final_float_failures.jsonl`。

## 生成与运行证据

- 最新 C 输出目录：`output/final_float_regression`
- 最新运行明细：`output/latest_runtime_results.json`；对应的最新 C 文件目录为 `output/final_float_regression`。
- 最新运行包含 47 个生成文件，其中 `Mbpp_138` 的失败属于 `source_invalid`，最终有效源实现运行统计将其排除。
- 运行统计报告：`reports/runtime_regression.md`
- 源无效记录：`reports/source_invalid_cases.json`
- 机器可读分类统计：`reports/failure_taxonomy.json`
- Python/C 差分测试：141 条用例中 139 条一致，剩余 2 条均属于 `Mbpp_138` 的源实现无效。
- 浮点回归：`Mbpp_432` 已生成 `double` 返回类型并通过 `7.5` 测试。

## 结论

当前流程已实现转换、编译和运行阶段的明确分层。所有生成的 47 个 C 文件均通过 GCC，46 个有效源实现对应的运行测试全部通过；剩余未覆盖记录被转换阶段显式拒绝，`Mbpp_138` 被独立归类为源实现无效。编译成功不再被单独视为语义等价，而是与运行时断言结果共同构成转换有效性的判断依据。
