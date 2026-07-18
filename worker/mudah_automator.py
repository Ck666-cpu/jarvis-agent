import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def automate_mudah_post(title: str, description: str, price: str, image_paths: list):
    async with async_playwright() as p:
        # 启动 Chromium 浏览器
        # 注意：headless=False 可以在开发时看到浏览器自己动，测试成功后改成 True 在后台静默运行
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 注入 Stealth 伪装，抹除 Playwright 的机器人指纹
        stealth = Stealth()
        stealth.apply_stealth_sync(context)

        page = context.new_page()
        await page

        try:
            print("正在访问 Mudah.my...")
            # 访问发布页面 (这里以首页为例，你需要根据实际情况替换为具体的 Post Ad 链接)
            await page.goto("https://www.mudah.my/")

            # TODO: 1. 模拟点击登录 (可能需要你提前准备好账号密码或者 Cookie)
            # await page.locator("登录按钮的CSS选择器").click()

            # TODO: 2. 填写表单
            # print(f"正在填写标题: {title}")
            # await page.locator("标题输入框的选择器").fill(title)

            # TODO: 3. 上传图片
            # await page.locator("图片上传的选择器").set_input_files(image_paths)

            # 模拟人类操作的停顿，防止被封锁
            await page.wait_for_timeout(3000)
            print("表单填写模拟完成！")

        except Exception as e:
            print(f"自动化过程中发生错误: {e}")
        finally:
            await browser.close()


# 本地测试代码
if __name__ == "__main__":
    asyncio.run(automate_mudah_post(
        title="Beautiful Condo Near MRT",
        description="A great place to live...",
        price="RM 2500",
        image_paths=[]
    ))