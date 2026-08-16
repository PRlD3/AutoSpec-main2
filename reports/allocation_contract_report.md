# malloc/realloc 分配语义修复报告

## 改动

列表辅助函数现在对分配失败和容量溢出采用显式终止语义：

- `malloc` 返回空指针时调用 `abort()`。
- `realloc` 返回空指针时调用 `abort()`，避免覆盖原有有效指针。
- 扩容前限制容量不超过 `1073741823`，避免 `capacity * 2` 的有符号整数溢出。
- `make_int_list` 和 `append_int_list` 的 ACSL 前置条件声明容量范围和输入数组有效性。

## 验证

- 重新生成：399 条记录中生成 47 个 C 文件。
- GCC 与运行时：代表性 `Mbpp_101.c` 编译和断言运行通过。
- Frama-C/WP + Z3：排除 `Mbpp_138` 后验证 46 个样例。
- 工具失败：0。
- 超时退出：0。
- 无法解析：0。
- 完全证明：0。
- 部分证明：46。

本轮 46 个样例均可被 Frama-C/WP 解析并生成证明目标。由于动态分配、循环终止、`assigns`/`from` 和 `__FC_assert` 相关目标仍未完全建模，当前结果仍属于部分证明。

## 代表性结果

`Mbpp_101.c` 的证明结果为 `21 / 38`，相比加入基础 contracts 后的 `18 / 27`，新增的分配失败和容量安全分支被纳入了 WP 目标集合。证明比例不应直接与上一轮比较，因为目标集合发生了扩展。

## 结果文件

- `reports/allocation_framac_results.jsonl`
- `reports/framac_summary.json`
- `scripts/mbpp_to_c.py`

## 后续工作

下一步应将 `abort()` 失败分支替换为显式可验证的分配失败策略，或将内存分配抽象为带 ACSL contract 的包装函数；同时为扩容循环补充容量增长不变量，并为列表辅助函数补充 `assigns` 与 `from` 关系。
