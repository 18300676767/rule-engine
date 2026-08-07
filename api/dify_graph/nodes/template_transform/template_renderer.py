from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from dify_graph.nodes.code.code_node import WorkflowCodeExecutor
from dify_graph.nodes.code.entities import CodeLanguage


class TemplateRenderError(ValueError):
    """Raised when rendering a Jinja2 template fails."""


class Jinja2TemplateRenderer(Protocol):
    """Render Jinja2 templates for template transform nodes."""

    def render_template(self, template: str, variables: Mapping[str, Any]) -> str:
        """Render a Jinja2 template with provided variables."""
        raise NotImplementedError


class CodeExecutorJinja2TemplateRenderer(Jinja2TemplateRenderer):
    """Adapter that renders Jinja2 templates via CodeExecutor."""

    _code_executor: WorkflowCodeExecutor

    def __init__(self, code_executor: WorkflowCodeExecutor) -> None:
        self._code_executor = code_executor

    def render_template(self, template: str, variables: Mapping[str, Any]) -> str:
        try:
            result = self._code_executor.execute(language=CodeLanguage.JINJA2, code=template, inputs=variables)
        except Exception as exc:
            if self._code_executor.is_execution_error(exc):
                raise TemplateRenderError(str(exc)) from exc
            raise

        rendered = result.get("result")
        if not isinstance(rendered, str):
            raise TemplateRenderError("Template render result must be a string.")
        return rendered


class InProcessJinja2TemplateRenderer:
    """Renders Jinja2 templates in-process using the Jinja2 library directly.

    This avoids the Sandbox overhead by rendering templates in the current Python process.
    Suitable for simple template rendering without code execution.
    """

    def render_template(self, template: str, variables: Mapping[str, Any]) -> str:
        try:
            from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

            env = Environment(undefined=StrictUndefined)
            tmpl = env.from_string(template)
            rendered = tmpl.render(**variables)
        except TemplateSyntaxError as e:
            raise TemplateRenderError(f"Template syntax error: {e}") from e
        except UndefinedError as e:
            raise TemplateRenderError(f"Undefined variable in template: {e}") from e
        except Exception as e:
            raise TemplateRenderError(f"Template render failed: {e}") from e

        if not isinstance(rendered, str):
            raise TemplateRenderError("Template render result must be a string.")
        return rendered
