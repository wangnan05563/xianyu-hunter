# AI Service Configuration Coding Standards
> This file archives coding standards for AI service configuration in xianyu-hunter-dev.
> Master index: [SKILL.md](../../../SKILL.md) step index, meta-rules: [meta-rules.md](../../../references/meta-rules.md).

---

### step 214: Model Name Case-Sensitivity Standard [Mandatory] v4.43

**Background**: AI service preset model names must match vendor official API docs exactly (including case). DeepSeek's deepseek-v4-flash must be all lowercase. Baidu's ERNIE-Speed-8K must match case precisely. Wrong case causes API 400 errors.

**Problem**: Preset model names inconsistent with official docs (wrong case/spelling), no unified validation.

**Standard**:

1. All preset model names (PRESETS / EMBEDDING_PRESETS) must match vendor official API documentation **character-for-character** (including case)
2. When adding presets, copy model names from official docs, never type manually
3. Model name changes must update: (a) frontend constants.ts presets, (b) backend config.py defaults (if any), (c) related test cases
4. Model names are **hard constraint constants**,禁止 runtime dynamic concatenation or modification
5. Model name capability check functions (e.g., _is_vision_capable) must use case-insensitive matching (.lower()) since vendors have different case strategies

**Config-driven**: Parameters managed in config.yaml model_names node, including case_sensitive_check (default True), official_docs_urls (vendor doc URL dictionary).

**Applicable**: All LLM / Embedding preset model name fields.
**Not applicable**: User-custom-input model names (format validation only, not value validation).

**Signal**:
- grep presets in constants.ts finds model names inconsistent with official docs -> CRITICAL
- _is_vision_capable etc. not using .lower() -> HIGH

**Historical lesson**: deepseek-chat correct but deepseek-v4-flash must be all lowercase; Baidu ERNIE-Speed-8K not ernie-speed-8k; Zhipu glm-4-flash all lowercase.

---

### step 215: Config Input Persistence and Reflection Standard [Mandatory] v4.43

**Background**: All input fields on frontend AI config page (base_url, model, vision_model, embedding_base_url, embedding_model, embedding_dimensions) must persist to backend (.env / keyring) and reflect correctly after page refresh. API Key reflected via masked value (****xxxx), other fields reflected with original values.

**Problem**: Some input values only in frontend state, not persisted to backend; lost after refresh; or masked values used for non-secret fields.

**Standard**:

1. **Persistence**: All config input values must persist to backend immediately on user modification (via PUT/PATCH endpoint), not depend on secondary actions (like "test connection" button) to save
2. **Reflection**: Backend GET endpoint must return all config field values (API Key masked), frontend setConfig must populate each field correctly
3. **API Key Masking Contract**:
   - Backend GET returns: pi_key: "****xxxx" (masked)
   - Frontend password input shows masked value (user can toggle visibility)
   - Frontend PUT sends: if value starts with **** -> backend recognizes "unchanged", skips update
   - Frontend PUT sends: if value is empty string -> backend recognizes "clear", deletes keyring entry
   - Frontend PUT sends: if value is non-masked string -> backend stores in keyring
4. **Non-secret fields**: base_url, model, vision_model, embedding_* must reflect original values, never masked
5. **Preset switch**: pplyPreset only sends base_url/model/vision_model, not api_key; backend PUT response must echo full config (including masked api_key)

**Config-driven**: Parameters managed in config.yaml config_persistence node, including persist_on_change (default True), mask_key_prefix (default "****"), mutation_response_echo (default True).

**Applicable**: All frontend pages with config inputs (AI config, notification channel config, proxy config, etc.).
**Not applicable**: One-time operation forms (like "test connection" does not save).