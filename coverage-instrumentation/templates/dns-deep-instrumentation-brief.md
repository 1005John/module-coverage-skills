# DNS 底层插桩指令模板

当 AT 层插桩覆盖率饱和时，需要对底层实现文件追加插桩。

工作流: AT 层饱和 → 确认底层文件在 .mak 中 → 分配桩 ID → 插桩 → 更新 extern.c → 清理编译 → 验证

Step 1: dir /s /b D:\ML307R\SDK\onemo\*dns*.* 查找底层文件。先确认文件在 .mak 构建列表中（findstr /i "cm_async_dns" *.mak），否则是死代码。

Step 2: 分配桩 ID（避免与已有模块重叠）。例: API 层 stmt=800-899, branch=3200-3299。

Step 3: 插桩模板 - #define CM_COVERAGE_ENABLE + #include cm_coverage.h + #undef + 本地计数器 + cm_cov_is_hit() 桥接 + #define COV_* 宏。

Step 4: 更新 cm_atcmd_extern.c（extern + sprintf + buffer 扩大）。

Step 5: COV_TOTAL_STUBS >= 最大桩 ID + 1。

Step 6: 删 .lib + .o + pack_c.via，增量编译。

Step 7: AT+COVERAGE? 验证新模块显示，执行命令后桩数 > 0。
