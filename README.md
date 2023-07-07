<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-cp-broadcast

_✨ 一个 Codeforces、牛客竞赛、AtCoder 平台的编程竞赛查询插件，ACMer必备 ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/HuParry/nonebot-plugin-cp-broadcast.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-cp-broadcast">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-cp-broadcast.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">

</div>

## 📖 介绍

对于每一个 ACMer 来说，参加编程竞赛是必不可少的，这个插件实现了 Codeforces、牛客竞赛、AtCoder 这三个主流的编程竞赛平台的比赛查询和播报。

## 💿 安装

<details>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-cp-broadcast

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-cp-broadcast
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-cp-broadcast
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-cp-broadcast
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-cp-broadcast
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_cp_broadcast"]

</details>

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| cp_broadcast_list | 否 | [ ] | 开启早晨自动播报今日比赛的群聊，填 QQ 群号，注意以字符串形式填入 |
| cp_broadcast_botname | 否 | "bot" | 填入你 bot 的名字，在 `help` 指令下会使用到你的 bot 的名字 |
| cp_broadcast_time | 否 | {"hour":"7", "minute":"20"} | 每日在群聊播报比赛信息的时间，默认是早上 7 点 20，你可以在配置文件中按默认值格式修改成你想要的时间，注意需要安装 `nonebot_plugin_apscheduler` 插件以实现定时效果。 |
| cp_broadcast_updatetime | 否 | {"hour":"0", "minute":"0"} | 每天自动更新比赛数据的时间，默认是 0 点 0 分，你可以在配置文件中按默认值格式修改成你想要的时间，注意需要安装 `nonebot_plugin_apscheduler` 插件以实现定时效果。 |

## 🎉 使用
### 指令表
| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| `cf` | 群员 | 否 | 群聊 | 发送最近三场 Codeforces 比赛的信息 |
| `牛客` or `nc` | 群员 | 否 | 群聊 | 发送最近三场牛客比赛的信息 |
| atc | 群员 | 否 | 群聊 | 发送最近两场 AtCoder 比赛的信息 |
| today | 群员 | 否 | 群聊 | 发送今天的比赛信息 |
| next | 群员 | 否 | 群聊 | 发送今天后的部分比赛信息 |
| help | 群员 | 否 | 群聊 | 发送帮助信息 |
| update | 群员 | 否 | 群聊 | 手动更新比赛信息 |
### 效果图
<img src="./docs/preview.webp" style="zoom:30%;" />

这是本蒟蒻的第一个上传至 pypi 的 nonebot 项目，可能有很多不完善的地方，欢迎大家来 pull requests。 

有任何问题可联系QQ：3411907440
