from abc import ABC, abstractmethod
from typing import Any
from a2a.types import (
    Part,
)
from a2a.helpers.proto_helpers import (
    new_text_part,
    new_data_part,
)
from google.protobuf import json_format


class RequestPartConverter(ABC):
    """Message part 请求内容转换器。"""

    @abstractmethod
    def convert_message_part(self, parts: list[Part]) -> str | dict[str, Any]:
        """将请求内容 Message 中的 parts 转换成 AgentReqeust 中的 content。"""

    @abstractmethod
    def convert_resume_part(self, parts: list[Part]) -> dict[str, Any]:
        """将请求内容 Message 中的 parts 转换成 AgentReqeust 中的 resume。"""


class ResponsePartConverter(ABC):
    """Message part 响应内容转换器。"""

    @abstractmethod
    def convert_content(self, content: str | dict[str, Any]) -> list[Part]:
        """将 AgentResponse 中的 content 转换成 Message 中的 parts。"""

    @abstractmethod
    def convert_artifact(self, artifact: str | dict[str, Any]) -> list[Part]:
        """将 AgentResponse 中的 artifact 转换成 Message 中的 parts。"""

    @abstractmethod
    def convert_interrupt(self, interrupt: dict[str, Any]) -> list[Part]:
        """将 AgentResponse 中的 interrupt 转换成 Message 中的 parts。"""


class DefaultRequestPartConverter(RequestPartConverter):
    """默认的请求 Message part 内容转换器。"""

    def convert_message_part(self, parts: list[Part]) -> str | dict[str, Any]:
        """将请求内容 Message 中的 parts 转换成 AgentReqeust 中的 content。

        Parts 内容示例:
        "parts": [
            {
                "data": {"content": "Hello", "resume": null}
            }
        ]
        """

        datas = _get_data_parts(parts)
        if len(datas) > 0:
            return datas[0].get("content", "")

        return ""

    def convert_resume_part(self, parts: list[Part]) -> dict[str, Any]:
        """将请求内容 Message 中的 parts 转换成 AgentReqeust 中的 resume。

        Parts 内容示例:
        "parts": [
            {
                "data": {"content": null, "resume": {"decisions": [{"type": "approve"}]}}
            }
        ]
        """

        datas = _get_data_parts(parts)
        if len(datas) > 0:
            return datas[0].get("resume", {})

        return {}


class DefaultResponsePartConverter(ResponsePartConverter):
    """默认的 Message part 响应内容转换器。"""

    def convert_content(self, content: str | dict[str, Any]) -> list[Part]:
        """将 AgentResponse 中的 content 转换成 Message 中的 parts。

        Parts 示例:
        "parts": [
          {
            "data": {
              "content": {
                "type": "ai",
                "text": "收到啦😉，你是有什么问题想要咨询，还是有什么事情想聊聊呀，可以把你的具体需求告诉我哦～",
                "name": "",
                "tool_calls": []
              },
              "interrupt": null
            }
          }
        ]
        """
        data = {"content": content, "interrupt": None}
        return [new_data_part(data=data)]

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
              "content": null,
              "interrupt": {
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
          }
        ]
        """
        data = {"content": None, "interrupt": interrupt}
        return [new_data_part(data=data)]


def _get_data_parts(parts: list[Part]) -> list[Any]:
    """提取所有 data Part 中的数据。"""
    result = []
    for part in parts:
        if part.HasField("data"):
            result.append(json_format.MessageToDict(part.data))
    return result
