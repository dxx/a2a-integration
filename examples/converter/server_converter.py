from typing import Any
from a2a.types import Part
from a2a.helpers.proto_helpers import (
    new_text_part,
    new_data_part,
)
from google.protobuf import json_format

from a2a_server.converter import (
    RequestPartConverter,
    ResponsePartConverter,
)


class CustomRequestPartConverter(RequestPartConverter):

    def convert_message_part(self, parts: list[Part]) -> str | dict[str, Any]:
        """将请求内容 Message 中的 parts 转换成 AgentReqeust 中的 content。

        Parts 内容示例:
        "parts": [
            {
                "text": "Hello"
            }
        ]
        """

        texts = _get_text_parts(parts)
        if len(texts) > 0:
            return texts[0]

        return ""

    def convert_resume_part(self, parts: list[Part]) -> dict[str, Any]:
        """将请求内容 Message 中的 parts 转换成 AgentReqeust 中的 resume。

        Parts 内容示例:
        "parts": [
            {
                "data": {"decisions": [{"type": "approve"}]}
            }
        ]
        """

        datas = _get_data_parts(parts)
        if len(datas) > 0:
            return datas[0]

        return {}


class CustomResponsePartConverter(ResponsePartConverter):

    def convert_content(self, content: str | dict[str, Any]) -> list[Part]:
        """将 AgentResponse 中的 content 转换成 Message 中的 parts。

        Parts 示例:
        "parts": [
          {
            "text": "收到啦😉，你是有什么问题想要咨询，还是有什么事情想聊聊呀，可以把你的具体需求告诉我哦～"
          }
        ]
        """
        if isinstance(content, str):
            return [new_text_part(text=content)]
        return [new_text_part(text="")]

    def convert_artifact(self, artifact: str | dict[str, Any]) -> list[Part]:
        """将 AgentResponse 中的 artifact 转换成 Message 中的 parts。

        Atifacts 示例:
        "artifacts": [
            {
                "artifactId": "763db67a-c611-4c78-95fa-d5893d7153d0",
                "name": "result",
                "parts": [
                    {
                        "text": "Finished"
                    }
                ]
            }
        ]
        """

        return (
            [new_text_part(text=artifact)]
            if isinstance(artifact, str)
            else [new_data_part(data=artifact)]
        )

    def convert_interrupt(self, interrupt: dict[str, Any]) -> list[Part]:
        """将 AgentResponse 中的 interrupt 转换成 Message 中的 parts。

        Parts 示例:
        "parts": [
          {
            "data": {
                "id": "5b7cac0cdf5f7240b8a7f105e130a751",
                "value": {
                    "action_requests": [
                        {
                            "name": "write_file",
                            "args": {"file_path": "files/hello.txt", "content": "hello"}
                        }
                    ]
                }
            }
          }
        ]
        """

        return [new_data_part(data=interrupt)]


def _get_text_parts(parts: list[Part]) -> list[Any]:
    """提取所有 text Part 中的数据。"""
    result = []
    for part in parts:
        if part.HasField("text"):
            result.append(part.text)
    return result


def _get_data_parts(parts: list[Part]) -> list[Any]:
    """提取所有 data Part 中的数据。"""
    result = []
    for part in parts:
        if part.HasField("data"):
            result.append(json_format.MessageToDict(part.data))
    return result
