"""共享存储组合。

task 的状态与事件流可以放在共享存储里，从而让多个进程（同一台机器上的多个
worker，或多台机器上的多个副本）看到同一份 task。本模块提供两个入口：

- `create_shared_storage()`：`DatabaseTaskStore`，只共享 task 状态。
- `create_cluster_shared_storage()`：`VersionedDatabaseTaskStore` +
  `DatabaseTaskEventStream`，共享 task 状态并支持跨副本回放事件流。

两者都负责建表与资源释放。

典型用法::

    from sqlalchemy.ext.asyncio import create_async_engine
    from a2a_server import A2AServerAgent
    from a2a_server.storage import create_shared_storage

    engine = create_async_engine("postgresql+asyncpg://...")
    storage = create_shared_storage(engine)

    agent = A2AServerAgent(
        agent=my_agent,
        agent_card=card,
        shared_storage=storage,
        interrupted_task_timeout=300,
    )

    app = FastAPI()
    agent.attach_app_server(app)

`shared_storage` 传入后，存储的建表与释放会随 Agent 的启停一起完成，
不再需要单独管理存储的生命周期。

注意：跨副本事件流要求 `task_store` 与 `event_stream` 共用同一个数据库。
事件由 `VersionedTaskStore` 在写 task 快照的同一事务里追加到 `task_events`
表，`DatabaseTaskEventStream` 再轮询该表；分成两个库会导致跨副本订阅读不到
任何事件。
"""

from dataclasses import dataclass
from typing import Any

from a2a.server.tasks.task_store import TaskStore
from a2a.server.cluster.event_stream import TaskEventStream
from a2a.server.cluster.task_store import VersionedTaskStore
from a2a.server.owner_resolver import OwnerResolver, resolve_user_scope


@dataclass
class SharedStorage:
    """共享的 task 状态与事件流存储组合。

    作为 `A2AServerAgent` 的 `shared_storage` 参数传入，存储的建表与释放
    会随 Agent 的启停一起完成。

    Attributes:
        task_store: task 状态存储。

            - `VersionedDatabaseTaskStore`：带乐观并发保护，**多副本部署必须用它**。
            - `DatabaseTaskStore`：无版本控制，适合单进程持久化或多 worker 共享。
            - `InMemoryTaskStore`：仅当前进程可见，仅适合单副本。
        event_stream: 跨副本事件流，用于让其他副本回放本副本产生的事件。
            为 `None` 表示不启用跨副本事件流。

            搭配 `DatabaseTaskEventStream` 时，`task_store` 必须是
            `VersionedTaskStore` —— 那张事件日志表只有版本化存储才会写。
        engine: 底层 SQLAlchemy engine，`aclose()` 时释放。
    """

    task_store: TaskStore | VersionedTaskStore
    event_stream: TaskEventStream | None = None
    engine: Any | None = None

    async def initialize(self) -> None:
        """建表。

        `DatabaseTaskStore` 只建 `tasks`；`VersionedDatabaseTaskStore` 额外建
        `task_versions`，`DatabaseTaskEventStream` 建 `task_events`。

        存储实现本身也会在首次读写时惰性建表，这里提前调用是为了让
        schema 问题在服务启动阶段就暴露出来。
        """

        for resource in (self.task_store, self.event_stream):
            if resource is None:
                continue
            initialize = getattr(resource, 'initialize', None)
            if initialize is not None:
                await initialize()

    async def aclose(self) -> None:
        """释放 engine。"""

        if self.engine is not None:
            await self.engine.dispose()


def create_shared_storage(
    engine: Any,
    create_table: bool = True,
    owner_resolver: OwnerResolver = resolve_user_scope,
) -> SharedStorage:
    """创建基于数据库的共享存储。

    task 状态落到数据库里，同一份 task 对多个进程可见：同一台机器上的多个
    worker，或多台机器上的多个副本，都能读到对方创建的 task。

    这里用的是 `DatabaseTaskStore`：只写 `tasks` 表，没有版本控制，也不启用
    跨副本事件流。适合「多副本共享 task 状态，但事件流由请求方自己驱动」的
    场景。

    需要跨副本回放事件流时用 `create_cluster_shared_storage()`：它用带乐观
    并发保护的 `VersionedDatabaseTaskStore` + `DatabaseTaskEventStream`，
    其它副本才能订阅到正在运行的 task 的后续事件。

    Args:
        engine: SQLAlchemy AsyncEngine。
        create_table: 是否在初始化时建表（`tasks`）。
        owner_resolver: owner 作用域解析函数，决定 task 在不同用户间的
            隔离方式。默认取 `context.user.user_name`。多个副本必须解析出
            相同的 owner，否则互相看不到对方的 task。

    Returns:
        组合好的 `SharedStorage`，`event_stream` 为 `None`。

    Raises:
        ImportError: 未安装 SQLAlchemy 与数据库驱动时抛出。
    """

    from a2a.server.tasks import DatabaseTaskStore

    task_store = DatabaseTaskStore(
        engine=engine,
        create_table=create_table,
        owner_resolver=owner_resolver,
    )

    return SharedStorage(
        task_store=task_store,
        event_stream=None,
        engine=engine,
    )


def create_cluster_shared_storage(
    engine: Any,
    create_table: bool = True,
    poll_interval_s: float = 0.5,
    owner_resolver: OwnerResolver = resolve_user_scope,
) -> SharedStorage:
    """创建基于集群的共享存储。

    Args:
        engine: SQLAlchemy AsyncEngine。
        create_table: 是否在初始化时建表。
        poll_interval_s: 事件流的轮询间隔（秒）。
        owner_resolver: owner 作用域解析函数，决定 task 在不同用户间的
            隔离方式。默认取 `context.user.user_name`。

    Returns:
        组合好的 `SharedStorage`。
    """

    from a2a.server.cluster import (
        DatabaseTaskEventStream,
        VersionedDatabaseTaskStore,
    )

    task_store = VersionedDatabaseTaskStore(
        engine=engine,
        create_table=create_table,
        owner_resolver=owner_resolver,
    )
    event_stream = DatabaseTaskEventStream(
        engine=engine,
        create_table=create_table,
        poll_interval_s=poll_interval_s,
    )

    return SharedStorage(
        task_store=task_store,
        event_stream=event_stream,
        engine=engine,
    )
