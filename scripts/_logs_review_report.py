# -*- coding: utf-8 -*-
"""Generate the detailed Logs Review Markdown report from the intermediate JSON."""
import json, datetime, collections

IN = "scripts/_logs_review_intermediate.json"
NOW = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = f"docs/logs-reports/logs-review-report-{NOW}.md"

with open(IN, encoding="utf-8") as f:
    data = json.load(f)

meta = data["meta"]
issues = data["issues"]
stacks = data["stacktraces"]

warn_issues = [i for i in issues if i["severity"] == "WARNING"]
err_issues = [i for i in issues if i["severity"] == "ERROR"]

# ---- aggregate a few cross-cutting metrics ----
dns_total = sum(i["frequency"] for i in warn_issues if "ERR_NAME_NOT_RESOLVED" in i["template"] or "network_transient" in i["template"])
disk_full = sum(i["frequency"] for i in warn_issues if "database or disk is full" in i["template"])
business_kpi = next((i for i in warn_issues if "business_kpi" in i["template"]), None)
addcookie_miss = sum(i["frequency"] for i in warn_issues if "add_cookies" in i["template"])
dom_timeout = sum(i["frequency"] for i in warn_issues if "DOM 回退查找卡片超时" in i["template"])
session_invalid = sum(i["frequency"] for i in warn_issues if "session 层已标记失效" in i["template"] or "无法获取 _m_h5_tk" in i["template"])
tunnel_err = sum(i["frequency"] for i in err_issues if "内网穿透" in i["template"])
renew_err = sum(i["frequency"] for i in err_issues if "续期连续失败" in i["template"] or "连续" in i["template"] and "续期失败" in i["template"])
kb_timeout = sum(i["frequency"] for i in err_issues if "知识库定时更新超时" in i["template"])

# ---- curated master findings ----
# severity: Critical/High/Medium/Low ; priority: P0/P1/P2/P3
findings = [
    dict(id="F1", title="磁盘/数据库写失败：database or disk is full（资源/磁盘泄漏）",
         severity="Critical", priority="P0", category="资源泄漏 / 数据丢失风险",
         scope="worker:_finalize_run / xianyu.db（events 表）；根因在磁盘 93% + chromadb 4.1G",
         evidence=f"WARNING 共 {disk_full} 次（2026-08-15 21:45–22:14 集中爆发，3 个任务轮流失败）；磁盘 D: 已用 93%（剩 9.3G/131G）；data/ 共 4.4G，其中 data/chromadb 占 4.1G。",
         root="SQLite 写搜索事件时返回 SQLITE_FULL。根因是磁盘空间被 chromadb 向量库持续增长吃满、缺乏保留/压缩策略；写失败导致搜索事件（遥测）被静默丢弃。",
         strategy="配置 + 监控 + 代码",
         fix=("① 运维：立即回收磁盘（清理 chromadb 中已下架商品的过期向量 / 启用 chromadb 保留策略与 compaction；临时扩容 D:）。\n"
              "② 代码：事件写入失败不应进入无限重试循环——改为‘本地队列 + 丢弃告警’，并记录一次 ERROR 级告警（当前是 WARNING 且每任务每轮都打，反而淹没真正信号）。\n"
              "③ 监控：新增磁盘使用率监控，≥85% 即告警（见 F10）。\n"
              "④ 排查 xianyu.db 是否开启 WAL + 自动 checkpoint，避免 WAL/rollback 临时文件加剧空间压力。")),
    dict(id="F2", title="目标站点 DNS 持续解析失败（net::ERR_NAME_NOT_RESOLVED）——采集链路整体不可用",
         severity="High", priority="P0", category="环境/网络（核心阻断）",
         scope="collection_service / collector._detail / collector._search / token_renewer",
         evidence=f"WARNING 约 {dns_total} 次（network_transient + 详情页/搜索/token 刷新均报 ERR_NAME_NOT_RESOLVED），30 分钟窗口内峰值达 100 次；与 F4 叠加导致 6 天零有效采集。",
         root="goofish.com 在运行环境内无法解析（DNS 失败），并非偶发瞬时故障。所有依赖导航/接口的请求全部失败，采集、token 刷新、自动重登全部被阻断。",
         strategy="代码 + 监控",
         fix=("① 代码：将‘瞬时网络错误’与‘DNS 解析失败（持续）’区分——连续 K 次 ERR_NAME_NOT_RESOLVED 即判定‘站点不可达’，停止逐条 item/keyword 的重试轰炸，改为单次明确告警 + 暂停采集。\n"
              "② 增加启动期 DNS/连通性健康检查（解析 www.goofish.com），不通则启动即给出可操作提示而非运行 6 天后才发现。\n"
              "③ 监控：站点不可达持续 >5min 触发 P0 告警并通知运维/用户。\n"
              "④ 若为沙箱/无外网环境，应在配置中显式关闭采集并在 UI 提示，而非持续刷 WARNING。")),
    dict(id="F3", title="会话永久失效 / Token 续期失败死循环（state_check）",
         severity="High", priority="P1", category="状态一致性（业务流程中断）",
         scope="login_orchestrator / token_renewer / cookie_rotator / worker",
         evidence=f"WARNING ‘Token 续期失败（第 N 次），session 层已标记失效’ {session_invalid} 次；ERROR ‘续期连续失败…触发自动重登’ {renew_err} 次；token_renewer 日志显示‘会话失效状态未恢复，第 8 次检查后退避 600s’；自 2026-08-14 17:35 起至 2026-08-20 15:28 持续 6 天。",
         root="_m_h5_tk 自启动即缺失/过期，自动重登因 F2（DNS 不通）无法完成，形成‘失效→重试→失败→再失效’循环；worker 每轮均‘跳过等待续期’，但续期永远不会成功。",
         strategy="代码 + 监控",
         fix=("① 代码：自动重登增加冷却/上限——连续 N 次失败后停止自动重登，改为单次高优告警 + 引导用户手动重登（notifier 已支持 system.error 推送，应在此触发，而非仅 DEBUG）。\n"
              "② 当会话已知失效时，worker 进入‘静默等待’而非每轮都打 INFO‘跳过本轮’（见 F11）。\n"
              "③ 监控：会话失效持续 >30min 触发告警，提示用户重新登录。")),
    dict(id="F4", title="business_kpi 分母为 0 日志高频刷屏（warning_noise）",
         severity="Low", priority="P2", category="日志噪声",
         scope="web.routes.business_kpi:_compute_business_kpi:276",
         evidence=f"WARNING {business_kpi['frequency'] if business_kpi else 0} 次（全量第一），每 ~5 分钟缓存预热触发一次。",
         root="‘近 30 天无订单记录’属正常初始态，却被当作 WARNING 每次计算都打印，无副作用但严重淹没日志。",
         strategy="代码（降频/降级）",
         fix=("① 仅在‘分母从非 0 变为 0’或状态变化时记录一次；或用冷却时间（如 6h 一条）限制。\n"
              "② 改为 DEBUG 或仅在确实有异常（抢单已触发但订单采集落空）时 WARNING。")),
    dict(id="F5", title="Cookie 注入未落地日志冗余且含无害项（warning_noise）",
         severity="Low", priority="P3", category="日志噪声 + 误报",
         scope="infra.browser:add_cookies:475/492、_retry_missing_cookies:640/657",
         evidence=f"add_cookies 相关 WARNING 共 {addcookie_miss} 次；同一调用必成对打印‘尝试显式属性重试’+‘显式属性重试后仍缺失’；其中 xlly_s 缺失为无害（追踪 cookie，非身份 cookie）。",
         root="每次注入都打两条；xlly_s 这种已知无害 cookie 被当异常告警，制造噪声并掩盖真正重要的 _m_h5_tk/_m_h5_tk_enc 缺失。",
         strategy="代码（合并/过滤）",
         fix=("① 将‘重试’与‘仍缺失’合并为单条结构化日志（含重试结果）。\n"
              "② 维护‘已知无害 cookie 白名单’（xlly_s 等），命中则不告警。\n"
              "③ 仅当关键身份 cookie（_m_h5_tk*、cookie2、unb 等）缺失时才 WARNING，并关联 F3 会话失效。")),
    dict(id="F6", title="DOM 回退查找卡片超时放弃（retry_failure，下游于 F2/F3）",
         severity="Medium", priority="P1", category="重试耗尽（性能浪费）",
         scope="collector._search:_collect_dom_cards:963",
         evidence=f"WARNING 共 {dom_timeout} 次（按 keyword 拆分多条），每次等待 30s 超时后放弃。",
         root="会话失效后页面被重定向到闲鱼首页，DOM 回退必然失败；仍每次等待满 30s 超时，浪费时间且刷 WARNING。",
         strategy="代码",
         fix=("① 进入 DOM 回退前先校验当前 URL 是否为搜索结果页，已被重定向到首页则直接跳过（日志降为 DEBUG）。\n"
              "② 会话已知失效时完全跳过 DOM 回退（与 F3/F11 联动）。\n"
              "③ 控制单 keyword 的 DOM 回退次数上限，避免重复超时。")),
    dict(id="F7", title="内网穿透（Tailscale）启动失败被记为 ERROR 并打印 38 行堆栈",
         severity="Medium", priority="P2", category="级别误判 + 堆栈噪声",
         scope="web.startup:_run_tunnel_autostart:771/1541、tunnel_service/TailscaleProvider",
         evidence=f"ERROR {tunnel_err} 次，每次附带 38 行完整 traceback；异常为 RuntimeError('请先打开并登录 Tailscale…')。",
         root="tunnel.auto_start=True 但 Tailscale 未安装/未登录，属‘可预期的未配置状态’，却被 logger.error + 抛栈，误导为系统故障。",
         strategy="代码（降级 + 抑制堆栈）",
         fix=("① 该情况降级为 WARNING，且仅记录 message，不打印完整 traceback（使用 logger.warning(...) 而非 error+exception）。\n"
              "② 尊重配置开关：auto_start 关闭或 provider 不可用时静默跳过。\n"
              "③ 若确需告警，合并为单次并提示如何启用，而非每次启动都打。")),
    dict(id="F8", title="知识库定时更新超时 >600s（performance）",
         severity="Medium", priority="P2", category="性能瓶颈",
         scope="chatbot.kb_refresh_scheduler:_refresh_job_sync:98",
         evidence=f"ERROR {kb_timeout} 次（‘知识库定时更新超时（>600s）’）。",
         root="KB 刷新（embedding/重建索引）耗时超 600s，可能与 chromadb 体积膨胀（4.1G，F1）或单批过大、无进度日志有关。",
         strategy="代码 + 性能",
         fix=("① 增加分片/增量刷新，避免全量重建；记录每阶段耗时（计时日志）。\n"
              "② 设定硬超时并告警，超时不阻塞主进程。\n"
              "③ 与 F1 联动：审计 chromadb 向量保留策略，清理僵尸向量以缩短刷新时间。")),
    dict(id="F9", title="详情页会话失效检测（home_title_redirect）与冗余 INFO 刷屏",
         severity="Low", priority="P3", category="日志噪声 / 冗余",
         scope="collector._detail:_mark_detail_session_invalid、worker:_search_phase/_dedup_and_limit",
         evidence="WARNING ‘详情页检测到会话失效（home_title_redirect）’ 43 次；INFO ‘[Task X] 会话已失效…跳过本轮搜索’ + ‘全部已看过，本轮跳过’ 每 ~1–2 分钟成对出现，6 天累计数千行。",
         root="会话已知失效时，仍对每个 detail/item 走完整‘检测→返回 None’流程并打 INFO，制造海量冗余日志，掩盖真实信号。",
         strategy="代码（去重/降级）",
         fix=("① 会话失效状态做全局缓存，失效期间 detail/搜索直接短路返回，避免逐条 goto 与重复 INFO。\n"
              "② ‘跳过本轮/全部已看过’降级为 DEBUG，或按任务每 N 分钟合并一条。\n"
              "③ page.unroute 超时（74 次）同样降级为 DEBUG。")),
    dict(id="F10", title="监控告警机制缺失（系统性）",
         severity="High", priority="P1", category="可观测性",
         scope="全局",
         evidence="日志中存在磁盘写满（F1）、站点不可达（F2）、会话失效 6 天（F3）等 P0/P1 事件，但全程仅靠被动刷 WARNING/ERROR，无任何阈值告警/收敛，问题潜伏 6 天无人知。",
         root="缺乏指标化监控与告警收敛：重复异常被当作独立事件刷屏，真正需要人工介入的 P0 反而被噪声淹没。",
         strategy="监控",
         fix=("① 磁盘使用率 ≥85% 告警（F1）。\n"
              "② 站点不可达持续 >5min 告警（F2）。\n"
              "③ 会话失效持续 >30min 告警 + 引导重登（F3）。\n"
              "④ 同类 WARNING 做时间窗聚合（如 5min 内同模板 >N 条则合并为一条摘要告警），避免刷屏。\n"
              "⑤ 关键指标（采集成功率、续期成功率）接入 dashboard。")),
    dict(id="F11", title="日志质量：未格式化的 %s 占位符",
         severity="Low", priority="P3", category="日志质量",
         scope="web.startup:_restore_session_on_startup:1083",
         evidence="启动日志出现字面量 ‘启动会话恢复成功: user_id=%s’，%s 未被替换——说明该 logger 用 %-style 但参数缺失（或混用 .format）。",
         root="日志调用参数不匹配，输出失真，影响问题定位。",
         strategy="代码",
         fix=("① 修正该 logger 调用，补齐参数或改为 f-string/正确 % 参数。\n"
              "② 建议统一日志格式化风格，避免 % 与 {} 混用。")),
]

sev_order = {"Critical":0,"High":1,"Medium":2,"Low":3}
findings.sort(key=lambda x: (sev_order[x["severity"]], x["priority"]))

def tbl_row(i):
    return (f"| {i['issue_id']} | {i['severity']} | {i['type']} | {i['priority']} | "
            f"{i['frequency']} | {i['max_window']} | {i['module']}:{i['func']}:{i['line']} | "
            f"{i['template'][:90].replace('|','/')} |")

L = []
L.append("# 后台系统日志分析报告（Logs Review）")
L.append("")
L.append(f"> 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
L.append(f"> 分析模式：**全量**（无基线，首次运行）  ")
L.append(f"> 日志文件：`run.stdout.log`")
L.append("")
L.append("## 一、日志摘要（元信息）")
L.append("")
L.append("| 指标 | 数值 |")
L.append("|------|------|")
L.append(f"| 总行数 | {meta['total_lines']:,} |")
L.append(f"| 成功解析（WARNING/ERROR/CRITICAL） | {meta['matched']:,} |")
L.append(f"| WARNING 原始行数 | {meta['warning_raw']:,} |")
L.append(f"| ERROR 原始行数 | {meta['error_raw']:,} |")
L.append(f"| CRITICAL 原始行数 | 0 |")
L.append(f"| 去重后的问题模板数 | {len(issues)} |")
L.append(f"| 异常堆栈（traceback）数 | {meta['traceback_count']} |")
L.append(f"| WARNING 模板数 | {len(warn_issues)} |")
L.append(f"| ERROR 模板数 | {len(err_issues)} |")
L.append("")
L.append("**整体结论（根因故事）**：系统在 2026-08-14 17:35 启动后，会话即处于失效状态"
         "（`_m_h5_tk` 缺失/过期），而目标站点 `goofish.com` 在运行环境内 DNS 解析持续失败"
         "（`net::ERR_NAME_NOT_RESOLVED`），导致 token 刷新与自动重登永远无法成功，形成"
         "‘失效→重试→失败’死循环。叠加磁盘使用率达 93%（`data/chromadb` 占 4.1G）引发的"
         " `database or disk is full` 写失败，**采集链路已连续 6 天零有效产出**。日志层面同时存在"
         "严重的噪声问题（business_kpi 分母为 0 刷屏 648 次、Cookie 注入冗余对、INFO 跳过日志数千行），"
         "以及级别误判（Tailscale 未配置被记为 ERROR 并打印 38 行堆栈）。")
L.append("")
L.append("## 二、WARNING 分类表（全量，按频率/优先级）")
L.append("")
L.append("| ID | 级别 | 类型 | 优先级 | 次数 | 30min峰 | 来源模块:函数:行 | 消息模板（归一化） |")
L.append("|----|------|------|--------|------|---------|----------------------|------------------------|")
for i in warn_issues:
    L.append(tbl_row(i))
L.append("")
L.append("## 三、ERROR 与异常堆栈")
L.append("")
L.append("| ID | 级别 | 类型 | 优先级 | 次数 | 来源模块:函数:行 | 消息模板（归一化） |")
L.append("|----|------|------|--------|------|----------------------|------------------------|")
for i in err_issues:
    L.append(tbl_row(i))
L.append("")
L.append(f"**异常堆栈统计**：共 {len(stacks)} 处 ERROR 后附带 traceback，其中：")
L.append(f"- `内网穿透自动启动失败`（Tailscale RuntimeError）：{tunnel_err} 次，每次 38 行完整堆栈（F7，级别误判+堆栈噪声）。")
L.append(f"- `续期连续失败…触发自动重登`：{renew_err} 次，无附带堆栈（仅 ERROR 行，F3）。")
L.append(f"- `知识库定时更新超时（>600s）`：{kb_timeout} 次，无附带堆栈（F8）。")
L.append(f"- `连续 N 次续期失败，触发重新登录`：1 次（F3）。")
L.append("")
L.append("## 四、关键发现与修复方案（严重程度 / 优先级 / 策略）")
L.append("")
L.append("> 严重程度：Critical > High > Medium > Low；优先级：P0（立即）> P1（本周）> P2（迭代）> P3（择机）。")
L.append("")
for f in findings:
    L.append(f"### {f['id']} · {f['title']}")
    L.append("")
    L.append(f"- **严重程度**：`{f['severity']}`　**优先级**：`{f['priority']}`　**类别**：{f['category']}")
    L.append(f"- **影响范围**：{f['scope']}")
    L.append(f"- **证据**：{f['evidence']}")
    L.append(f"- **根因**：{f['root']}")
    L.append(f"- **修复策略**：{f['strategy']}")
    L.append(f"- **具体建议**：")
    for line in f["fix"].split("\n"):
        if line.strip():
            L.append(f"  - {line.strip()}")
    L.append("")
L.append("## 五、监控告警完善建议（汇总）")
L.append("")
L.append("| 监控项 | 触发条件 | 级别 |")
L.append("|--------|----------|------|")
L.append("| 磁盘使用率 | ≥85%（当前 93%） | P0 |")
L.append("| 站点不可达 | goofish.com DNS/连通性失败持续 >5min | P0 |")
L.append("| 会话失效 | _m_h5_tk 缺失持续 >30min | P1 |")
L.append("| 知识库刷新 | 单次 >600s | P1 |")
L.append("| 同类日志刷屏 | 5min 内同模板 WARNING >20 条 → 聚合为单条摘要告警 | P2 |")
L.append("| 采集成功率 | 滚动窗口成功率 <阈值 | P1 |")
L.append("")
L.append("## 六、凭据安全检查")
L.append("")
L.append("- 扫描 `token/password/secret/api_key/bearer/长 hex` 等模式：**未发现明文凭据泄露**。")
L.append("- 发现 1 处日志质量问题：`web.startup:_restore_session_on_startup` 打印字面量 `user_id=%s`"
         "（% 占位符未替换，参数缺失/格式化风格混用），见 F11。不影响安全，但影响排障。")
L.append("- 报告中已对所有 item id、task id、req id 做 `{hex}/{task}/{req}` 归一化脱敏。")
L.append("")
L.append("## 七、基线快照状态")
L.append("")
L.append("- 本次为**全量模式**（配置 `baseline_log` 为空），未做增量对比。")
L.append("- 建议：将本轮作为基线快照（复制 `run.stdout.log` 至 `logs/baselines/`），下次运行切换增量模式，"
         "仅关注新增 WARNING/ERROR，量化优化效果。")
L.append("")
L.append("---")
L.append("*本报告由 logs-review 技能生成，问题分类依据 `config.yaml` 的 side_effect / classify 规则，"
         "部分高频噪声经人工复核已上调严重程度（如 F2 站点不可达、F3 会话死循环）。*")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))

print("report written:", OUT)
print("findings:", len(findings), "warn_templates:", len(warn_issues), "err_templates:", len(err_issues))
