# 维度 11：错误处理

> **编码规范引用**：coding-standards v1.3 §代码边界契约
> **配置节点**：config.yaml#error_handling
> **参考文档**：references/maintainability.md §5

## 触发条件
- 新增 try/except 块时
- 关键迁移/启动代码的异常处理
- 外部依赖调用（API/浏览器/文件 I/O）时

## 检查规则

### 强制（P0 阻塞）
- 禁止 `except: pass` 或 `except Exception: pass` 静默吞异常
- 异常信息必须包含足够上下文：`f"操作失败 table={table} pk={pk}"`
- 关键迁移失败必须 `raise RuntimeError` 中断启动（如建表失败）
- 非关键迁移失败允许 `logger.warning` + 继续启动

### 推荐（P1 严重）
- 外部依赖调用必须有容错：token 预刷新、DOM 回退（`querySelector` 回退）、限流重试
- 自定义业务异常层次：`XianyuError → ConfigError / ItemNotFoundError`
- 分层错误处理：infra 抛底层异常 → modules 转业务异常 → web 转 HTTPException
- `asyncio.gather` 使用 `return_exceptions=True` 收集所有结果再分拣
- KeyboardInterrupt/SystemExit/asyncio.CancelledError 不吞，直接 re-raise

### 禁止
- 空 `except:` 块
- 只 `print(e)` 不 `logger.exception()`
- 在 except 块中再次抛出一个**无上下文**的新异常（丢失原始堆栈）
- 事务中吞异常不 rollback

## Grep 扫描命令
```bash
# 检测静默吞异常
grep -rn "except.*:" src/xianyu_hunter/ -A 1 | grep "pass"

# 检测只 print 不 log
grep -rn "except.*:.*print(" src/xianyu_hunter/

# 检测 raise 丢失上下文（raise e 而非 raise）
grep -rn "except.*:.*raise e$" src/xianyu_hunter/
```

## 判断标准
- `except: pass` 静默吞：P0 阻塞
- 关键迁移失败未 raise：P0 阻塞
- 异常信息无上下文：P0 阻塞
- 缺少外部调用容错：P1 严重

## 适用场景
- 所有 try/except 块
- 数据库迁移脚本
- 外部 API/浏览器调用
- 后台任务异常处理

## 不适用场景
- KeyboardInterrupt/SystemExit/asyncio.CancelledError 的处理（应 re-raise）
- pytest 测试中预期的异常（`with pytest.raises(...)`）
- 资源清理中的 `finally:` 块（`pass` 合法）
