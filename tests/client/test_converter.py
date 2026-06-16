from google.protobuf import json_format

import pytest

from a2a.types import Part
from a2a_client.converter import (
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

    def test_convert_content_with_string(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        result = converter.convert_content("hello")
        assert len(result) == 1
        assert json_format.MessageToDict(result[0]) == {
            "data": {"content": "hello", "resume": None}
        }

    def test_convert_content_with_dict(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        content = {"type": "ai", "text": "你好"}
        result = converter.convert_content(content)
        assert len(result) == 1
        assert json_format.MessageToDict(result[0]) == {
            "data": {"content": content, "resume": None}
        }

    def test_convert_resume_with_dict(
        self, converter: DefaultRequestPartConverter
    ) -> None:
        resume = {"decisions": [{"type": "approve"}]}
        result = converter.convert_resume(resume)
        assert len(result) == 1
        assert json_format.MessageToDict(result[0]) == {
            "data": {"content": None, "resume": resume}
        }


class TestDefaultResponsePartConverter:
    @pytest.fixture
    def converter(self) -> DefaultResponsePartConverter:
        return DefaultResponsePartConverter()

    # convert_atifact_part
    def test_convert_atifact_part_empty_list(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        assert converter.convert_atifact_part([]) == ""

    def test_convert_atifact_part_no_data(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        parts = [_make_text_part("hello")]
        assert converter.convert_atifact_part(parts) == ""

    def test_convert_atifact_part_with_content(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        parts = [_make_data_part({"content": "hello world"})]
        assert converter.convert_atifact_part(parts) == "hello world"

    def test_convert_atifact_part_without_content(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        parts = [_make_data_part({"other": "field"})]
        assert converter.convert_atifact_part(parts) == ""

    def test_convert_atifact_part_multiple_data(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        parts = [
            _make_data_part({"content": "first"}),
            _make_data_part({"content": "second"}),
        ]
        assert converter.convert_atifact_part(parts) == "first"

    # convert_interrupt_part
    def test_convert_interrupt_part_empty_list(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        assert converter.convert_interrupt_part([]) == {}

    def test_convert_interrupt_part_no_data(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        parts = [_make_text_part("hello")]
        assert converter.convert_interrupt_part(parts) == {}

    def test_convert_interrupt_part_with_interrupt(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        interrupt = {"action_requests": [{"name": "write_file", "args": "hello"}]}
        parts = [_make_data_part({"interrupt": interrupt})]
        assert converter.convert_interrupt_part(parts) == interrupt

    def test_convert_interrupt_part_without_interrupt(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        parts = [_make_data_part({"other": "field"})]
        assert converter.convert_interrupt_part(parts) == {}

    def test_convert_interrupt_part_multiple_data(
        self, converter: DefaultResponsePartConverter
    ) -> None:
        parts = [
            _make_data_part({"interrupt": {"a": 1}}),
            _make_data_part({"interrupt": {"b": 2}}),
        ]
        assert converter.convert_interrupt_part(parts) == {"a": 1}
