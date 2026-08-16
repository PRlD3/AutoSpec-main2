# ACSL Contract 补充进度

## 本轮改动

列表运行时生成代码已开始加入 ACSL 前置条件和修改集：

- `make_int_list` 增加非负长度和输入数组可读性要求。
- `append_int_list` 增加列表指针、数据区、长度容量关系和可写数组要求。
- `append_int_list` 增加 `assigns`，明确允许修改列表数据指针、长度和容量。

## 验证结果

使用重新生成的 `Mbpp_101.c` 验证：

- GCC C11 编译通过。
- C 运行时断言通过。
- Frama-C/WP 能够解析新增 contracts。
- 本样例得到 `18 / 27` 个目标证明。

新增 contracts 使列表辅助函数的 `assigns`、长度和容量相关目标进入 WP 分析，但 `malloc/realloc` 的分配语义、循环终止性、整数容量增长和 `__FC_assert` 前置条件仍有 `Unknown` 或 `Timeout`。

## 当前限制

目前 contracts 仍未对分配失败、整数溢出、`realloc` 失败后的旧指针保留、列表数据初始化和数组内容保持关系进行完整建模。因此本轮结果只能标记为 contract 基础设施进展，不能标记为内存安全形式化证明通过。

## 下一步

优先为 `make_empty_int_list` 和 `make_int_list` 增加可被 Frama-C 33.0 接受的结构体结果建模，然后为 `realloc` 扩容循环增加容量增长不变量和溢出前置条件。
