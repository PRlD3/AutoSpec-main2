# Python 实现选择策略

## 选择顺序

转换器现在按以下顺序选择记录中的 Python 实现：

1. `solutions.with_tests.code`，且 `verifier_status == "SUCCESS"`。
2. `latest_generation.code`，且 `latest_generation.stage == "with_tests"`。
3. `latest_generation.code`。
4. `solutions.no_tests.code`。
5. 顶层 `code` 字段。

选择逻辑位于 `scripts/mbpp_to_c.py` 的 `select_code`。

## 样例验证

| 任务 | 选中版本 | 编译 | 运行 |
|---|---|---|---|
| `Mbpp_138` | `latest_generation`，`stage=remediation_3` | 成功 | 失败 |
| `Mbpp_287` | `solutions.with_tests`，`verifier_status=SUCCESS` | 成功 | 通过 |
| `Mbpp_69` | `solutions.with_tests`，`verifier_status=SUCCESS` | 转换阶段拒绝 | 不适用 |

`Mbpp_287` 原先使用 `solutions.no_tests` 的错误公式，切换到 `with_tests` 后三个断言均满足。

`Mbpp_138` 的 `with_tests` 和 `latest_generation` 版本都被数据集标记为失败，且其实现仍不能满足测试中对 `10` 和 `14` 的期望。因此该样例保留为数据集实现失败，不应归因于 C 转换器。

`Mbpp_69` 的 `with_tests` 版本虽然通过数据集验证，但使用了当前转换器尚未支持的字符串 `join` 和 `map` 语义，因此被记录为转换阶段失败。这是转换能力不足，不是实现选择失败。
