# 全功能模拟程序设计方案

## 1. 目标概述
该程序旨在提供一个可扩展的端游战斗循环模拟平台，能够：

1. 从剑三客户端的打包资源与解包目录读取技能、奇穴、秘籍、装备等原始数据；
2. 根据任务请求初始化玩家与目标，加载属性、Buff、奇穴增益并执行战斗模拟；
3. 支持自定义 Lua 脚本或游戏内宏描述全新的循环逻辑；
4. 提供异步批量模拟、实时进度查询与结果统计；
5. 对外暴露 HTTP 接口供前端提交任务、查看结果与导出战斗记录。

## 2. 系统架构

```
+-----------------+      +-------------------+      +------------------+
| HTTP Controller | ---> | Task Orchestrator | ---> | Simulation Engine |
+-----------------+      +-------------------+      +------------------+
         |                         |                            |
         v                         v                            v
+-----------------+      +-------------------+      +------------------+
| Resource Loader | <--- | Cache & Registry  | <--- | Lua Runtime Host |
+-----------------+      +-------------------+      +------------------+
         |
         v
+-----------------+
| Client Resource |
| (bin/unpacked)  |
+-----------------+
```

### 2.1 HTTP 控制层
* 使用基于 `Boost.Beast` 或 `cpp-httplib` 的轻量 REST 服务；
* 主要路由：
  * `POST /tasks`：提交模拟请求；
  * `GET /tasks/{id}`：查询进度与结果；
  * `GET /tasks/{id}/detail`：拉取详细战斗记录；
  * `DELETE /tasks/{id}`：取消任务。

### 2.2 任务协调器
* 负责解析用户请求，将其转换为 `Task::Data`；
* 基于 `folly::ThreadPool` 或 `boost::asio::thread_pool` 管理工作线程；
* 每个任务包含 N 次模拟：前 M 次记录详细日志，其余只返回统计信息；
* 维护任务状态机（`Pending`、`Running`、`Finished`、`Cancelled`、`Timeout`）。

### 2.3 模拟引擎
* 提供 `Simulation::run(const Task::Data&)` 入口；
* 关键子系统：
  * **事件队列**：最小堆按时间排序驱动技能、冷却、宏步骤；
  * **技能系统**：`SkillManager` 缓存技能数据并在战斗时读取；
  * **Buff / 奇穴系统**：被动增益在初始化时作用于角色属性；
  * **伤害结算**：统一公式考虑攻击力、增伤百分比、会心、破防等；
  * **宏运行时**：Lua VM 执行自定义脚本或由宏转换生成的 Lua 函数。

## 3. 资源加载流程

1. 启动时读取 `config.json`：
   ```json
   {
     "dirSeasunGame": "D:/JX3",
     "dirUnpacked": "D:/JX3Unpack",
     "clientProfile": "zhcn_hd",
     "threadPoolSize": 8
   }
   ```
2. 根据 `clientProfile` 拼接 bin 路径 `dirSeasunGame/Game/JX3/zhcn_hd/bin/zhcn_hd/bin64`；
3. 调用 `gdi::dataInit(jx3Dir, dirUnpacked)`；
4. `ResourceLoader` 提供以下接口：
   * `Skill loadSkill(uint32_t id)`：访问 `skills.tab`、执行 `GetSkillLevelData`；
   * `Buff loadBuff(uint32_t id)`：访问 `buff.tab`、执行脚本增益；
   * `Item loadEquipment(uint32_t id)`：从 `custom_*` 表读取装备属性；
   * `Talent loadTrait(uint32_t id)`：包装奇穴被动；
5. 所有对象都会同时缓存 UI 记录（`ui_skill.tab` / `ui_buff.tab` 等），以提供图标编号、描述文本等展示信息。

## 4. 任务输入结构

```json
{
  "school": "太虚剑意",
  "duration": 360,
  "times": 500,
  "detailCount": 5,
  "latency": { "network": 30, "keyboard": 40 },
  "attributes": { "attack": 12345, "crit": 0.35, ... },
  "talents": [6201, 6202, ...],
  "recipes": [723001, 723002],
  "buffs": [812345, 856789],
  "equipment": { "weapon": 101234, "armor": [201111, 201112], ... },
  "fight": {
    "method": "lua",
    "data": "function Init(player) ... end"
  }
}
```

* `method` 支持 `builtin`（默认循环）、`lua`（自定义 Lua）、`macro`（游戏内宏数组）。
* 请求会在服务端生成任务 ID 并异步执行。

## 5. 模拟执行步骤

1. **初始化角色**：
   * 实例化 `Player`，加载基础属性与装备；
   * 调用 `skillLearn`、`skillActive` 激活奇穴与秘籍；
   * 应用初始 Buff 并将加成写入 `PlayerAttributes`。
2. **构建循环环境**：
   * 若存在 `fight.method == "lua"`，将脚本缓存到 `LuaRuntime` 并生成 `customLua`；
   * 若为宏数组，先转换为 Lua 模板再加载；
   * 注册默认事件（普攻、宏步骤、触发器等）。
3. **运行事件队列**：
   * `Event::run()` 驱动时间推进，直至战斗时长或脚本结束；
   * 每次技能命中、伤害结算都会写入 `FightLog`。
4. **生成结果**：
   * 统计总伤害、DPS、技能占比、会心等指标；
   * `detailCount` 内的模拟保留完整 `FightLog` 以供分析；
   * 其余模拟只返回汇总数据。

## 6. 统计与查询

* `TaskResult` 保存每次模拟的 DPS 列表，并提供：
  * 平均值、标准差、95% 置信区间；
  * 每技能伤害占比；
  * 进度信息（已完成次数、耗时、预计剩余时间）。
* 查询接口：
  * `GET /tasks/{id}`：返回 `status`、`progress`、`dpsSummary`；
  * `GET /tasks/{id}/detail`：支持分页返回详细 `FightLog`；
  * `GET /tasks/{id}/chart`：提供按技能分类的汇总数据。

## 7. 日志与监控

* 使用 `spdlog` 记录任务创建、资源加载、错误信息；
* 对关键指标（任务耗时、成功率、Lua 报错等）输出 Prometheus metrics；
* 在 Lua 脚本执行失败时捕获异常并返回友好的错误信息。

## 8. 扩展性考虑

* **模块化资源层**：`ResourceLoader` 与 `CacheRegistry` 可替换为其他数据源（如私服或测试服）；
* **脚本沙箱**：Lua 环境只暴露必要接口，限制 IO 和危险函数；
* **插件机制**：提供 `plugin` 目录允许第三方扩展自定义 Buff 或统计逻辑；
* **并行扩展**：任务调度器支持调整线程池规模，未来可改用分布式队列；
* **可视化前端**：借助 `ui_*` 表信息搭建图形界面，展示技能图标、奇穴选择。

## 9. 开发里程碑

1. **基础设施**：完成配置加载、资源初始化、HTTP 接口；
2. **核心模拟**：实现事件队列、技能系统、伤害公式；
3. **自定义循环**：接入 Lua VM 与宏转换；
4. **统计与查询**：实现任务状态跟踪与结果统计；
5. **前端集成**：输出支持图标和描述字段的 JSON 响应；
6. **运维支持**：添加日志、监控与异常处理策略。

## 10. 安全与合规

* 对上传的 Lua 脚本执行超时限制与沙箱隔离，防止恶意代码；
* 校验客户端资源路径，确保只访问配置允许的目录；
* 对外接口增加身份验证（Token/签名）与速率限制，避免滥用。

该设计方案覆盖了技能数据加载、奇穴增益应用、自定义循环模拟以及批量任务管理，能够支撑多种战斗循环的精确模拟与分析。
