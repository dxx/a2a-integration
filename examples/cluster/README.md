# 集群（多副本）部署示例

演示如何把 A2A 服务部署成多副本：多个进程共用同一个数据库，task 状态与事件流
放在共享存储里，任意副本都能读取其它副本创建的 task，也能回放其它副本产生的
事件流。

本示例基于 `HITLLangGraphAgent`（人工审批）。要跨副本续跑被中断的任务，需要两处
共享存储：

1. **A2A task 状态** —— 由 `create_shared_storage()` 提供的
   `VersionedDatabaseTaskStore` + `DatabaseTaskEventStream`。副本 B 才能读到副本 A
   创建的 `input-required` 任务。
2. **LangGraph 图状态** —— 由各副本共享的 checkpoint saver。副本 B 才能拿到副本 A
   被中断时保存的待恢复状态。否则 `Command(resume=...)` 会变成空操作且不报错。

**依赖**:
```bash
uv sync --group examples
```

**运行**:
```bash
# 副本 1
uv run python examples/cluster/server.py \
    --database-url "postgresql+asyncpg://postgres:postgres@localhost:5432/a2a" \
    --port 8080
# 副本 2（同一个数据库）
uv run python examples/cluster/server.py \
    --database-url "postgresql+asyncpg://postgres:postgres@localhost:5432/a2a" \
    --port 8081

# 客户端：跨副本的人工审批
uv run python examples/cluster/client.py
```

**主要功能**:
- 使用 `create_shared_storage()` 创建共享的 task 存储与事件流
- `A2AServerAgent` 注入 `shared_storage` / `interrupted_task_timeout`
- 存储的建表与 engine 的释放随 Agent 的启停自动完成
- 客户端第一轮发给副本 1 触发中断，第二轮发给副本 2 续跑完成

## 服务端参数

```bash
uv run python examples/cluster/server.py --help
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--database-url` | `postgresql+asyncpg://postgres:postgres@localhost:5432/a2a` | task 存储与事件流使用的数据库，需带异步驱动（`postgresql+asyncpg` / `mysql+aiomysql` / `sqlite+aiosqlite`） |
| `--host` | `127.0.0.1` | 监听地址 |
| `--port` | `8080` | 监听端口，多副本启动时各自换端口 |

停在 `input-required` / `auth-required` 的 task 空闲 300 秒后释放运行时占用，该值在
`server.py` 的 `INTERRUPTED_TASK_TIMEOUT` 常量里调整。

## 客户端环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `A2A_REPLICA1_URL` | `http://127.0.0.1:8080` | 客户端访问的副本 1 地址 |
| `A2A_REPLICA2_URL` | `http://127.0.0.1:8081` | 客户端访问的副本 2 地址 |

## checkpoint 文件

LangGraph 的 checkpoint 固定写在 `examples/cluster/a2a_checkpoints.sqlite`（脚本所在
目录的绝对路径），**所有副本共享同一个文件**。几个注意点：

- `AsyncSqliteSaver.from_conn_string()` 收的是 **SQLite 文件路径**（或 `file:` URI），
  不是 SQLAlchemy URL，写成 `sqlite+aiosqlite://...` 会报
  `OperationalError: unable to open database file`。
- 必须是绝对路径。相对路径在不同工作目录启动的副本会各写各的文件，表现为
  「恢复时图再次中断」这种静默失效。
- 父目录不会自动创建，不存在时会直接报错。

多副本生产部署建议把 checkpoint 换成 `AsyncPostgresSaver` 等数据库型 saver，
避免 SQLite 写并发与单机文件限制。
