from google.protobuf import json_format

import pytest

from a2a.types import Part
from a2a_server.converter import (
    DefaultRequestPartConverter,
    DefaultResponsePartConverter,
)


def _make_data_part(data_dict: dict) -> Part:
    part = Part()
    part.data.CopyFrom(json_format.ParseDict(data_dict, part.data))
    return part


def _make_text_part(text: str) -> Part:
    part = Part()
    part.text = text
    return part


class TestDefaultRequestPartConverter:
    @pytest.fixture
    def converter(self) -> DefaultRequestPartConverter:
        return DefaultRequestPartConverter()

    def test_convert_message_part_empty_list(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        result = converter.convert_message_part([])
        assert result == ""

    def test_convert_message_part_no_data(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        parts = [_make_text_part("hello")]
        result = converter.convert_message_part(parts)
        assert result == ""

    def test_convert_message_part_with_content(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        parts = [_make_data_part({"content": "hello world"})]
        result = converter.convert_message_part(parts)
        assert result == "hello world"

    def test_convert_message_part_without_content(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        parts = [_make_data_part({"other": "field"})]
        result = converter.convert_message_part(parts)
        assert result == ""

    def test_convert_message_part_multiple_data(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        """只取第一个 data part 的 content。"""
        parts = [
            _make_data_part({"content": "first"}),
            _make_data_part({"content": "second"}),
        ]
        result = converter.convert_message_part(parts)
        assert result == "first"

    def test_convert_resume_part_empty_list(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        result = converter.convert_resume_part([])
        assert result == {}

    def test_convert_resume_part_no_data(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        parts = [_make_text_part("hello")]
        result = converter.convert_resume_part(parts)
        assert result == {}

    def test_convert_resume_part_with_resume(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        parts = [_make_data_part({"resume": {"decisions": [{"type": "approve"}]}})]
        result = converter.convert_resume_part(parts)
        assert result == {"decisions": [{"type": "approve"}]}

    def test_convert_resume_part_without_resume(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        parts = [_make_data_part({"other": "field"})]
        result = converter.convert_resume_part(parts)
        assert result == {}

    def test_convert_resume_part_multiple_data(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        """只取第一个 data part 的 resume。"""
        parts = [
            _make_data_part({"resume": {"a": 1}}),
            _make_data_part({"resume": {"b": 2}}),
        ]
        result = converter.convert_resume_part(parts)
        assert result == {"a": 1}


class TestDefaultResponsePartConverter:
    @pytest.fixture
    def converter(self) -> DefaultResponsePartConverter:
        return DefaultResponsePartConverter()

    def test_convert_content_with_string(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        result = converter.convert_content("hello")
        assert len(result) == 1
        assert json_format.MessageToDict(result[0]) == {
            "data": {"content": "hello", "interrupt": None}
        }

    def test_convert_content_with_dict(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        content = {"type": "ai", "text": "你好"}
        result = converter.convert_content(content)
        assert len(result) == 1
        assert json_format.MessageToDict(result[0]) == {
            "data": {"content": content, "interrupt": None}
        }

    def test_convert_interrupt(self, converter: DefaultResponsePartConverter) -> None:
        interrupt = {"action_requests": [{"name": "write_file", "args": "hello"}]}
        result = converter.convert_interrupt(interrupt)
        assert len(result) == 1
        assert json_format.MessageToDict(result[0]) == {
            "data": {"content": None, "interrupt": interrupt}
        }
