import os
import ollama
from celery import Celery
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)


@app.task(name="tasks.scrape_website")
def scrape_website(url: str):
    print(f"\n========================================")
    print(f"🧠 [Jarvis Worker] 任务启动：抓取并分析网页")
    print(f"🔗 目标网址: {url}")
    print(f"========================================\n")

    with sync_playwright() as p:
        # 【伪装核心 1】：修改底层启动参数，屏蔽自动化特征
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",  # 极其重要：关闭自动化控制标识
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ],
            ignore_default_args=["--enable-automation"]  # 忽略默认的自动化参数
        )

        # 【伪装核心 2】：注入一个极其逼真的真人 User-Agent，并设置真实的屏幕分辨率
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN,zh;q=0.9,en;q=0.8",
            timezone_id="Asia/Shanghai"
        )

        # 【伪装核心 3】：在页面加载任何脚本之前，注入 stealth 插件修补底层指纹
        stealth = Stealth()
        stealth.apply_stealth_sync(context)

        page = context.new_page()

        try:
            print("[1/3] 正在潜行抓取网页 DOM...")

            # 延长超时时间，因为 Cloudflare 盾可能需要 5-10 秒来计算浏览器指纹
            page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # 等待一下，让页面完全渲染
            page.wait_for_timeout(3000)

            page_text = page.evaluate("document.body.innerText")
            title = page.title()

            clean_text = "\n".join([line.strip() for line in page_text.splitlines() if line.strip()])
            content_to_analyze = clean_text[:3000]

            print(f"[2/3] 抓取成功！获取到有效文本 {len(clean_text)} 字符。开始呼叫本地大模型...")

            prompt = f"""
            你是一个高级信息分析助手。请阅读以下从网页提取的文本内容，并给出一个结构化的总结。
            网页标题：{title}
            网页内容片段：
            {content_to_analyze}

            请输出：
            1. 一句话核心摘要
            2. 三个关键信息点（用 bullet points 列出）
            """

            response = ollama.chat(model='qwen2:7b', messages=[
                {'role': 'user', 'content': prompt}
            ])

            ai_summary = response['message']['content']
            print("\n💡 [3/3] 大模型分析完成，以下是总结报告：")
            print("--------------------------------------------------")
            print(ai_summary)
            print("--------------------------------------------------\n")

            return {"status": "success", "title": title, "summary": ai_summary}

        except Exception as e:
            print(f"❌ [Worker] 执行失败: {str(e)}")
            return {"status": "failed", "error": str(e)}
        finally:
            browser.close()