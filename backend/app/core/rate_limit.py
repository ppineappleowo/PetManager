"""业务层限流契约；实现不应依赖用户仓库。"""
from typing import Protocol


class RateLimiter(Protocol):
    def consume_attempt(self, scopes: list[tuple[str, int]], window: int) -> int:
        """原子预占所有范围；允许返回 0，否则返回等待秒数。"""
        ...
