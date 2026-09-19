"""Safe arithmetic calculator tool."""

import ast
import math
import operator
from typing import ClassVar

from app.agents.state import JSONValue
from app.tools.registry import BaseTool, ToolContext, ToolError


class CalculatorTool(BaseTool):
    """Evaluate a bounded arithmetic expression without dynamic code execution."""

    _binary_operators: ClassVar = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary_operators: ClassVar = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Evaluate a simple arithmetic expression."

    @property
    def input_schema(self) -> dict[str, JSONValue]:
        return {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        }

    async def execute(
        self,
        arguments: dict[str, JSONValue],
        context: ToolContext,
    ) -> JSONValue:
        expression = arguments.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ToolError("CALCULATOR_INVALID_INPUT", "Calculator expression must be a non-empty string")
        if len(expression) > 200:
            raise ToolError("CALCULATOR_INVALID_INPUT", "Calculator expression is too long")
        try:
            tree = ast.parse(expression, mode="eval")
            value = self._evaluate(tree.body)
        except ToolError:
            raise
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            raise ToolError("CALCULATOR_INVALID_EXPRESSION", "Calculator expression is invalid") from exc
        if not math.isfinite(float(value)) or abs(value) > 1_000_000_000_000:
            raise ToolError("CALCULATOR_RESULT_OUT_OF_RANGE", "Calculator result is out of range")
        return {"expression": expression.strip(), "result": value}

    @classmethod
    def _evaluate(cls, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                raise ToolError("CALCULATOR_INVALID_EXPRESSION", "Boolean values are not supported")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in cls._binary_operators:
            left = cls._evaluate(node.left)
            right = cls._evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ToolError("CALCULATOR_RESULT_OUT_OF_RANGE", "Exponent is too large")
            return cls._binary_operators[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in cls._unary_operators:
            return cls._unary_operators[type(node.op)](cls._evaluate(node.operand))
        raise ToolError("CALCULATOR_INVALID_EXPRESSION", "Only arithmetic operators are supported")
