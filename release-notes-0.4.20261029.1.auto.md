# Release 0.4.20261029.1

（自动生成的发布说明，来自 git 提交记录；正式发布前请替换为正式说明。）

852fedec feat(tests): 按 T02796 裁决「按建议」落地视觉像素基线门禁
1a387feb feat(config): 按 T02571 裁决把配置保存改为按页段提交
572e5795 feat(config): 按 T02572 裁决 D-5 落地字段级脏检测与跨页草稿保留
0e9b00ef refactor(config): 按 T02571 裁决 D-6 把 DiffPreviewModal 与 configStore 解耦
c0b49477 feat(about): 按 T02593 裁决填回两个真实外链（社区→仓首页、报告问题→Issues）
4a1a67cb feat(items): 按 T02661 裁决「方案1」让 facets 随同列表筛选收缩
ef5da29e feat(ai): 按 T02891 裁决 A 把 chatbot/RAG/Agent/远程 Embedding/价格解读纳入 AI 总开关
59841080 test(menu): D-9 删独立入口后把 Python 侧菜单计数下限同步为 28
940981e6 fix(items): 按 T02968 裁决 B 给采集写侧补 user_id 归属（首采者持有）
2c07140d refactor(tasks): 按 T02963 裁决把 mode 默认值归一到 API 契约，domain 改必填
38abb989 feat(orders): 告警深链补「今日（UTC）」窗口，Orders 页消费并显式标注
a031ce9a docs(stats): 写明「今日」= UTC 自然日及其与 AI 用量本地日的差异（T02734 裁决 A）
78b6e3e3 docs(anticrawl): D-10 裁决落地，策略卡文案从「待裁决」改为终态说明
7fcbcf75 refactor(chatbot): 按 D-9 裁决删除向量库维护独立页，入口收敛到客服配置 Tab
5b5e2acf fix(db-admin): 按 D-8 裁决关闭覆盖导入，删除 INSERT OR REPLACE 分支
43bc70f9 docs(notifications): 分类表补 price 并标明三类保留分类无写入点（T02812 裁决 A）
ceec08b7 feat(ai): 关总开关时三个推理端点退回规则解析，硬失败只留 test-connection（T02947 裁决 A）
533c0f64 chore: 更新版本号并添加 GitHub 一键发布脚本配置
9aa64c55 feat(orders): 订单列表补 start_time/end_time 日期区间参数（T02829 ①，口径中立部分）
5738cb84 feat(evaluations): 筛选改完 300ms 自动查询，商品ID 仍走回车/失焦（T02669）
