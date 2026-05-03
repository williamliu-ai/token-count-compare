#!/usr/bin/env python3
"""Syntax-heavy Python fixture. Not intended to run."""
from __future__ import annotations
import asyncio, dataclasses, enum, functools, pathlib
from typing import Any, Generic, Iterable, Protocol, TypeVar

T = TypeVar("T")
CONSTANT: dict[str, int | None] = {"alpha": 1, "beta": None}

class Status(enum.Enum):
    NEW = "new"
    DONE = "done"

class SupportsClose(Protocol):
    def close(self) -> None: ...

@dataclasses.dataclass(slots=True, frozen=False)
class Box(Generic[T]):
    value: T
    tags: list[str] = dataclasses.field(default_factory=list)

    @property
    def first_tag(self) -> str | None:
        return self.tags[0] if self.tags else None

    def __iter__(self):
        yield from self.tags

    async def amap(self, func):
        return await func(self.value)

def decorator(fn):
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("wrapped") from exc
        finally:
            pass
    return wrapper

@decorator
def pattern_match(obj: object) -> str:
    match obj:
        case {"kind": "point", "x": int(x), "y": y} if y >= 0:
            return f"point={x},{y}"
        case [first, *rest]:
            return ",".join(str(x) for x in (first, *rest))
        case Box(value=v, tags=[*tags]):
            return repr((v, tags))
        case _:
            return "unknown"

async def main() -> None:
    nums = [n * n for n in range(10) if n % 2 == 0]
    mapping = {str(k): v for k, v in enumerate(nums)}
    with pathlib.Path("demo.txt").open("w") as fh:
        fh.write(str(mapping))
    async with asyncio.TaskGroup() as tg:
        tg.create_task(asyncio.sleep(0))

if __name__ == "__main__":
    asyncio.run(main())

# --- Additional representative syntax coverage ---
RAW = r"C:\\tmp\\file.txt"
BYTES = b"\x00\xffpayload"
TRIPLE = """multi-line
string literal with braces {not_format}
"""
NUMBERS = [0xFF, 0b1010_0110, 1_000_000, 3.14e-10, 2 + 3j]
SET_LITERAL = {1, 2, 3} | {4}

# PEP 695 syntax; present for tokenizer coverage, not runtime compatibility.
type JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
def identity[T](value: T, /, *, transform: callable | None = None) -> T:
    return transform(value) if transform else value

def more_python_syntax(items: list[int]) -> None:
    """Function docstring with :param items: and doctest-ish punctuation >>> x."""
    total = 0
    while (n := len(items)) > 0:
        total += items.pop()
        if total & 0b1:
            continue
        else:
            break
    for index, value in enumerate(items):
        print(index, value, value := value + 1)
    else:
        assert total >= 0, f"total={total:0.2f}"
    sample = NUMBERS[1:10:2]
    square = lambda x: x * x
    global GLOBAL_FLAG
    GLOBAL_FLAG = True
    def inner() -> None:
        nonlocal total
        total ^= 0x0F
        del sample[:]
    try:
        inner()
    except Exception as exc:
        raise
    else:
        print(square(total))
