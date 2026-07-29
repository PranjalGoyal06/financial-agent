import asyncio
from typing import Any, Coroutine

async def run_concurrently(tasks: list[Coroutine], execute_async: bool = True, return_exceptions: bool = False) -> list[Any]:
    """Execute a list of tasks either concurrently or sequentially.
    
    Args:
        tasks: List of awaitable tasks.
        execute_async: If True, uses asyncio.gather to run tasks concurrently. If False, runs them sequentially.
        return_exceptions: Same behavior as asyncio.gather(..., return_exceptions).
    
    Returns:
        List of results in the same order as tasks.
    """
    if execute_async:
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)
    
    results = []
    for task in tasks:
        try:
            res = await task
            results.append(res)
        except Exception as e:
            if return_exceptions:
                results.append(e)
            else:
                raise
    return results
