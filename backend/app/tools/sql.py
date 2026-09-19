"""Read-only PostgreSQL SQL tool with AST and policy validation."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import sqlglot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import expressions as exp

from app.agents.state import JSONValue
from app.core.config import Settings, get_settings
from app.tools.registry import BaseTool, ToolContext, ToolError


class SqlQueryTool(BaseTool):
    """Execute only whitelisted PostgreSQL SELECT statements."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        allowed_tables: set[str] | frozenset[str] | None = None,
        timeout_seconds: float | None = None,
        row_limit: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        resolved_tables = allowed_tables if allowed_tables is not None else set(resolved.sql_allowed_tables)
        resolved_timeout = timeout_seconds if timeout_seconds is not None else resolved.sql_timeout_seconds
        resolved_row_limit = row_limit if row_limit is not None else resolved.sql_row_limit
        if resolved_timeout <= 0:
            raise ValueError("SQL timeout must be greater than zero")
        if resolved_row_limit <= 0:
            raise ValueError("SQL row limit must be greater than zero")
        self.session = session
        self.allowed_tables = frozenset(table.lower() for table in resolved_tables)
        self.timeout_seconds = resolved_timeout
        self.row_limit = resolved_row_limit

    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return "Run a read-only SELECT query against whitelisted business tables."

    @property
    def input_schema(self) -> dict[str, JSONValue]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

    async def execute(
        self,
        arguments: dict[str, JSONValue],
        context: ToolContext,
    ) -> JSONValue:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ToolError("SQL_INVALID_INPUT", "SQL query is required")
        try:
            safe_query = self._prepare_query(query)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError("SQL_INVALID_QUERY", "SQL query could not be validated") from exc
        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await self.session.execute(text(safe_query))
                rows = [self._json_object(dict(row)) for row in result.mappings().all()]
        except TimeoutError as exc:
            raise ToolError("SQL_TIMEOUT", "SQL query timed out") from exc
        except Exception as exc:
            raise ToolError("SQL_EXECUTION_FAILED", "SQL query execution failed") from exc
        return {
            "query": safe_query,
            "columns": list(rows[0]) if rows else [],
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(rows) >= self.row_limit,
        }

    def _prepare_query(self, query: str) -> str:
        statements = sqlglot.parse(query, read="postgres")
        if len(statements) != 1:
            raise ToolError("SQL_FORBIDDEN", "Only one SQL statement is allowed")
        statement = statements[0]
        if not isinstance(statement, exp.Select):
            raise ToolError("SQL_FORBIDDEN", "Only SELECT statements are allowed")
        cte_names = {
            cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE) if cte.alias_or_name
        }
        for table in statement.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name not in cte_names and table_name not in self.allowed_tables:
                raise ToolError("SQL_TABLE_NOT_ALLOWED", f"Table is not whitelisted: {table_name}")
        statement = statement.copy()
        existing_limit = statement.args.get("limit")
        if existing_limit is None:
            statement = statement.limit(self.row_limit)
        else:
            literal = existing_limit.expression
            if not isinstance(literal, exp.Literal) or not literal.is_number or int(literal.this) > self.row_limit:
                statement = statement.limit(self.row_limit)
        return statement.sql(dialect="postgres")

    @classmethod
    def _json_object(cls, row: dict[object, object]) -> dict[str, JSONValue]:
        return {str(key): cls._json_value(value) for key, value in row.items()}

    @classmethod
    def _json_value(cls, value: object) -> JSONValue:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (UUID, Decimal)):
            return str(value)
        if isinstance(value, list):
            return [cls._json_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._json_value(item) for key, item in value.items()}
        return str(value)
