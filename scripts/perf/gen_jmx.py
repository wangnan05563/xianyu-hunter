#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 XianyuHunter 全接口性能压测 JMX（读扩展 + 受控写）。

输出:
  test_results/jmeter/scripts/xianyu_load_test_reads.jmx   (Tier A 全量只读 + Phase1-4 峰值)
  test_results/jmeter/scripts/xianyu_load_test_writes.jmx  (Tier B 受控写)

认证: WEB_TOKEN 默认从 -Jweb_token=xxx 注入（JMeter __P），不在文件内硬编码密钥。
参数化 ID: 从测试库抽取的真实 ID 作为 TestPlan 变量，避免 404 噪声。
"""
import os

OUT_DIR = "D:/code/otherProjects/17_xianyu/test_results/jmeter/scripts"

# 从测试库抽取的真实 ID（见 inspect 结果）
IDS = {
    # 改用 user_id='default' 的任务，使 WEB_TOKEN 管理令牌(request.state.user_id='default')通过多租户归属校验，headless 下可真正压测任务系列
    "TASK_ID": "t7b2ef2f2",
    "ITEM_ID": "1054852225970",
    "ORDER_ID": "zz_no_order_placeholder",  # orders 表为空 -> 期望 404；缺失订单触发 500(真实健壮性缺陷) 保留为信号
    "TABLE": "tasks",
    "ERRORLOG_ID": "1",
    "SESSION_ID": "7e749a355bcf435fb63155193f41024c",
    "SELLER_ID": "2221340564575",  # 真实存在的卖家(8 个商品)
}

# (method, path, label, [(param,value)...] or None, assert_codes)
READS = [
    ("GET", "/api/stats", "Dashboard统计", None, "200"),
    ("GET", "/api/stats/today", "今日统计", None, "200"),
    ("GET", "/api/stats/business-kpi", "业务KPI", None, "200"),
    ("GET", "/api/stats/trend", "趋势", None, "200"),
    ("GET", "/api/stats/eval-funnel", "评估漏斗", None, "200"),
    ("GET", "/api/stats/price-trend", "价格趋势", None, "200"),
    ("GET", "/api/stats/seller-price-trend", "卖家价格趋势", [("seller_id", "${SELLER_ID}")], "200"),
    ("GET", "/api/prices/histogram", "价格直方图", None, "200"),
    ("GET", "/api/prices/category-stats", "价格分类统计", None, "200"),
    ("GET", "/api/prices/category-comparison", "价格分类对比", None, "200"),
    ("GET", "/api/prices/sold-range", "售出区间", None, "200"),
    ("GET", "/api/prices/bargain-eval", "砍价评估", [("task_id", "${TASK_ID}"), ("current_price", "100")], "200"),
    ("GET", "/api/tasks", "任务列表", [("limit", "20"), ("offset", "0")], "200"),
    ("GET", "/api/tasks/${TASK_ID}", "任务详情", None, "200"),
    ("GET", "/api/tasks/${TASK_ID}/runs", "任务运行记录", None, "200"),
    ("GET", "/api/tasks/${TASK_ID}/precheck", "任务预检", None, "200"),
    ("GET", "/api/orders", "订单列表", [("limit", "20")], "200"),
    ("GET", "/api/orders/${ORDER_ID}", "订单详情", None, "200|404"),
    ("GET", "/api/items/batch", "商品批量", [("ids", "${ITEM_ID}")], "200"),
    ("GET", "/api/items/${ITEM_ID}/summary", "商品摘要", None, "200"),
    ("GET", "/api/evaluations", "评估列表", None, "200"),
    ("GET", "/api/evaluations/latest/${ITEM_ID}", "最新评估", None, "200|404"),
    ("GET", "/api/evaluations/distribution", "评估分布", None, "200"),
    ("GET", "/api/evaluations/auto-collect-stats", "自动采集统计", None, "200"),
    ("GET", "/api/evaluations/feedback/stats", "反馈统计", None, "200"),
    ("GET", "/api/evaluations/threshold-suggestion", "阈值建议", None, "200"),
    ("GET", "/api/evaluations/seller-price-trend", "评估卖家价格趋势", [("seller_id", "${SELLER_ID}")], "200"),
    ("GET", "/api/config", "配置", None, "200"),
    ("GET", "/api/config/raw", "配置原始", None, "200"),
    ("GET", "/api/config/backups", "配置备份", None, "200"),
    ("GET", "/api/config/version", "配置版本", None, "200"),
    ("GET", "/api/config/export", "配置导出", None, "200"),
    ("GET", "/api/config/share", "配置分享", None, "200"),
    ("GET", "/api/menu", "菜单", None, "200"),
    ("GET", "/api/preferences", "偏好", None, "200"),
    ("GET", "/api/prompts", "Prompt列表", None, "200"),
    ("GET", "/api/templates", "模板", None, "200"),
    ("GET", "/api/about", "关于", None, "200"),
    ("GET", "/api/about/check-update", "检查更新", None, "200"),
    ("GET", "/api/notifications", "通知列表", None, "200"),
    ("GET", "/api/notifications/unread_count", "未读计数", None, "200"),
    ("GET", "/api/error-logs", "错误日志", None, "200"),
    ("GET", "/api/error-logs/${ERRORLOG_ID}", "错误日志详情", None, "200|404"),
    ("GET", "/api/logs", "日志", None, "200"),
    ("GET", "/api/logs/search", "日志搜索", None, "200"),
    ("GET", "/api/accounts", "账号", None, "200"),
    ("GET", "/api/accounts/stats", "账号统计", None, "200"),
    ("GET", "/api/anticrawl/strategy", "反爬策略", None, "200"),
    ("GET", "/api/anticrawl/freq/stats", "反爬频率统计", None, "200"),
    ("GET", "/api/anticrawl/fingerprint", "反爬指纹", None, "200"),
    ("GET", "/api/anticrawl/health", "反爬健康", None, "200"),
    ("GET", "/api/vector-admin/status", "向量库状态", None, "200"),
    ("GET", "/api/kb/status", "知识库状态", None, "200|404"),
    ("GET", "/api/kb/versions", "知识库版本", None, "200|404"),
    ("GET", "/api/tunnel/status", "隧道状态", None, "200"),
    ("GET", "/api/maintenance/status", "维护状态", None, "200"),
    ("GET", "/api/batch-refresh/status", "批量刷新状态", None, "200"),
    ("GET", "/api/batch-refresh/history", "批量刷新历史", None, "200"),
    ("GET", "/api/cron/examples", "Cron示例", None, "200"),
    ("GET", "/api/param-calculator/rules", "参数计算器规则", None, "200"),
    ("GET", "/api/db-admin/tables", "DB表列表", None, "200"),
    ("GET", "/api/db-admin/tables/${TABLE}/schema", "DB表结构", None, "200"),
    ("GET", "/api/db-admin/tables/${TABLE}/rows?limit=50", "DB表行", None, "200"),
    ("GET", "/api/chatbot/sessions", "会话列表", None, "200"),
    ("GET", "/api/chatbot/config", "客服配置", None, "200"),
    ("GET", "/api/chatbot/feedback/recent", "近期反馈", None, "200"),
]

# (method, path, label, body or "", assert_codes)
WRITES = [
    ("PUT", "/api/preferences", "偏好UPSERT", '{"perf_test_key":"1"}', "200|404|405"),
    ("POST", "/api/notifications/read_all", "通知全部已读", "", "200|404"),
    ("POST", "/api/chatbot/sessions", "创建会话", '{"title":"perf-test"}', "200|201|422"),
    ("DELETE", "/api/chatbot/sessions/${SESSION_ID}", "删除会话", "", "200|404"),
    ("POST", "/api/maintenance/cache", "清理缓存(dry_run)", '{"target":"temp","dry_run":true}', "200"),
    ("POST", "/api/config/preview", "配置预览", '{"antidetect":{"qps":1.5}}', "200"),
    ("POST", "/api/evaluations/${ITEM_ID}/feedback?feedback=accurate", "提交评估反馈", "", "200|404"),
]

PHASES = [
    ("Phase1-基准测试(10并发/60s)", 10, 5, 60),
    ("Phase2-负载测试(50并发/180s)", 50, 15, 180),
    ("Phase3-压力测试(100并发/180s)", 100, 20, 180),
    ("Phase4-峰值测试(200并发/180s)", 200, 30, 180),
]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def assert_xml(codes: str) -> str:
    # 统一用单条正则 + Matches(test_type=8) 断言响应码，支持 "200|404" 多码
    # （JMeter 多 pattern 默认按 AND 逻辑，会导致 200/404 永不匹配；正则 OR 最稳）
    import re as _re
    code_list = [c.strip() for c in codes.split("|") if c.strip()]
    # test_type=2 = Matches (Perl5 regex, full-match)。注意: 8=Substring(字面,忽略正则),
    # 不能用 8，否则 "^(?:200|404)$" 作为字面子串永远匹配不到响应码。
    regex = "|".join(_re.escape(c) for c in code_list)
    return (
        '        <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="状态码断言" enabled="true">\n'
        '          <collectionProp name="Asserion.test_strings">\n'
        '            <stringProp name="0">' + esc(regex) + '</stringProp>\n'
        '          </collectionProp>\n'
        '          <stringProp name="Assertion.custom_message"></stringProp>\n'
        '          <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>\n'
        '          <boolProp name="Assertion.assume_success">false</boolProp>\n'
        '          <intProp name="Assertion.test_type">2</intProp>\n'
        '        </ResponseAssertion>\n'
        '        <hashTree/>\n'
    )


def read_sampler_xml(ep) -> str:
    method, path, label, params, codes = ep
    out = []
    out.append('        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="' + esc(label) + '">')
    if params:
        out.append('          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">')
        out.append('            <collectionProp name="Arguments.arguments">')
        for pname, pval in params:
            out.append('              <elementProp name="' + esc(pname) + '" elementType="HTTPArgument">')
            out.append('                <boolProp name="HTTPArgument.always_encode">false</boolProp>')
            out.append('                <stringProp name="Argument.name">' + esc(pname) + '</stringProp>')
            out.append('                <stringProp name="Argument.value">' + esc(pval) + '</stringProp>')
            out.append('                <stringProp name="Argument.metadata">=</stringProp>')
            out.append('                <boolProp name="HTTPArgument.use_equals">true</boolProp>')
            out.append('              </elementProp>')
        out.append('            </collectionProp>')
        out.append('          </elementProp>')
    else:
        out.append('          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">')
        out.append('            <collectionProp name="Arguments.arguments"/>')
        out.append('          </elementProp>')
    out.append('          <stringProp name="HTTPSampler.path">' + esc(path) + '</stringProp>')
    out.append('          <stringProp name="HTTPSampler.method">' + method + '</stringProp>')
    out.append('          <boolProp name="HTTPSampler.follow_redirects">true</boolProp>')
    out.append('          <boolProp name="HTTPSampler.auto_redirects">false</boolProp>')
    out.append('          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>')
    out.append('          <boolProp name="HTTPSampler.DO_MULTIPART_POST">false</boolProp>')
    out.append('          <stringProp name="HTTPSampler.embedded_url_re"></stringProp>')
    out.append('          <stringProp name="HTTPSampler.connect_timeout">10000</stringProp>')
    out.append('          <stringProp name="HTTPSampler.response_timeout">30000</stringProp>')
    out.append('        </HTTPSamplerProxy>')
    out.append('        <hashTree>')
    out.append(assert_xml(codes))
    out.append('        </hashTree>')
    return "\n".join(out)


def write_sampler_xml(ep) -> str:
    method, path, label, body, codes = ep
    out = []
    out.append('        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="' + esc(label) + '">')
    if body:
        # 单个无名参数(name="") -> JMeter 将其 value 作为原始请求体发送(最稳的 raw-body 方式)。
        # 注意: 不能用 HTTPSampler.postBody(在高并发+keepalive 下会丢 body，导致后端 422)。
        out.append('          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">')
        out.append('            <collectionProp name="Arguments.arguments">')
        out.append('              <elementProp name="" elementType="HTTPArgument">')
        out.append('                <boolProp name="HTTPArgument.always_encode">false</boolProp>')
        out.append('                <stringProp name="Argument.name"></stringProp>')
        out.append('                <stringProp name="Argument.value">' + esc(body) + '</stringProp>')
        out.append('                <stringProp name="Argument.metadata">=</stringProp>')
        out.append('                <boolProp name="HTTPArgument.use_equals">false</boolProp>')
        out.append('              </elementProp>')
        out.append('            </collectionProp>')
        out.append('          </elementProp>')
    else:
        out.append('          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">')
        out.append('            <collectionProp name="Arguments.arguments"/>')
        out.append('          </elementProp>')
    out.append('          <stringProp name="HTTPSampler.path">' + esc(path) + '</stringProp>')
    out.append('          <stringProp name="HTTPSampler.method">' + method + '</stringProp>')
    out.append('          <boolProp name="HTTPSampler.follow_redirects">true</boolProp>')
    out.append('          <boolProp name="HTTPSampler.auto_redirects">false</boolProp>')
    out.append('          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>')
    out.append('          <boolProp name="HTTPSampler.DO_MULTIPART_POST">false</boolProp>')
    out.append('          <stringProp name="HTTPSampler.connect_timeout">10000</stringProp>')
    out.append('          <stringProp name="HTTPSampler.response_timeout">30000</stringProp>')
    out.append('        </HTTPSamplerProxy>')
    out.append('        <hashTree>')
    out.append(assert_xml(codes))
    out.append('        </hashTree>')
    return "\n".join(out)


def summary_listener_xml(name: str) -> str:
    return (
        '        <ResultCollector guiclass="SummaryReport" testclass="ResultCollector" testname="' + esc(name) + '">\n'
        '          <boolProp name="ResultCollector.error_logging">false</boolProp>\n'
        '          <objProp>\n'
        '            <name>saveConfig</name>\n'
        '            <value class="SampleSaveConfiguration">\n'
        '              <time>true</time><latency>true</latency><timestamp>true</timestamp>\n'
        '              <success>true</success><label>true</label><code>true</code><message>true</message>\n'
        '              <threadName>true</threadName><dataType>true</dataType><encoding>false</encoding>\n'
        '              <assertions>true</assertions><subresults>true</subresults><responseData>false</responseData>\n'
        '              <samplerData>false</samplerData><xml>false</xml><fieldNames>true</fieldNames>\n'
        '              <responseHeaders>false</responseHeaders><requestHeaders>false</requestHeaders>\n'
        '              <responseDataOnError>false</responseDataOnError>\n'
        '              <saveAssertionResultsFailureMessage>true</saveAssertionResultsFailureMessage>\n'
        '              <assertionsResultsToSave>0</assertionsResultsToSave><bytes>true</bytes><sentBytes>true</sentBytes>\n'
        '              <url>true</url><threadCounts>true</threadCounts><idleTime>true</idleTime><connectTime>true</connectTime>\n'
        '            </value>\n'
        '          </objProp>\n'
        '          <stringProp name="filename"></stringProp>\n'
        '        </ResultCollector>\n'
        '        <hashTree/>\n'
    )


def thread_group_xml(name, threads, ramp, duration, samplers_xml):
    return (
        '      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="' + esc(name) + '">\n'
        '        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>\n'
        '        <elementProp name="ThreadGroup.main_controller" elementType="LoopController">\n'
        '          <boolProp name="LoopController.continue_forever">false</boolProp>\n'
        '          <stringProp name="LoopController.loops">-1</stringProp>\n'
        '        </elementProp>\n'
        '        <stringProp name="ThreadGroup.num_threads">' + str(threads) + '</stringProp>\n'
        '        <stringProp name="ThreadGroup.ramp_time">' + str(ramp) + '</stringProp>\n'
        '        <boolProp name="ThreadGroup.scheduler">true</boolProp>\n'
        '        <stringProp name="ThreadGroup.duration">' + str(duration) + '</stringProp>\n'
        '        <stringProp name="ThreadGroup.delay">0</stringProp>\n'
        '        <boolProp name="ThreadGroup.same_user_on_next_iteration">false</boolProp>\n'
        '      </ThreadGroup>\n'
        '      <hashTree>\n'
        + samplers_xml +
        '      </hashTree>\n'
    )


def user_vars_xml():
    items = [
        ("HOST", "127.0.0.1"),
        ("PORT", "8011"),
        ("WEB_TOKEN", "${__P(web_token,)}"),
        ("PROTOCOL", "http"),
    ]
    for k, v in IDS.items():
        items.append((k, v))
    out = ['      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments">',
            '        <collectionProp name="Arguments.arguments">']
    for name, val in items:
        out.append('          <elementProp name="' + name + '" elementType="Argument">')
        out.append('            <stringProp name="Argument.name">' + name + '</stringProp>')
        out.append('            <stringProp name="Argument.value">' + esc(val) + '</stringProp>')
        out.append('            <stringProp name="Argument.metadata">=</stringProp>')
        out.append('          </elementProp>')
    out.append('        </collectionProp>')
    out.append('      </elementProp>')
    return "\n".join(out)


def global_config_xml():
    return (
        '      <ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP 默认配置">\n'
        '        <elementProp name="HTTPsampler.Arguments" elementType="Arguments">\n'
        '          <collectionProp name="Arguments.arguments"/>\n'
        '        </elementProp>\n'
        '        <stringProp name="HTTPSampler.domain">${__P(host,${HOST})}</stringProp>\n'
        '        <stringProp name="HTTPSampler.port">${__P(port,${PORT})}</stringProp>\n'
        '        <stringProp name="HTTPSampler.protocol">${PROTOCOL}</stringProp>\n'
        '        <stringProp name="HTTPSampler.contentEncoding">utf-8</stringProp>\n'
        '        <stringProp name="HTTPSampler.path"></stringProp>\n'
        '        <stringProp name="HTTPSampler.concurrentPool">6</stringProp>\n'
        '        <stringProp name="HTTPSampler.connect_timeout">10000</stringProp>\n'
        '        <stringProp name="HTTPSampler.response_timeout">30000</stringProp>\n'
        '      </ConfigTestElement>\n'
        '      <hashTree/>\n'
        '      <HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="HTTP 请求头管理">\n'
        '        <collectionProp name="HeaderManager.headers">\n'
        '          <elementProp name="" elementType="Header">\n'
        '            <stringProp name="Header.name">Authorization</stringProp>\n'
        '            <stringProp name="Header.value">Bearer ${WEB_TOKEN}</stringProp>\n'
        '          </elementProp>\n'
        '          <elementProp name="" elementType="Header">\n'
        '            <stringProp name="Header.name">Accept</stringProp>\n'
        '            <stringProp name="Header.value">application/json</stringProp>\n'
        '          </elementProp>\n'
        '          <elementProp name="" elementType="Header">\n'
        '            <stringProp name="Header.name">Content-Type</stringProp>\n'
        '            <stringProp name="Header.value">application/json</stringProp>\n'
        '          </elementProp>\n'
        '          <elementProp name="" elementType="Header">\n'
        '            <stringProp name="Header.name">User-Agent</stringProp>\n'
        '            <stringProp name="Header.value">JMeter/5.6.3 XianyuHunter-PerfTest</stringProp>\n'
        '          </elementProp>\n'
        '        </collectionProp>\n'
        '      </HeaderManager>\n'
        '      <hashTree/>\n'
    )


def build_reads_jmx():
    tgroups = []
    for name, th, ramp, dur in PHASES:
        sams = "\n".join(read_sampler_xml(ep) for ep in READS)
        tgroups.append(thread_group_xml(name, th, ramp, dur, sams + summary_listener_xml(name + " 汇总报告")))
    return _wrap(tgroups)


def build_writes_jmx():
    sams = "\n".join(write_sampler_xml(ep) for ep in WRITES)
    tg = thread_group_xml("WritePhase-受控写(20并发/120s)", 20, 10, 120, sams + summary_listener_xml("WritePhase 汇总报告"))
    return _wrap([tg])


def _wrap(thread_groups_xml):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">\n'
        '  <hashTree>\n'
        '    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="XianyuHunter 全接口性能测试(扩展)">\n'
        '      <stringProp name="TestPlan.comments">全接口压测: 读扩展(Phase1-4) + 受控写。web-only 模式(无浏览器/调度器)。认证 Bearer WEB_TOKEN(-Jweb_token 注入)。</stringProp>\n'
        '      <boolProp name="TestPlan.functional_mode">false</boolProp>\n'
        '      <boolProp name="TestPlan.serialize_threadgroups">true</boolProp>\n'
        + user_vars_xml() + '\n'
        '      <stringProp name="TestPlan.user_define_classpath"></stringProp>\n'
        '    </TestPlan>\n'
        '    <hashTree>\n'
        + global_config_xml() +
        "\n".join(thread_groups_xml) + '\n' +
        '    </hashTree>\n'
        '  </hashTree>\n'
        '</jmeterTestPlan>\n'
    )


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    r = build_reads_jmx()
    with open(os.path.join(OUT_DIR, "xianyu_load_test_reads.jmx"), "w", encoding="utf-8") as f:
        f.write(r)
    w = build_writes_jmx()
    with open(os.path.join(OUT_DIR, "xianyu_load_test_writes.jmx"), "w", encoding="utf-8") as f:
        f.write(w)
    print("reads endpoints:", len(READS), "phases:", len(PHASES), "-> xianyu_load_test_reads.jmx")
    print("writes endpoints:", len(WRITES), "-> xianyu_load_test_writes.jmx")
