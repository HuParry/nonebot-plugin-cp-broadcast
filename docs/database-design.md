# Codeforces JSON 数据设计

## 文件位置与格式

Codeforces 用户资料、监视状态和 rating 历史统一保存在 `cp_broadcast_path/data.json`。默认目录由 `nonebot_plugin_localstore` 提供；设置 `cp_broadcast_path` 后，JSON 文件会放在指定目录中。

顶层 `users` 是以小写规范 handle 为键的对象。每个用户分成 `profile`、`monitor` 和 `rating_history` 三部分：

```json
{
  "version": 1,
  "users": {
    "example_handle": {
      "profile": {
        "handle": "example_handle",
        "first_name": null,
        "last_name": null,
        "country": null,
        "city": null,
        "organization": null,
        "contribution": 0,
        "rank": "expert",
        "rating": 1600,
        "max_rank": "expert",
        "max_rating": 1700,
        "last_online_time_seconds": 1760000000,
        "registration_time_seconds": 1600000000,
        "friend_of_count": 0,
        "avatar": null,
        "title_photo": null,
        "fetched_at_seconds": 1780000000
      },
      "monitor": {
        "remarks": "example_handle",
        "created_at_seconds": 1780000000,
        "last_processed_submission_id": 295818395,
        "last_submission_event_at_seconds": 1780000000,
        "last_notified_submission_id": 295818395,
        "last_submission_notice_at_seconds": 1780000000,
        "last_notified_rating_update_time_seconds": 1706633100,
        "last_notified_rating_contest_id": 1918,
        "delivery_attempts": {
          "123456789": {
            "submission_id": 295818395,
            "submission_attempt_at_seconds": 1780000000,
            "rating_update_time_seconds": 1706633100,
            "rating_contest_id": 1918
          }
        }
      },
      "rating_history": {
        "123456": {
          "contest_id": 123456,
          "contest_name": "Example Contest",
          "rank": 100,
          "rating_update_time_seconds": 1760000000,
          "old_rating": 1500,
          "new_rating": 1600
        }
      }
    }
  }
}
```

上例中的 Unix 时间仅用于说明字段格式。Codeforces API 可能不返回某些可选资料字段；JSON 使用 `null` 表示缺失值，不用 `0` 代替未知数据。`rating_history` 是以 contest ID 为键的映射，便于去重和直接查找某场比赛。

## 为什么按这三类数据组织

2026-09-29 用 `HuParry` 查询了插件配置的三个 Codeforces API 地址：[`user.info`](https://codeforces.com/api/user.info?handles=HuParry)、[`user.status`](https://codeforces.com/api/user.status?handle=HuParry&from=1&count=1)、[`user.rating`](https://codeforces.com/api/user.rating?handle=HuParry)。返回结构分别是用户资料对象、最近一条提交和比赛 rating 历史数组。

- `profile` 保存 `user.info` 的当前快照，包括姓名、组织、当前/最高 rating、段位、头像和时间字段。
- `monitor` 保存插件自身的备注、导入时间、提醒水位和冷却时间。
- `rating_history` 是 API rating 历史的有限快照：每次成功获取 API 列表后整体替换，只保留更新时间最新的 5 场（不足 5 场时全部保留）。contest ID 作为对象键。API 请求失败时保留上一次成功获取的快照。
- `user.status` 请求固定使用 `from=1&count=1`，只取最新提交。`monitor.last_processed_submission_id` 保存已在查询中处理的最新提交 ID，无论是否生成通知或是否发送成功，都在本轮查询中推进并保存；`last_notified_submission_id` 只保存实际发送成功的提交 ID。API 的 contest ID 和提交时间用于生成消息，不保留整份提交记录。

用户资料中保存本插件实际需要的公开字段，不保存可能包含隐私内容且当前功能不用的字段。字段未返回时保留为 `null`。

## 读写与文件安全

- 启动时创建数据目录。如果 `data.json` 不存在，就写入空结构：`{"version": 1, "users": {}}`。
- 添加或刷新用户时更新 `profile`，并用 API 返回的 rating 历史整体替换旧快照，只保存最近 5 场。重新执行 `cf监视 <handle>` 会刷新资料和历史，但保留已有备注和提醒游标。
- 启动时若文件中某个用户的 `rating_history` 超过 5 场，会按更新时间保留最新 5 场，并将规范化结果写回文件。轮询处理新 rating 通知时仍使用本次完整 API 响应，因此历史条数上限不会限制通知检测。
- 删除用户时，从 `users` 中删除该 handle 对应的整个对象。
- 修改备注时只更新 `monitor.remarks`。
- 每次写入先生成同目录临时文件，完成 JSON 序列化并同步写盘后，再用原子替换更新 `data.json`。内存状态只在文件替换成功后更新。
- 数据由进程内异步锁串行修改。启动时持有 `.cp-broadcast.lock` 的系统文件锁直到进程关闭；第二个使用同一目录的进程会启动失败，防止互相覆盖状态、重复发消息。锁文件不保存业务数据，也不会在退出时删除；系统在进程退出后释放锁。不同目录的数据独立，部署时仍应停止旧机器人实例。
- 若文件 JSON 格式错误或版本号不支持，插件启动会报错并保留原文件，不会自动清空或覆盖它。
- 插件内所有 Codeforces API 请求（监视、用户查询和比赛查询）共用异步限速锁，按单调时钟确保请求开始至少间隔 2.1 秒，满足[官方每 2 秒最多请求一次的限制](https://codeforces.com/apiHelp)。请求失败也会计入限速；头像下载不属于 API 请求。

## 通知处理逻辑

rating 通知水位由 `(last_notified_rating_update_time_seconds, last_notified_rating_contest_id)` 组成，以更新时间和 contest ID 的字典序识别新比赛记录。同一轮中水位之后的所有 rating 记录都会生成通知。

提交监视只比较本次最新提交 ID 与上次保存的 ID 是否不同，不比较 ID 大小，也不比较评测状态等其他字段。添加用户时，成功获取的最新提交只作为基线；成功返回空列表时基线为 `0`，后续首次提交可以触发提醒。请求失败时基线为 `null`，第一次成功获取记录时只建立基线，避免把历史提交当成新活动。后续请求失败不改变基线，相同 ID 不会触发提醒；成功返回空列表也不会清除已有的真实提交 ID。

`last_notified_submission_id` 初始为 `0`，仅在成功发送后更新；`last_submission_notice_at_seconds` 保存最近一次成功通知时间。这两个字段不负责推进提交检测游标。

提交检测将不同的有效提交 ID 视为新提交，即使新 ID 数值更小。一旦观察到不同 ID，立即在本轮候选数据中更新 `last_processed_submission_id`；符合冷却条件时再生成事件，并保存生成时间 `last_submission_event_at_seconds`。候选数据成功写入 JSON 后，函数才返回事件；写入失败会直接报错，事件不会传给发送端。相同 ID 在后续轮询中直接跳过，不依赖发送成功确认，也不依赖按群去重才能避免重复判定。

全局活动检测从生成事件时开始 7200 秒冷却，使用事件生成时间，不依赖成功发送时间。冷却期内查询到的新提交会记录为已处理，不生成事件，不会在冷却结束后补发；即使 API 延迟返回，提交时间位于冷却期内也会跳过。发送失败或确认写入失败不会清除冷却状态。一轮有多次提交时，只检测 API 返回的最新一条。各群另通过独立的尝试时间执行同样的 7200 秒冷却，作为发送端保护。

通知在每个群中独立处理：

1. 将群号统一成字符串并去除重复配置。
2. 在 `monitor.delivery_attempts[群号]` 检查对应水位。提交 ID 相同、rating 水位未递增或提交处于该群冷却期时跳过。
3. 在调用发送接口之前，原子写入预留记录。提交记录保存 `submission_id`、`submission_attempt_at_seconds`；rating 记录保存 `(rating_update_time_seconds, rating_contest_id)`。冷却期内的新提交也会推进该群提交水位，但不会延长冷却期。
4. 只有预留落盘成功才发送。发送成功后单独更新全局已通知水位；一个群或一条消息失败不会阻止其他群、其他消息继续处理。

预留记录在发送失败、超时、取消或进程退出后保留，最新提交 ID 连续保持不变时，同一群只尝试发送一次。确认信息写入失败也不会绕过去重记录。记录按用户和群覆盖水位，不逐条追加通知历史。

这种策略优先避免重复刷屏：发送前退出、发送失败或超时可能导致提醒丢失，插件不会自动重发。即使 API 连续返回同一事件、多个轮询并发运行，预留也只会成功一次；定时任务另设 `max_instances=1` 和 `coalesce=True`。消息使用“检测到新提交”并展示提交 ID 和实际提交时间；API 没有返回 contest ID 时不会显示 `None`。

部署更新后，启动日志会包含“已启用按群持久化去重（发送前预留，失败不自动重发）”。如果群里仍出现旧的“卷王……又开始上cf做题啦”文案，需要排查旧进程或实际加载的插件安装目录。

## 重新添加监视用户

本实现不读取或迁移 SQLite 数据，也不使用旧版 `data.db`。首次启动会创建空的 `data.json`。切换到 JSON 存储后，请对每个需要监视的用户逐个发送 `cf监视 <handle>`；备注可之后用 `cf监视备注 <handle> <备注>` 设置。

## 源码位置

- JSON 文件存储、校验、原子写入、Codeforces API 数据模型及监视逻辑：[`nonebot_plugin_cp_broadcast/json_store.py`](../nonebot_plugin_cp_broadcast/json_store.py)
- Codeforces 指令入口：[`nonebot_plugin_cp_broadcast/codeforces.py`](../nonebot_plugin_cp_broadcast/codeforces.py)
- 定时任务入口：[`nonebot_plugin_cp_broadcast/__init__.py`](../nonebot_plugin_cp_broadcast/__init__.py)
- 按群去重、发送和失败隔离：[`nonebot_plugin_cp_broadcast/broadcast.py`](../nonebot_plugin_cp_broadcast/broadcast.py)
- 数据目录配置及 API 地址：[`nonebot_plugin_cp_broadcast/config.py`](../nonebot_plugin_cp_broadcast/config.py)
