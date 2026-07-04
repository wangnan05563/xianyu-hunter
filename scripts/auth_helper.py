"""浏览器认证助手 - 通过 subprocess 被 web 后端调用

两个子命令：
- info    启动 headless 持久化 Chromium 访问 goofish/personal，提取用户昵称/头像
- qr      启动 headless 持久化 Chromium 打开登录页，截屏二维码到 out_dir/qr.png，
          轮询 cookie 检测登录完成；状态写 out_dir/status.json

所有结果以 JSON 形式写到 out_dir 中，由 web 后端读取。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 允许从仓库根直接运行
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))


def _get_browser_cfg():
    from xianyu_hunter.infra.yaml_config import get_config

    return get_config().browser


def _export_cookies_to_json(cookies: list[dict], method: str) -> None:
    """登录成功后导出 Cookie 到 JSON 文件（供 Web 后端立即验证）"""
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        get_cookie_store().export_cookies(cookies, method=method)
    except Exception as e:
        print(f"[auth_helper] Cookie JSON 导出失败: {e}", file=sys.stderr)


def _set_status(out_dir: Path, **kw) -> None:
    """原子写入 status.json；web 后端轮询此文件"""
    s = {}
    p = out_dir / "status.json"
    if p.exists():
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            s = {}
    s.update(kw)
    s["ts"] = time.time()
    p.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


async def _check_login_error(page) -> dict:
    """检测闲鱼登录页是否返回了错误页（非法请求 / appNameError 等）"""
    return await page.evaluate(
        """() => {
          const t = (document.body && document.body.innerText) || '';
          const keywords = [
            '非法请求', 'appNameError', '参数错误', '登录已过期',
            '请重新登录', '访问被拒绝', 'access denied', 'access denied',
            '鉴权失败', '安全校验',
          ];
          const hits = keywords.filter(k => t.includes(k));
          const url = location.href.toLowerCase();
          const badUrl = /(deny|error|forbidden|not[-_]?found|404)/.test(url);
          return { hits: hits, url: url, badUrl: badUrl };
        }"""
    )


# ============== info: 拉取当前登录用户信息 ==============
async def _cmd_info(out_dir: Path) -> int:
    """拉取当前登录用户信息（昵称/头像/user_id）

    策略：
    1) 看 cookie：_m_h5_tk / cookie2 / _tb_token_ 任一存在 → 可能有登录态
    2) 访问 /personal 页面：以页面 DOM 为准（DOM 有"登录"链接 = 未登录）
    3) 从页面抓昵称/头像；过滤掉"登录/登錄"等按钮文本
    4) 从 cookie 提取 user id（unb → _tb_token_）
    """
    from playwright.async_api import async_playwright

    cfg = _get_browser_cfg()
    _set_status(out_dir, state="starting", message="启动浏览器…")
    try:
        async with async_playwright() as pw:
            # 反检测参数：闲鱼对 headless 浏览器有较强的指纹检测
            # --disable-blink-features=AutomationControlled 去掉 navigator.webdriver=true
            # 其余参数减少自动化特征暴露
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=cfg.user_data_dir,
                headless=True,
                user_agent=cfg.user_agent,
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",  # 允许跨域（登录页需要）
                ],
            )
            try:
                _set_status(out_dir, state="fetching", message="访问个人主页…")
                page = await ctx.new_page()
                await page.goto(
                    "https://www.goofish.com/personal",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(3000)
                cur_url = page.url
                # 1) 页面级登录判定：URL 跳到 login.* / passport.* = 未登录
                url_low = cur_url.lower()
                is_login_url = any(k in url_low for k in ("/login", "/mini_login", "/passport/", "login.htm"))
                # 2) 抓昵称/头像
                info = await page.evaluate(
                    """() => {
                      // 个人中心常见登录后元素
                      const sel = [
                        '[class*="userInfo"] [class*="nick"]',
                        '[class*="user-info"] [class*="nick"]',
                        '[class*="userInfo--"] [class*="nick--"]',
                        '[class*="userName"]',
                        '[class*="nickName"]',
                        '[class*="username"]',
                        'header [class*="nick"]',
                        'a[href*="personal"] [class*="nick"]',
                      ];
                      let nick = '';
                      for (const s of sel) {
                        const el = document.querySelector(s);
                        if (el && (el.textContent || '').trim()) {
                          nick = (el.textContent || '').trim();
                          break;
                        }
                      }
                      // 头像
                      const ava = document.querySelector(
                        '[class*="avatar"] img, [class*="Avatar"] img, img[class*="avatar"]'
                      );
                      // 备用：window.__INIT_DATA__ 里的 nick/userNick
                      let wNick = '';
                      try {
                        const w = window;
                        for (const k of Object.keys(w)) {
                          if (k.startsWith('__INIT') || k.startsWith('_INIT')) {
                            const obj = w[k];
                            if (obj && typeof obj === 'object') {
                              const s = JSON.stringify(obj);
                              const m = s.match(/"(?:userNick|userName|nickName|nick)"\\s*:\\s*"([^"]{1,30})"/);
                              if (m) { wNick = m[1]; break; }
                            }
                          }
                        }
                      } catch (_) {}
                      return {
                        nick: nick || wNick || '',
                        avatar: ava ? (ava.src || ava.getAttribute('data-src') || '') : '',
                        title: document.title || '',
                        url: location.href,
                      };
                    }"""
                )
                # 过滤"登录"按钮文本和闲鱼默认欢迎语（未登录时也会显示）
                raw_nick = (info.get("nick") or "").strip()
                if raw_nick in ("登录", "登錄", "Login", "Sign in", "立即登录", "Hi! 你好", "Hi！你好", "你好", ""):
                    raw_nick = ""
                # 3) cookie 信息
                cookies = await ctx.cookies()
                goofish_cookies = [c for c in cookies if "goofish" in (c.get("domain") or "")]
                goofish_names = {c.get("name", "") for c in goofish_cookies}
                uid = ""
                for c in goofish_cookies:
                    if c.get("name") == "unb":
                        uid = c["value"]
                        break
                if not uid:
                    for c in goofish_cookies:
                        if c.get("name") == "_tb_token_":
                            uid = c["value"][:16]
                            break
                # 4) 最终登录态判定
                #    关键：以关键登录 Cookie 为准（unb/_tb_token_/cookie2 任一存在即视为已登录）
                #    之前要求 nick 非空 + cookie 才算登录，会导致 DOM 抓取失败时误判为未登录
                #    （顶部 UserMenu 显示"未登录"），而 cookie 才是登录态的硬指标
                #    关键登录 Cookie：unb（用户ID）、_tb_token_（淘宝Token）、cookie2
                login_cookie_names = {"unb", "_tb_token_", "cookie2"}
                has_login_cookie = bool(login_cookie_names & goofish_names)
                if is_login_url:
                    logged_in = False
                else:
                    # cookie 在 + 不在登录页 URL → 视为已登录
                    # 不再要求 nick 非空：nick 抓取易受 DOM 反爬影响，cookie 更可靠
                    logged_in = has_login_cookie
                # 5) 昵称为空且登录态有效：依次尝试 淘宝我的页面 → cookie unb 兜底
                if logged_in and not raw_nick:
                    try:
                        await page.goto(
                            "https://main.m.taobao.com/myTaobao.htm",
                            wait_until="domcontentloaded",
                            timeout=10000,
                        )
                        await page.wait_for_timeout(2000)
                        info2 = await page.evaluate(
                            """() => {
                              const sel = [
                                '[class*="nick"]', '[class*="userName"]',
                                '[class*="username"]', '[class*="userNick"]',
                                '[class*="user-nick"]', '[class*="nickname"]',
                              ];
                              for (const s of sel) {
                                const el = document.querySelector(s);
                                if (el && (el.textContent || '').trim()) {
                                  return (el.textContent || '').trim();
                                }
                              }
                              return '';
                            }"""
                        )
                        if info2 and info2 not in ("登录", "登錄", "Login", "Sign in"):
                            raw_nick = info2
                    except Exception:
                        pass
                # 5.1) 仍为空：用 unb cookie 值作为兜底昵称（至少有可读标识，比空字符串好）
                #      不直接用 user_id 是因为 user_id 可能是 _tb_token_ 截断的前 16 字符
                if logged_in and not raw_nick:
                    for c in goofish_cookies:
                        if c.get("name") == "unb" and c.get("value"):
                            raw_nick = f"闲鱼用户{c['value'][-4:]}"
                            break
                result = {
                    "logged_in": logged_in,
                    "user_id": uid,
                    "nick": raw_nick,
                    "avatar_url": info.get("avatar", ""),
                    "title": info.get("title", ""),
                    "url": cur_url,
                    "fetched_at": time.time(),
                }
                (out_dir / "userinfo.json").write_text(
                    json.dumps(result, ensure_ascii=False), encoding="utf-8"
                )
                _set_status(
                    out_dir,
                    state="done",
                    message=f"logged_in={logged_in}, nick='{raw_nick}', uid='{uid[:8]}', url={cur_url}",
                )
                return 0
            finally:
                await ctx.close()
    except Exception as e:  # noqa: BLE001
        _set_status(out_dir, state="error", message=str(e))
        return 1


# ============== qr: 启动登录流程 + 截屏二维码 ==============
async def _cmd_qr(out_dir: Path, timeout: int) -> int:
    from playwright.async_api import async_playwright

    cfg = _get_browser_cfg()
    _set_status(out_dir, state="starting", message="启动浏览器…")
    try:
        async with async_playwright() as pw:
            # 使用与搜索相同的 Chromium 浏览器（headless=False 用于显示二维码）
            # 不传 channel="msedge"，确保 Cookie 加密密钥与搜索浏览器一致
            # 关键：不注入 stealth 脚本、不传反检测参数，以最接近用户手动打开的方式启动
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=cfg.user_data_dir,
                headless=False,
                # 不设 user_agent，使用 Chromium 原生 UA
                # 不传 args，避免任何可能被识别为自动化的启动标志
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            try:
                # 不注入 stealth 脚本 — 保留浏览器原生状态，避免被检测
                pass

                _set_status(out_dir, state="opening", message="打开登录页…")
                page = await ctx.new_page()
                # 不再直接访问 passport.goofish.com/mini_login.htm（裸访问缺 ttid/redirectType 等参数会触发 appNameError）
                # 改为先访问主站 www.goofish.com，由主站自然跳转到带完整参数的登录页
                await page.goto(
                    "https://www.goofish.com",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                # 等待页面稳定后检查是否需要点击登录按钮或已自动跳转到登录页
                await page.wait_for_timeout(3000)
                cur_url = page.url

                # 如果已被重定向到登录相关 URL，说明主站自动处理了跳转
                if any(k in cur_url.lower() for k in ("login", "passport", "mini_login")):
                    _set_status(out_dir, state="opening", message="已跳转至登录页…")
                    await page.wait_for_timeout(3000)
                else:
                    # 未自动跳转：尝试在主站找到并点击登录按钮
                    try:
                        login_btn = await page.query_selector(
                            'a[href*="login"], [class*="login"], [data-login], '
                            '.login-btn, .header-login, [aria-label*="登录"]'
                        )
                        if login_btn:
                            await login_btn.click()
                            _set_status(out_dir, state="opening", message="点击登录入口…")
                            await page.wait_for_timeout(4000)
                        else:
                            # 兜底：直接用带参数的 h5 登录 URL（参考闲鱼 H5 实际调用格式）
                            _set_status(out_dir, state="opening", message="打开 H5 登录页…")
                            await page.goto(
                                "https://passport.goofish.com/mini_login.htm"
                                "?ttid=h5@iframe&redirectType=iframeRedirect"
                                "&returnUrl=https%3A%2F%2Fwww.goofish.com%2F",
                                wait_until="domcontentloaded",
                                timeout=20000,
                            )
                            await page.wait_for_timeout(4500)
                    except Exception:
                        # 点击失败也兜底到带参数的 URL
                        _set_status(out_dir, state="opening", message="打开 H5 登录页…")
                        await page.goto(
                            "https://passport.goofish.com/mini_login.htm"
                            "?ttid=h5@iframe&redirectType=iframeRedirect"
                            "&returnUrl=https%3A%2F%2Fwww.goofish.com%2F",
                            wait_until="domcontentloaded",
                            timeout=20000,
                        )
                        await page.wait_for_timeout(4500)

                # 截屏前检测页面是否错误页
                # 已知现象：appName / 签名 / cookies 任一异常时，闲鱼会渲染"非法请求 [appNameError]"
                err_signals = await _check_login_error(page)
                if err_signals["hits"] or err_signals["badUrl"]:
                    # 第一次失败：尝试清除 goofish 相关 cookies 后重试一次
                    # browser-data 中的过期/异常 cookie 是最常见的原因
                    _set_status(out_dir, state="opening", message="检测到异常，清除 cookies 后重试…")
                    cookies = await ctx.cookies()
                    bad_domains = [c.get("domain") for c in cookies if any(k in (c.get("domain") or "") for k in ("goofish", "taobao", "alipay"))]
                    if bad_domains:
                        await ctx.clear_cookies(domain=bad_domains[0])
                    for d in set(bad_domains):
                        try:
                            await ctx.clear_cookies(domain=d)
                        except Exception:
                            pass
                    await page.goto(
                        "https://passport.goofish.com/mini_login.htm"
                        "?ttid=h5@iframe&redirectType=iframeRedirect"
                        "&returnUrl=https%3A%2F%2Fwww.goofish.com%2F",
                        wait_until="domcontentloaded",
                        timeout=20000,
                    )
                    await page.wait_for_timeout(5000)
                    err_signals = await _check_login_error(page)
                    if err_signals["hits"] or err_signals["badUrl"]:
                        # 第二次失败：可能是 browser-data 目录本身有问题
                        # 关闭当前上下文，删除 Default 目录后重试（保留其他配置）
                        _set_status(out_dir, state="opening", message="重置浏览器配置后重试…")
                        await ctx.close()
                        # 删除 Default 目录以清除所有异常状态（Cookie、LocalStorage 等）
                        import shutil
                        default_dir = Path(cfg.user_data_dir) / "Default"
                        if default_dir.exists():
                            shutil.rmtree(default_dir, ignore_errors=True)
                        # 重新以主 user_data_dir 启动（确保 Cookie 写入正确位置）
                        ctx = await pw.chromium.launch_persistent_context(
                            user_data_dir=cfg.user_data_dir,
                            headless=False,
                            viewport={"width": 1280, "height": 800},
                            locale="zh-CN",
                            timezone_id="Asia/Shanghai",
                        )
                        page = await ctx.new_page()
                        await page.goto(
                            "https://passport.goofish.com/mini_login.htm"
                            "?ttid=h5@iframe&redirectType=iframeRedirect"
                            "&returnUrl=https%3A%2F%2Fwww.goofish.com%2F",
                            wait_until="domcontentloaded",
                            timeout=20000,
                        )
                        await page.wait_for_timeout(5000)
                        err_signals = await _check_login_error(page)
                        if err_signals["hits"] or err_signals["badUrl"]:
                            msg = (
                                f"闲鱼登录页返回错误页"
                                + (f"（命中关键字：{','.join(err_signals['hits'])}）" if err_signals["hits"] else "")
                                + (f"（可疑 URL：{err_signals['url']}）" if err_signals["badUrl"] else "")
                                + "；通常是 appName / 签名 / cookies 异常导致"
                                + "，建议删除 browser-data 目录后重试"
                            )
                            _set_status(out_dir, state="error", message=msg)
                            return 3
                qr_png = out_dir / "qr.png"
                await page.screenshot(path=str(qr_png), full_page=False)
                # 顺便也截个 full-page 备份（包含提示文字，对用户更友好）
                qr_full = out_dir / "qr_full.png"
                try:
                    await page.screenshot(path=str(qr_full), full_page=True)
                except Exception:
                    pass
                _set_status(
                    out_dir,
                    state="qr_ready",
                    message=f"请用手机闲鱼 App 在 {timeout}s 内扫码",
                    qr_png=str(qr_png),
                )
                # 轮询 cookie
                start = time.monotonic()
                while time.monotonic() - start < timeout:
                    cookies = await ctx.cookies()
                    names = {c["name"] for c in cookies}
                    if {"_m_h5_tk", "unb", "sgcookie"} & names:
                        _set_status(out_dir, state="success", message="✓ 登录成功")
                        # 导出 Cookie 到 JSON（主验证数据源）
                        _export_cookies_to_json(cookies, "qr")
                        # 拉一次 userinfo 缓存下来
                        await asyncio.sleep(800 / 1000)
                        await _fetch_userinfo_into(ctx, out_dir)
                        return 0
                    await asyncio.sleep(2)
                _set_status(out_dir, state="timeout", message=f"超时（{timeout}s 内未完成扫码）")
                return 2
            finally:
                await ctx.close()
    except Exception as e:  # noqa: BLE001
        _set_status(out_dir, state="error", message=str(e))
        return 1


async def _fetch_userinfo_into(ctx, out_dir: Path) -> None:
    """登录成功后顺便抓 userinfo 写入缓存（用 personal 页面更稳定）

    与 _cmd_info 共用判定逻辑：cookie 有效即视为已登录，nick 抓取失败时
    用 unb cookie 后4位兜底，避免登录态与昵称耦合导致 UserMenu 显示"未登录"。
    """
    try:
        page = await ctx.new_page()
        await page.goto("https://www.goofish.com/personal", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2500)
        info = await page.evaluate(
            """() => {
              const sel = [
                '[class*="userInfo"] [class*="nick"]',
                '[class*="user-info"] [class*="nick"]',
                '[class*="userInfo--"] [class*="nick--"]',
                '[class*="userName"]', '[class*="username"]',
                '[class*="userNick"]', '[class*="user-nick"]',
                '[class*="nickname"]', '[class*="nickName"]',
              ];
              let nick = '';
              for (const s of sel) {
                const el = document.querySelector(s);
                if (el && (el.textContent || '').trim()) {
                  nick = (el.textContent || '').trim();
                  break;
                }
              }
              const ava = document.querySelector('[class*="avatar"] img, [class*="Avatar"] img');
              return {
                nick: nick,
                avatar: ava ? (ava.src || '') : '',
              };
            }"""
        )
        cookies = await ctx.cookies()
        goofish_cookies = [c for c in cookies if "goofish" in (c.get("domain") or "")]
        uid = ""
        for c in goofish_cookies:
            if c.get("name") == "unb":
                uid = c["value"]
                break
        nick = (info.get("nick") or "").strip()
        if nick in ("登录", "登錄", "Login", "Sign in", "立即登录", "Hi! 你好", "Hi！你好", "你好", ""):
            nick = ""
        # 兜底：DOM 抓取失败时用 unb 后4位生成可读昵称
        if not nick and uid:
            nick = f"闲鱼用户{uid[-4:]}"
        result = {
            "logged_in": True,
            "user_id": uid,
            "nick": nick,
            "avatar_url": info.get("avatar", ""),
            "url": page.url,
            "fetched_at": time.time(),
        }
        (out_dir / "userinfo.json").write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:  # noqa: BLE001
        _set_status(out_dir, message=f"抓 userinfo 失败（忽略）: {e}")


# ============== CLI ==============
def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="拉取当前登录用户信息")
    p_info.add_argument("--out-dir", required=True, help="结果输出目录")

    p_qr = sub.add_parser("qr", help="启动登录流程 + 截屏二维码")
    p_qr.add_argument("--out-dir", required=True)
    p_qr.add_argument("--timeout", type=int, default=180)

    args = p.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "info":
        return asyncio.run(_cmd_info(out_dir))
    if args.cmd == "qr":
        return asyncio.run(_cmd_qr(out_dir, args.timeout))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
