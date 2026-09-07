# 维度 49：构建产物与路径标准（release 集中化 / SPA 单一来源 / 路径零硬编码）🆕v4.73.0 · F-REVIEW-248

> **编码规范引用**：xianyu-hunter-dev 规范 29（构建产物集中到 release/）/ 规范 30（SPA 单一来源）/ 规范 33（配置与路径零硬编码）
> **配置节点**：config.yaml#checklist.build_output_central + config.yaml#build_output_standards
> **测试关联**：xianyu-auto-testing 模式 AO（release 构建路径一致性）/ 模式 AP（沙箱安全删除）

## 触发条件
- 修改 `frontend/vite.config.ts` 的 `outDir` / `base` / 构建参数
- 修改任何把 SPA 拷入安装包 / 伺服 SPA 的脚本（build-exe.ps1 5.1、部署脚本）
- 出现 `dist\xianyu-hunter`、`/xianyu` 等路径 / base path 字面量散落
- 切换产品输出根或前端 base path

## 检查规则

### 强制（P0 阻塞）
- vite `outDir` 必须指向唯一编译产物根（约定 `../release/spa`），禁止写死其它散落目录（如旧的 `backend/.../static/spa`、`frontend/dist`）。
- `base` 必须来自配置（vite `base:'/xianyu/'`），且前端所有导航 / 资源引用必须基于 `import.meta.env.BASE_URL` 派生，**禁止写死裸根 `/` 或绝对字面量 `/xianyu/...`**（见规范 23）。
- 任何把 SPA 拷入安装包的步骤，源必须是 vite 权威输出 `release/spa`；若需拷 `backend/.../static` 等次级目录，必须**先排除 `spa` 子目录**，严禁第二副本混入（见规范 30）。

### 推荐（P1 严重）
- 产品输出根（release/）、base path、构建参数全部走 `vite.config.ts` / `build-exe.ps1` 变量，禁止散落绝对盘符路径（如 `D:\...\dist`）。
- `build.emptyOutDir` 相关清理由受控脚本（bat `rmdir /s /q`）负责，避免依赖被沙箱 safe-delete 劫持的删除（见规范 28）。
- 改输出根 / base path 时，相关七处路径引用（vite outDir / build-exe --distpath / installer OutputDir / 部署复制源 / app.py 伺服路径 / 子脚本默认路径 / cleanup+gitignore）必须同步对齐（见规范 29 判断逻辑）。

### 推荐（P2 改进）
- KB 索引排除清单里的 `dist`/`build` 字面量语义为“被排除目录名”，与构建产物目录同名但含义不同，审查时**不得盲目替换**，需区分保留。

## Grep 扫描命令
```bash
# 检测残留 dist\xianyu-hunter / dist\XianyuHunter-Setup 等旧产物引用（应全部清零）
grep -rn "dist\\\\xianyu-hunter\|dist\\\\XianyuHunter-Setup" frontend/ scripts/ --include="*.ts" --include="*.ps1" --include="*.bat" --include="*.py" 2>/dev/null

# 检测 vite outDir 是否指向约定根
grep -n "outDir" frontend/vite.config.ts

# 检测前端写死 /xianyu 绝对路径（应改 BASE_URL 派生）
grep -rn "location.replace('/')\|href='/xianyu" frontend/src/ --include="*.ts" --include="*.tsx"

# 检测 SPA 拷贝是否从第二副本（应只从 release/spa）
grep -n "static.*spa\|release/spa\|release\\\\spa" scripts/build-exe.ps1
```

## 判断标准
- vite outDir 未指向 `release/spa` → P0 阻塞
- 前端导航 / 资源写死裸根或 `/xianyu` 绝对字面量（非 BASE_URL 派生） → P0 阻塞
- 安装包 SPA 拷贝源为第二副本（非 release/spa） → P0 阻塞
- 输出根 / base path 写死绝对盘符路径 → P1 严重
- 七处路径引用未同步对齐 → P1 严重

## 适用场景
- 桌面 PyInstaller 打包项目（exe 从磁盘加载前端）
- 任何前端编译产物集中归档发布的场景
- 需要跨多脚本保持输出根一致的项目

## 不适用场景
- 纯前端 SPA（无 PyInstaller 打包 → release 打包侧动作不适用，但 SPA 单一来源 / vite outDir 唯一仍适用）
- SSR（Next/Nuxt）或非 SPA 多页应用（SPA 单一来源 / 子路径路由铁律不适用，见规范 23–25）
- 非本沙箱环境（无 safe-delete 守卫 → emptyOutDir 清理可简化，但单一来源原则仍适用）
