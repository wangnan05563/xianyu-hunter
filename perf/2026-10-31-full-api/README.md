# perf/2026-10-31-full-api

XianyuHunter 全量 `/api/*`（272 端点）系统化性能测试的一次完整留档：基准 / 压力阶梯 / 30 分钟耐久长跑，含瓶颈定位与优化建议。

| 文件 | 用途 |
|---|---|
| `REPORT.md` | **测试报告**（环境口径、覆盖率对账、三组阶梯、长跑分窗、瓶颈定位表 A/B/C、偏差声明） |
| `OPTIMIZATIONS.md` | **优化建议清单**（20 条，按 数据库/缓存/代码/连接池/部署 分组，每条含具体改动 + 证据 + 量化收益 + 优先级 + 验证方式） |
| `CONCLUSION.md` | **整体结论**（健康度评估、Top 3、短期路线、对目标约束的回执与未达成项） |
| `jmx/*.jmx` | 4 份 JMX 脚本（由 `jmeter-config*.yml` 的 `scenarios` 段经 `gen_jmx.py` 生成，零硬编码） |
| `jmeter-config.yml` / `jmeter-config-v2.yml` | 两轮唯一参数来源；v2 是最终采用口径，把 `soak_mixed.duration_override` 改为 `14400` 即可复跑 4 小时长跑 |
| `tier-rules.json` / `build_scenarios.py` / `emit_config.py` | 端点分层规则与场景/配置生成（换业务 = 改 JSON，不改引擎代码） |
| `endpoint-coverage.json` | 272 端点的分层归属与逐条 `reason`（哪些为什么不压、为什么不出击） |
| `setup_sandbox.py` / `coverage_probe.py` / `aggregate.py` / `patch_and_v2.py` | 沙箱搭建、覆盖率探针、结果聚合、口径修正 |
| `results/` | 10 个阶段的逐请求原始样本（`.jsonl.gz`）、聚合 JSON、阶梯/接口/长跑表、SUT 资源采样 CSV、单发探针 |

执行方式：`jmeter-performance-test` 技能，`mode: python_replay`（本机无 Java/JMeter，自动回退等价回放引擎）；被测实例为隔离沙箱（端口 8011 + SQLite backup 副本库 + 调度器关闭），生产数据未被触碰。

安全说明：配置里只留 `token_file` / `token_env` 的**引用路径**，令牌明文存在于临时目录并已随目录删除；复跑前需重新注入（环境变量 `WEB_TOKEN` 或指向你自己的 token 文件）。
