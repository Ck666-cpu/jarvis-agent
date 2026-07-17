import time
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings

# 初始化 FastAPI 应用
app = FastAPI(title="Jarvis Python Worker")

# 配置 LlamaIndex 使用本地的 Ollama 模型
# 注意：host.docker.internal 是让 Docker 容器能够访问你 Windows 宿主机的魔法地址
llm = Ollama(model="llama3", request_timeout=120.0, base_url="http://host.docker.internal:11434")

# 全局设置 LLM (后续加入 Embedding 和 RAG 都会默认用这个)
Settings.llm = llm

# 定义接收请求的数据格式
class QueryRequest(BaseModel):
    prompt: str

@app.get("/")
def health_check():
    return {"status": "Jarvis Python Worker is alive and ready!"}

@app.post("/api/v1/chat")
def chat_with_local_llm(request: QueryRequest):
    try:
        print(f"收到指令: {request.prompt}")
        # 调用本地大模型进行推理
        response = llm.complete(request.prompt)
        return {"response": str(response)}
    except Exception as e:
        print(f"推理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # 启动 Web 服务，监听 8000 端口
    uvicorn.run(app, host="0.0.0.0", port=8000)
