import os
import asyncio
import ollama
from celery import Celery
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json
from llama_index.llms.ollama import Ollama
from mudah_automator import automate_mudah_post

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
# 初始化本地大模型引擎
llm = Ollama(model="llama3", request_timeout=120.0, base_url="http://host.docker.internal:11434")

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

@app.task(name="tasks.automate_mudah_post")
def process_telegram_message(raw_text: str, image_paths: list):
    """
    接收原始文本和图片路径，利用 LLM 清洗数据，并触发自动化发布
    """
    print(f"========== 开始处理任务 ==========")
    print(f"收到原始文案: {raw_text}")

    # 1. 构建 Prompt，强制 Llama 3 扮演专业房产中介并返回 JSON
    prompt = f"""
    You are a professional real estate copywriter in Malaysia. 
    Extract and rewrite the following raw Telegram message into a highly attractive Mudah.my property listing.

    Raw Message:
    {raw_text}

    Requirements:
    1. Title must be catchy (e.g., include tags like 🔥, 🚆 Near MRT, etc.)
    2. Price must be a formatted string (e.g., 'RM 2500')
    3. Description should be professional, well-structured, and persuasive.

    You MUST output ONLY a valid JSON object in the following format, with no markdown formatting or other text:
    {{
        "title": "...",
        "price": "...",
        "description": "..."
    }}
    """

    try:
        print("正在呼叫本地 Llama 3 进行智能提取和文案重写...")
        response = llm.complete(prompt)
        result_text = str(response).strip()

        # 尝试清理可能出现的 Markdown 标记 (大模型有时候很顽皮，喜欢加 ```json)
        if result_text.startswith("```json"):
            result_text = result_text[7:-3]

        # 解析 JSON
        property_data = json.loads(result_text)
        print("✅ 数据清洗成功！")
        print(json.dumps(property_data, indent=2, ensure_ascii=False))

        # 2. 拿到结构化数据后，触发 Playwright 进行自动化填表
        print("正在唤醒 Playwright 数字机器人...")
        posting_result = asyncio.run(automate_mudah_post(
            title=property_data["title"],
            description=property_data["description"],
            price=property_data["price"],
            image_paths=image_paths,
            headless=os.getenv("HEADLESS", "True").lower() == "true",
        ))

        if posting_result.get("status") == "success":
            print(f"✅ Mudah.my listing posted! URL: {posting_result.get('url', 'N/A')}")
        else:
            print(f"⚠️  Posting issue: {posting_result.get('message', 'unknown')}")

        return {"status": "success", "data": property_data, "posting": posting_result}

    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败，LLM 输出的格式不对: {str(response)}")
        return {"status": "error", "message": "Failed to parse LLM output"}
    except Exception as e:
        print(f"❌ 处理过程中发生严重错误: {e}")
        return {"status": "error", "message": str(e)}


@app.task(name="tasks.post_to_mudah")
def post_to_mudah(title: str, description: str, price: str, image_paths: list = None):
    """
    Standalone task: directly post a listing to Mudah.my without LLM rewriting.
    Useful when the caller already has structured data.
    """
    print(f"========== Mudah Direct Post ==========")
    print(f"Title: {title} | Price: {price}")

    try:
        result = asyncio.run(automate_mudah_post(
            title=title,
            description=description,
            price=price,
            image_paths=image_paths or [],
            headless=os.getenv("HEADLESS", "True").lower() == "true",
        ))
        return result
    except Exception as e:
        print(f"❌ Direct post failed: {e}")
        return {"status": "error", "message": str(e)}
