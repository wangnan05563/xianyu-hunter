# 模式 AO：release 构建路径一致性测试

> 配置节点：`config.yaml#mode_ao_release_build_path`
> 对应：`xianyu-hunter-dev` 规范 29/30/33；审查 `xianyu-frontend-code-review` F-REVIEW-248 / `xianyu-backend-code-review` B-REVIEW-342。

### 触发关键词
- 构建产物路径 / release 集中化 / SPA 单一来源
- 陈旧 dist 残留 / dist\xianyu-hunter / 前端白屏旧 chunk
- 打包 SPA 不一致 / 安装包含多份 SPA

### 步骤 0：加载配置
读取 `config.yaml#mode_ao_release_build_path` 段。禁止硬编码任何路径/模式/严重级。

### 步骤 1：vite 编译产物集中化验证（规范 29 / F-REVIEW-248）
1. `frontend/vite.config.ts` 的 `build.outDir` 必须等于 `vite_out_dir_expected`（`release/spa`），禁止写死 `frontend/dist` / `backend/.../static/spa` 等散落目录。
2. `base` 必须来自配置（`/xianyu/`），且前端导航/资源引用基于 `import.meta.env.BASE_URL` 派生（见规范 23）。

### 步骤 2：SPA 单一来源验证（规范 30 / F-REVIEW-248 / B-REVIEW-342）
1. 安装包 `release/xianyu-hunter/static/spa` 必须只来自 vite 权威输出 `release/spa`。
2. 构建脚本（build-exe.ps1 5.1）拷 `backend/.../static` 等次级目录时，必须先排除 `spa` 子目录，严禁第二副本混入（`spa_single_source.forbid_secondary_copy_dirs`）。
3. 后端 `app.py` 伺服 SPA 路径必须 `get_project_root() / "release" / "spa"`，禁止 `parents[3]` 魔法数、禁止 `backend/.../static/spa` 兜底目录。

### 步骤 3：零陈旧残留验证（规范 29 / 33）
1. 按 `residual_scan.forbidden_patterns` + `scan_globs` grep，确认无 `dist\xianyu-hunter` / `dist\XianyuHunter-Setup` / `release/xianyu-hunter/static/spa` 等陈旧引用（应清零）。

### 步骤 4：七处路径引用对齐（规范 29 判断逻辑）
变更输出根 / base path 时，按 `alignment_points` 清单逐项核对 vite outDir / build-exe --distpath / installer OutputDir / 部署复制源 / app.py 伺服路径 / 子脚本默认路径 / cleanup+gitignore 是否同步。

### 跨技能校验
- `xianyu-hunter-dev` 规范 29/30/33
- `xianyu-frontend-code-review` F-REVIEW-248（维度 49）
- `xianyu-backend-code-review` B-REVIEW-342（维度 49）
