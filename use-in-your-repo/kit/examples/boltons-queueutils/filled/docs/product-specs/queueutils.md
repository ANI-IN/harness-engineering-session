# queueutils

Priority queues with one API for two backends (`boltons/queueutils.py`).

## Queues

| Class | Backend |
|---|---|
| `HeapPriorityQueue` | a list ordered with `heapq.heappush` and `heapq.heappop` |
| `SortedPriorityQueue` (also `PriorityQueue`) | a `BarrelList` from `listutils` (a plain `list` when `listutils` is missing), kept sorted with `bisect.insort` |

## Behaviour

| Call | Result |
|---|---|
| `add(task, priority=None)` | adds a hashable task; adding a task that is already queued changes its priority; `priority` defaults to 0 |
| `remove(task)` | removes the task; raises `KeyError` if it is not queued |
| `peek(default)` | the next task, left in the queue; on an empty queue returns `default` if given, else raises `IndexError` |
| `pop(default)` | the next task, removed; on an empty queue returns `default` if given, else raises `IndexError` |
| `len(queue)` | the number of queued tasks |

Higher priorities come out first. Tasks with the same priority come out in the order they were
added. `priority_key` in the constructor changes how a priority is turned into a number.
