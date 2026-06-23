# cm_coverage.h 模板（正确的 .h/.c 分离模式）

此目录下有两个文件：
- `cm_coverage.h` — 宏定义 + extern 声明（无变量定义）
- `cm_coverage.c` — 变量定义 + 函数实现

## 为什么分离？

头文件中直接定义变量（`int x = 0;`）会导致：
- 多文件 include 时链接器报 `multiple definition`
- static 变量每个编译单元独立副本，extern 引用报 L6218E
- volatile 与 memset 冲突

正确做法：.h 只放声明和宏，.c 放定义。

## 配置要点

- `COV_TOTAL_STUBS` 必须 >= 所有模块最大桩 ID + 1
  - MQTT: STMT 100-500, BRANCH 1100-1332
  - HTTP: STMT 200-437, BRANCH 2000-2211
  - EXT:  STMT 0-53, BRANCH 1100+
  - 推荐设为 2500
- `COV_BRANCH_START` 必须与插桩脚本的 branch_id 起始值一致
