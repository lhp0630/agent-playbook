import io
from itertools import chain
from typing import Any

import pandas as pd
from pydantic_ai import (
    BinaryContent,
    ModelRequest,
    ModelRequestContext,
    RunContext,
    UserContent,
    UserPromptPart,
)
from pydantic_ai.capabilities import Hooks


async def convert_office_to_markdown(
    ctx: RunContext[Any],
    request_context: ModelRequestContext,
) -> ModelRequestContext:
    request_parts = [
        *chain.from_iterable(
            message.parts
            for message in request_context.messages
            if isinstance(message, ModelRequest)
        )
    ]

    for part in request_parts:
        if not isinstance(part, UserPromptPart) or isinstance(part.content, str):
            continue

        new_content: list[str | UserContent] = []

        for item in part.content:
            if (
                isinstance(item, BinaryContent)
                and item.is_document
                and item.format in ["xlsx", "xls"]
            ):
                new_content.append(_excel_to_markdown(item.data))
            else:
                new_content.append(item)

        part.content = new_content

    return request_context


def _excel_to_markdown(content: BinaryContent) -> str:
    vendor_metadata = content.vendor_metadata

    title: str = content.identifier
    if vendor_metadata:
        if "filename" in vendor_metadata:
            title = vendor_metadata.pop("filename")
        elif "markdown_title" in vendor_metadata:
            title = vendor_metadata.pop("markdown_title")

    df_sheets = pd.read_excel(io.BytesIO(content.data), engine="calamine", sheet_name=None)

    markdown_parts: list[str] = [f"# {title}"]

    for sheet, df in df_sheets.items():
        markdown_parts.append(f"## {sheet}\n{df.to_markdown(index=False)}")

    return "\n".join(markdown_parts)


hooks = Hooks()
hooks.before_model_request(convert_office_to_markdown)
