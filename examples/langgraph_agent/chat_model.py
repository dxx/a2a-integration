import os
from langchain import chat_models

BASE_URL = "https://api.minimaxi.com/v1"
API_KEY = os.getenv("MINIMAX_API_KEY")

def get_chat_model():
    return chat_models.init_chat_model(
        model="MiniMax-M3",
        model_provider="openai",
        base_url=BASE_URL,
        api_key=API_KEY,
        extra_body={
            # Minimax 将思考字段从 content 中分离出来
            "reasoning_split": True,
        }
    )
