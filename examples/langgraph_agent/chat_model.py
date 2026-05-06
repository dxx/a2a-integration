import os
from langchain import chat_models

BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
API_KEY = os.getenv("VOLCANO_API_KEY")

def get_chat_model():
    return chat_models.init_chat_model(
        model="doubao-seed-2-0-lite-260215",
        model_provider="openai",
        base_url=BASE_URL,
        api_key=API_KEY,
        extra_body={
            # Minimax 将思考字段从 content 中分离出来
            "reasoning_split": True,
        }
    )
