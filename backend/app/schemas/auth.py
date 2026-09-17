"""认证进出契约：凭据校验与用户输出。

校验规则是硬契约：username 3–32 位（提交前 strip，仅字母/数字/下划线）、
password 6–64 位，违规一律 422。service 与 schema 不 import fastapi。
"""
import re
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

_USERNAME_PATTERN = re.compile(r"^\w+$", re.ASCII)


class Credentials(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        value = value.strip()
        if not 3 <= len(value) <= 32 or not _USERNAME_PATTERN.fullmatch(value):
            raise ValueError("用户名需为 3–32 位字母、数字或下划线")
        return value

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if not 6 <= len(value) <= 64:
            raise ValueError("密码长度需为 6–64 位")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
