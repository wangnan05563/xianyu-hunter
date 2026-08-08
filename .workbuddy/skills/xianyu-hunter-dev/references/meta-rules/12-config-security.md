# 配置安全与凭据管理

> 快捷预设 API Key 独立存储、配置字段五层链路覆盖。
>
> 涵盖规范: #70, #87
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #70 快捷预设独立 API Key 存储
每个预设必须有独立凭证槽位（`<prefix>_preset_<preset_id>`），切换预设时原子操作保存/恢复凭证；首次切换时自动迁移全局凭证
- grep: `grep "api_key" config.py` 发现全局单一存储，无 preset 维度区分 → 违规

### #87 配置字段五层链路覆盖
用户可编辑的配置字段必须覆盖五层：DB schema → get_config → update_config → types.ts → Config.tsx，缺一即 Bug
- grep: `grep "ALTER TABLE.*ADD COLUMN" migrations/` 找到新增字段 → 检查五层链路是否齐全
