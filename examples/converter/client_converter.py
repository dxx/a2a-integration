from typing import Any
from a2a.types import Part
from a2a.helpers.proto_helpers import (
    new_data_part,
    new_text_part,
    get_text_parts
)
from google.protobuf import json_format

from a2a_client.converter import (
    RequestPartConverter,
    ResponsePartConverter,
)

class CustomRequestPartConverter(RequestPartConverter):

    def convert_content(self, content: str | dict[str, Any]) -> list[Part]:
        """将 AgentRequest 中的 content 转换成 Message 中的 parts。

        Parts 内容示例:
        "parts": [
            {
                "text": "Hello"
            }
        ]
        """

        if isinstance(content, str):
            return [new_text_part(text=content)]
        return [new_text_part(text="")]

    def convert_resume(self, resume: dict[str, Any]) -> list[Part]:
        """将 AgentRequest 中的 resume 转换成 Message 中的 parts。

        Parts 内容示例:
        "parts": [
            {
                "data": {"decisions": [{"type": "approve"}]}
            }
        ]
        """

        return [new_data_part(data=resume)]


class CustomResponsePartConverter(ResponsePartConverter):

    def convert_message_part(self, parts: list[Part]) -> str | dict[str, Any]:
        """将 Message 中的 parts 转换成 AgentResponse 中的 content。

        Parts 示例:
        "parts": [
          {
            "text": "收到啦😉，你是有什么问题想要咨询，还是有什么事情想聊聊呀，可以把你的具体需求告诉我哦～"
          }
        ]
        """

        texts = _get_text_parts(parts)
        if len(texts) > 0:
            return texts[0]

        return ""

    def convert_artifact_part(self, parts: list[Part]) -> str | dict[str, Any]:
        """将 Message 中的 parts 转换成 AgentResponse 中的 artifact。

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

        return _get_part_content(parts)

    def convert_interrupt_part(self, parts: list[Part]) -> dict[str, Any]:
        """将 Message 中的 parts 转换成 AgentResponse 中的 interrupt。

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

        datas = _get_data_parts(parts)
        if len(datas) > 0:
            return datas[0]

        return {}


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


def _get_part_content(parts: list[Part]) -> str | dict[str, Any]:
    if not parts:
        return ""

    first_part = parts[0]

    if first_part.HasField("text"):
        return "\n".join(get_text_parts(parts))
    elif first_part.HasField("data"):
        # 第一个 data
        return json_format.MessageToDict(first_part.data)

    return ""
