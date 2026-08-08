# 维度 16：Composition Root

> **编码规范引用**：coding-standards v1.3 §依赖注入
> **配置节点**：config.yaml#composition_root
> **参考文档**：references/architecture.md §5

## 触发条件
- 修改 `container.py` 或依赖注入逻辑时
- 新增需要被注入的服务/仓储时
- 出现循环导入错误时

## 检查规则

### 强制（P0 阻塞）
- `container.py` 是唯一 DI 容器（Composition Root），所有跨层依赖从此获取
- container 使用 `@lru_cache` 管理单例
- 其他模块通过 `from xianyu_hunter.container import get_xxx` 获取依赖
- 循环依赖检测：container 中的 Provider 函数互相调用不能形成循环

### 推荐（P1 严重）
- 单例生命周期在 lifespan 中统一管理（startup 创建、shutdown 销毁）
- 每个 Provider 函数职责单一：只创建并返回一个服务实例
- 重资源配置（如 Playwright browser）在 lifespan 中预热
- 测试中可通过直接构造函数注入 mock 替代 container

### 禁止
- 多个 DI 容器文件（除 `container.py` 外的其他 DI 容器）
- 模块级全局单例遍布各处（如 `_buyer_service = BuyerService()`）
- 在业务模块中直接 `container.get_xxx()` 绕过构造函数注入
- Provider 函数间循环调用

## Grep 扫描命令
```bash
# 检测 container.py 是否为唯一 DI 容器
grep -rn "@lru_cache\ndef get_" src/xianyu_hunter/ | grep -v "container\.py"

# 检测模块级全局单例
grep -rn "^_\w+_service\s*=\s*\w+\(\)" src/xianyu_hunter/

# 检测 Provider 间循环引用
grep -rn "from.*container import" src/xianyu_hunter/container.py
```

## 判断标准
- 非 container 的 @lru_cache Provider：P0 阻塞
- 模块级全局单例：P0 阻塞
- 循环依赖：P0 阻塞
- 缺少 lifespan 管理：P1 严重

## 适用场景
- `infra/container.py` DI 容器
- `web/app.py` lifespan 钩子
- 服务的初始化和生命周期管理

## 不适用场景
- Pydantic 模型的工厂方法（非 DI）
- SQLAlchemy session 的创建（遵循自身异步模式）
- 第三方库的全局状态管理
