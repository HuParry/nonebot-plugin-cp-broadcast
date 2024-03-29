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

除了简单的指令外，它支持每天定时发送三种比赛的信息。

查询的结果会存到列表里，以减少网站爬取的次数。

· Codeforces:
极负盛名的俄罗斯算法竞赛练习网站。相关的比赛播报乃至用户监视提醒功能均由Codeforces官方提供的api实现。当然由于是国外网站，在国内访问可能会比较缓慢。

· 牛客竞赛:
国内比较出名的找工作乃至练习算法的竞赛平台。比赛信息的获取是通过对网页爬取分析得到的。目前没开发出牛客竞赛的用户监视功能。

· AtCoder:
日本出名的算法竞赛平台。比赛信息的获取是通过对网页爬取分析得到的。目前没开发出AtCoder的用户监视功能。

为什么取 cp-broadcast 这个英文名呢？因为竞赛性编程的英文是：Competitive Programming，直接拿来做名字感觉太长了，因此我把它写成了缩写，broadcast 是播报的意思，因此就用 cp-broadcast 来当名字了。

插件可能有很多不完善的地方，欢迎大家来提 issue 和 pull requests。 

有任何问题可联系QQ：3411907440。

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

|           配置项            | 必填 |                     默认值                     |                                      说明                                      |
|:------------------------:|:----:|:-------------------------------------------:|:----------------------------------------------------------------------------:|
|    cp_broadcast_path     | 否 | get_data_dir("nonebot_plugin_cp_broadcast") |                        数据存储路径定义，用户不定义则由localstore插件确定                        |
|    cp_broadcast_list     | 否 |                     [ ]                     |                      开启早晨自动播报今日比赛的群聊，填 QQ 群号，注意以字符串形式填入                      |
|   cp_broadcast_botname   | 否 |                    "bot"                    |                    填入你 bot 的名字，在 `help` 指令下会使用到你的 bot 的名字                    |
|    cp_broadcast_time     | 否 |         {"hour":"7", "minute":"20"}         |             每日在群聊播报比赛信息的时间，默认是早上 7 点 20，你可以在配置文件中按默认值格式修改成你想要的时间             |
| cp_broadcast_updatetime  | 否 |         {"hour":"0", "minute":"0"}          |              每天自动更新比赛数据的时间，默认是 0 点 0 分，你可以在配置文件中按默认值格式修改成你想要的时间              |
|   cp_broadcast_cf_list   | 否 |                     [ ]                     |                   开启 Codeforces 播报功能的群聊，cf监视的相关功能只在指定群聊里发送                   |
| cp_broadcast_cf_interval | 否 |                     10                      | 更新 Codeforces 监视信息的时间间隙，默认为 10 分钟（不建议设置太短，可能会对服务器造成比较大的压力。另外监视人数多的话间隙尽量加长一点） |

就像这样：
```
cp_broadcast_path="data/cp_broadcast"
cp_broadcast_list=["xxxxxxxx"]
cp_broadcast_botname="bot"
cp_broadcast_time={"hour":"7", "minute":"20"}
cp_broadcast_updatetime={"hour":"0", "minute":"0"}
cp_broadcast_cf_list=["xxxxxxxx"]
cp_broadcast_cf_interval=10
```

该插件依赖 [nonebot_plugin_apscheduler](https://github.com/nonebot/plugin-apscheduler) 实现定时发送功能，如果你未安装此依赖的话，将无法触发与定时相关的功能。

## 🎉 使用
### 指令表
|      指令      | 权限 | 需要@ | 范围 |             说明              |
|:------------:|:----:|:----:|:----:|:---------------------------:|
|     `cf`     | 群员 | 否 | 群聊 |   发送最近三场 Codeforces 比赛的信息   |
| `牛客` or `nc` | 群员 | 否 | 群聊 |        发送最近三场牛客比赛的信息        |
|    `atc`     | 群员 | 否 | 群聊 |    发送最近两场 AtCoder 比赛的信息     |
|   `today`    | 群员 | 否 | 群聊 |          发送今天的比赛信息          |
|    `next`    | 群员 | 否 | 群聊 |        发送今天后的部分比赛信息         |
|    `help`    | 群员 | 是 | 群聊 |           发送帮助信息            |
|   `update`   | 群员 | 否 | 群聊 |          手动更新比赛信息           |
|    `cf监视`    | 群员 | 是 | 群聊 |       监视某人的 rating 变化       |
|   `cf监视移除`   | 群员 | 是 | 群聊 |      移除监视某人的 rating 变化      |
|   `cf监视列表`   | 群员 | 是 | 群聊 |         展示已经监视了哪些人          |
|    `cf查询`    | 群员 | 是 | 群聊 |        查询对应 id 的相关信息        |
|    `cf排名`    | 群员 | 是 | 群聊 |      查询当前监视列表的rating排名      |
|   `cf监视备注`   | 群员 | 是 | 群聊 | 给某个已经被监视的人备注一个名字，两字符串之间用空格隔开 |


### 效果图

<img src="./docs/cf.JPG" width="375"/>

<img src="./docs/nc.JPG" width="375" />

<img src="./docs/atc.JPG" width="375" />

<img src="./docs/today.JPG" width="375" />

<img src="./docs/next.JPG" width="375" />

<img src="./docs/help.png" width="375" />

<img src="./docs/update.JPG" width="375" />

<img src="./docs/cfjianshi.JPG" width="375" />

<img src="./docs/remove.png" width="375" />

<img src="./docs/cfjianshiliebiao.png" width="375" />

<img src="./docs/cfchaxun.JPG" width="375" />

<img src="./docs/cf_change.png" width="375" />

<img src="./docs/cf_change2.jpg" width="375" />

<img src="./docs/cf_paimin.JPG" width="375" />

<img src="./docs/cf_jianshi.JPG" width="375" />