# AstrBot 插件开发文档提取版

说明：

- 原入口页 `https://astrbot.app/dev/plugin.html` 已迁移到新的插件开发章节。
- 本文件按官方章节合并整理为单个 Markdown 文档，便于离线保存和检索。
- 官方页面中的配图、截图类内容未全部内嵌，相关位置会标注“配图省略”。

来源页面：

- https://docs.astrbot.app/dev/star/plugin-new.html
- https://docs.astrbot.app/dev/star/guides/simple.html
- https://docs.astrbot.app/dev/star/guides/listen-message-event.html
- https://docs.astrbot.app/dev/star/guides/send-message.html
- https://docs.astrbot.app/dev/star/guides/plugin-config.html
- https://docs.astrbot.app/dev/star/guides/ai.html
- https://docs.astrbot.app/dev/star/guides/storage.html
- https://docs.astrbot.app/dev/star/guides/html-to-pic.html
- https://docs.astrbot.app/dev/star/guides/session-control.html
- https://docs.astrbot.app/dev/star/guides/other.html
- https://docs.astrbot.app/dev/star/plugin-publish.html

---

## 1. AstrBot 插件开发指南

来源：https://docs.astrbot.app/dev/star/plugin-new.html

欢迎来到 AstrBot 插件开发指南。开始之前，官方建议你具备以下基础：

1. 有一定的 Python 编程经验。
2. 有一定的 Git、GitHub 使用经验。

开发者交流群：`975206796`

### 1.1 环境准备

#### 获取插件模板

1. 打开 AstrBot 插件模板：`https://github.com/AstrBotDevs/helloworld`
2. 点击右上角 `Use this template`
3. 点击 `Create new repository`
4. 填写仓库名，要求：
   - 推荐以 `astrbot_plugin_` 开头
   - 不能包含空格
   - 保持全部字母小写
   - 尽量简短
5. 点击 `Create repository`

#### 克隆项目到本地

```bash
git clone https://github.com/AstrBotDevs/AstrBot
mkdir -p AstrBot/data/plugins
cd AstrBot/data/plugins
git clone 插件仓库地址
```

然后使用 `VSCode` 打开 `AstrBot` 项目，并找到 `data/plugins/<你的插件名字>` 目录。

#### 修改 `metadata.yaml`

AstrBot 识别插件元数据依赖 `metadata.yaml`，必须修改。

#### 设置插件 Logo（可选）

可以在插件目录下添加 `logo.png` 作为插件 Logo。官方建议：

- 长宽比 `1:1`
- 推荐尺寸 `256x256`

#### 插件展示名（可选）

可在 `metadata.yaml` 中增加或修改 `display_name` 字段，作为插件市场等场景中的展示名。

#### 声明支持平台（可选）

可以在 `metadata.yaml` 中新增 `support_platforms` 字段：

```yaml
support_platforms:
  - telegram
  - discord
```

`support_platforms` 中的值需要使用 `ADAPTER_NAME_2_TYPE` 的 key，目前支持：

- `aiocqhttp`
- `qq_official`
- `telegram`
- `wecom`
- `lark`
- `dingtalk`
- `discord`
- `slack`
- `kook`
- `vocechat`
- `weixin_official_account`
- `satori`
- `misskey`
- `line`

#### 声明 AstrBot 版本范围（可选）

可以在 `metadata.yaml` 中新增 `astrbot_version` 字段，格式遵循 PEP 440，且不要加 `v` 前缀：

```yaml
astrbot_version: ">=4.16,<5"
```

常见写法：

- `>=4.17.0`
- `>=4.16,<5`
- `~=4.17`

如果当前 AstrBot 版本不满足该范围，插件会被阻止加载；在 WebUI 安装插件时可以选择忽略警告继续安装。

### 1.2 调试插件

AstrBot 使用运行时注入插件，因此调试时需要启动 AstrBot 本体。推荐使用热重载：

- 在 WebUI 插件管理中找到插件
- 点击右上角 `...`
- 选择 `重载插件`

如果因为代码错误导致加载失败，也可以在管理面板中点击“尝试一键重载修复”。

### 1.3 插件依赖管理

插件依赖通过 `requirements.txt` 管理。如果插件依赖第三方库，务必在插件目录中创建 `requirements.txt`，避免用户安装后出现 `Module Not Found`。

### 1.4 开发原则

- 功能需经过测试。
- 需包含良好的注释。
- 持久化数据请存储于 `data` 目录下，而不是插件自身目录，防止更新或重装时被覆盖。
- 做好错误处理，不要让插件因单个错误崩溃。
- 提交前使用 `ruff` 格式化代码。
- 不要使用 `requests` 发网络请求，建议使用 `aiohttp`、`httpx` 等异步库。
- 如果是给已有插件增强功能，优先给原插件提 PR，而不是重复造轮子。

---

## 2. 最小实例

来源：https://docs.astrbot.app/dev/star/guides/simple.html

插件模板中的 `main.py` 是一个最小可运行示例：

```python
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        logger.info("触发hello world指令!")
        yield event.plain_result(f"Hello, {user_name}!")

    async def terminate(self):
        """可选择实现 terminate 函数，当插件被卸载/停用时会调用。"""
```

解释：

- 插件类需要继承 `Star`
- `Context` 用于插件与 AstrBot Core 交互
- 具体的处理函数 `Handler` 在插件类中定义
- `AstrMessageEvent` 存储消息发送者、消息内容等信息
- `AstrBotMessage` 是平台下发的消息对象，可通过 `event.message_obj` 获取

注意：

- `Handler` 必须定义在插件类中，前两个参数必须为 `self` 和 `event`
- 插件类所在文件必须命名为 `main.py`
- 所有处理函数都要写在插件类中

---

## 3. 处理消息事件

来源：https://docs.astrbot.app/dev/star/guides/listen-message-event.html

事件监听器用于接收平台下发的消息，实现指令、指令组、事件监听等功能。

使用前需导入：

```python
from astrbot.api.event import filter, AstrMessageEvent
```

注意：这里的 `filter` 是 AstrBot 的注册器，必须显式导入，否则会和 Python 内置的高阶函数 `filter` 混淆。

### 3.1 消息与事件

AstrBot 接收平台消息后，会封装为 `AstrMessageEvent` 对象再传给插件。

#### `AstrBotMessage`

```python
class AstrBotMessage:
    type: MessageType
    self_id: str
    session_id: str
    message_id: str
    group_id: str = ""
    sender: MessageMember
    message: List[BaseMessageComponent]
    message_str: str
    raw_message: object
    timestamp: int
```

其中：

- `raw_message` 为平台适配器的原始消息对象
- `message` 为消息链，如 `[Plain("Hello"), At(qq=123456)]`
- `message_str` 为纯文本拼接结果

#### 消息链

消息链是一个有序列表，每个元素称为消息段。常见类型：

- `Plain`
- `At`
- `Image`
- `Record`
- `Video`
- `File`

OneBot v11 还常见：

- `Face`
- `Node`
- `Nodes`
- `Poke`

### 3.2 基础指令

```python
@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    user_name = event.get_sender_name()
    message_str = event.message_str
    yield event.plain_result(f"Hello, {user_name}!")
```

注意：指令名不能带空格，否则会被解析到第二个参数。

### 3.3 带参指令

```python
@filter.command("add")
def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"Wow! The anwser is {a + b}!")
```

### 3.4 指令组

```python
@filter.command_group("math")
def math(self):
    pass


@math.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"结果是: {a + b}")


@math.command("sub")
async def sub(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"结果是: {a - b}")
```

嵌套示例：

```python
@filter.command_group("math")
def math():
    pass


@math.group("calc")
def calc():
    pass


@calc.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"结果是: {a + b}")


@calc.command("sub")
async def sub(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"结果是: {a - b}")


@calc.command("help")
def calc_help(self, event: AstrMessageEvent):
    yield event.plain_result("这是一个计算器插件，拥有 add, sub 指令。")
```

### 3.5 指令别名

```python
@filter.command("help", alias={"帮助", "helpme"})
def help(self, event: AstrMessageEvent):
    yield event.plain_result("这是一个计算器插件，拥有 add, sub 指令。")
```

### 3.6 事件过滤

接收所有消息：

```python
@filter.event_message_type(filter.EventMessageType.ALL)
async def on_all_message(self, event: AstrMessageEvent):
    yield event.plain_result("收到了一条消息。")
```

只接收私聊：

```python
@filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
async def on_private_message(self, event: AstrMessageEvent):
    yield event.plain_result("收到了一条私聊消息。")
```

当前 `EventMessageType` 包含：

- `PRIVATE_MESSAGE`
- `GROUP_MESSAGE`

指定平台：

```python
@filter.platform_adapter_type(
    filter.PlatformAdapterType.AIOCQHTTP | filter.PlatformAdapterType.QQOFFICIAL
)
async def on_aiocqhttp(self, event: AstrMessageEvent):
    yield event.plain_result("收到了一条信息")
```

当前 `PlatformAdapterType` 包含：

- `AIOCQHTTP`
- `QQOFFICIAL`
- `GEWECHAT`
- `ALL`

管理员权限：

```python
@filter.permission_type(filter.PermissionType.ADMIN)
@filter.command("test")
async def test(self, event: AstrMessageEvent):
    pass
```

### 3.7 多过滤器组合

过滤器之间是 `AND` 逻辑：

```python
@filter.command("helloworld")
@filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
async def helloworld(self, event: AstrMessageEvent):
    yield event.plain_result("你好！")
```

### 3.8 事件钩子

事件钩子不能和以下装饰器混用：

- `@filter.command`
- `@filter.command_group`
- `@filter.event_message_type`
- `@filter.platform_adapter_type`
- `@filter.permission_type`

Bot 初始化完成：

```python
@filter.on_astrbot_loaded()
async def on_astrbot_loaded(self):
    print("AstrBot 初始化完成")
```

等待 LLM 请求时：

```python
@filter.on_waiting_llm_request()
async def on_waiting_llm(self, event: AstrMessageEvent):
    await event.send(" 正在等待请求...")
```

LLM 请求时：

```python
from astrbot.api.provider import ProviderRequest


@filter.on_llm_request()
async def my_custom_hook_1(self, event: AstrMessageEvent, req: ProviderRequest):
    req.system_prompt += "自定义 system_prompt"
```

LLM 响应完成时：

```python
from astrbot.api.provider import LLMResponse


@filter.on_llm_response()
async def on_llm_resp(self, event: AstrMessageEvent, resp: LLMResponse):
    print(resp)
```

发送消息前：

```python
@filter.on_decorating_result()
async def on_decorating_result(self, event: AstrMessageEvent):
    result = event.get_result()
    chain = result.chain
    chain.append(Plain("!"))
```

发送消息后：

```python
@filter.after_message_sent()
async def after_message_sent(self, event: AstrMessageEvent):
    pass
```

### 3.9 优先级

```python
@filter.command("helloworld", priority=1)
async def helloworld(self, event: AstrMessageEvent):
    yield event.plain_result("Hello!")
```

默认优先级为 `0`。

### 3.10 控制事件传播

```python
@filter.command("check_ok")
async def check_ok(self, event: AstrMessageEvent):
    ok = self.check()
    if not ok:
        yield event.plain_result("检查失败")
        event.stop_event()
```

调用 `event.stop_event()` 后，后续插件处理和 LLM 请求都不会继续。

---

## 4. 消息的发送

来源：https://docs.astrbot.app/dev/star/guides/send-message.html

### 4.1 被动消息

```python
@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    yield event.plain_result("Hello!")
    yield event.plain_result("你好！")
    yield event.image_result("path/to/image.jpg")
    yield event.image_result("https://example.com/image.jpg")
```

### 4.2 主动消息

某些平台支持机器人主动推送消息。可以把 `event.unified_msg_origin` 保存下来，后续再发送：

```python
from astrbot.api.event import MessageChain


@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    umo = event.unified_msg_origin
    message_chain = MessageChain().message("Hello!").file_image("path/to/image.jpg")
    await self.context.send_message(event.unified_msg_origin, message_chain)
```

### 4.3 富媒体消息

```python
import astrbot.api.message_components as Comp


@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    chain = [
        Comp.At(qq=event.get_sender_id()),
        Comp.Plain("来看这个图："),
        Comp.Image.fromURL("https://example.com/image.jpg"),
        Comp.Image.fromFileSystem("path/to/image.jpg"),
        Comp.Plain("这是一个图片。"),
    ]
    yield event.chain_result(chain)
```

提示：

- 在 `aiocqhttp` 适配器中，`plain` 消息会在发送时被 `strip()`
- 需要保留前后空格或换行时，可在前后添加零宽空格 `\u200b`

其他富媒体组件：

```python
Comp.File(file="path/to/file.txt", name="file.txt")

path = "path/to/record.wav"
Comp.Record(file=path, url=path)

path = "path/to/video.mp4"
Comp.Video.fromFileSystem(path=path)
Comp.Video.fromURL(url="https://example.com/video.mp4")
```

### 4.4 发送视频消息

```python
from astrbot.api.message_components import Video

music = Video.fromFileSystem(path="test.mp4")
music = Video.fromURL(url="https://example.com/video.mp4")
yield event.chain_result([music])
```

### 4.5 发送群合并转发消息

目前文档标注主要适用于 `OneBot v11`：

```python
from astrbot.api.message_components import Node, Plain, Image

node = Node(
    uin=905617992,
    name="Soulter",
    content=[
        Plain("hi"),
        Image.fromFileSystem("test.jpg"),
    ],
)
yield event.chain_result([node])

---

## 5. 插件配置

来源：https://docs.astrbot.app/dev/star/guides/plugin-config.html

AstrBot 支持通过 `_conf_schema.json` 定义插件配置，并自动在管理面板中可视化编辑。

### 5.1 Schema 定义

```json
{
  "token": {
    "description": "Bot Token",
    "type": "string"
  },
  "sub_config": {
    "description": "测试嵌套配置",
    "type": "object",
    "hint": "xxxx",
    "items": {
      "name": {
        "description": "testsub",
        "type": "string",
        "hint": "xxxx"
      },
      "id": {
        "description": "testsub",
        "type": "int",
        "hint": "xxxx"
      },
      "time": {
        "description": "testsub",
        "type": "int",
        "hint": "xxxx",
        "default": 123
      }
    }
  }
}
```

字段说明：

- `type`：必填。支持 `string`、`text`、`int`、`float`、`bool`、`object`、`list`、`dict`、`template_list`
- `description`：可选。配置描述
- `hint`：可选。提示信息
- `obvious_hint`：可选。是否醒目显示 hint
- `default`：可选。默认值
- `items`：可选。`object` 类型的子 Schema
- `invisible`：可选。是否隐藏
- `options`：可选。下拉选项列表
- `editor_mode`：可选。启用代码编辑器模式，需要 AstrBot `>= v3.5.10`
- `editor_language`：可选。编辑器语言，默认 `json`
- `editor_theme`：可选。可用 `vs-light`、`vs-dark`
- `_special`：可选。调用 AstrBot 内置可视化选择器

`_special` 可选值：

- `select_provider`
- `select_provider_tts`
- `select_provider_stt`
- `select_persona`

### 5.2 `file` 类型

```json
{
  "demo_files": {
    "type": "file",
    "description": "Uploaded files for demo",
    "default": [],
    "file_types": ["pdf", "docx"]
  }
}
```

### 5.3 `dict` 类型

```python
"custom_extra_body": {
  "description": "自定义请求体参数",
  "type": "dict",
  "items": {},
  "hint": "用于在请求时添加额外的参数，如 temperature、top_p、max_tokens 等。",
  "template_schema": {
      "temperature": {
          "name": "Temperature",
          "description": "温度参数",
          "hint": "控制输出的随机性，范围通常为 0-2。值越高越随机。",
          "type": "float",
          "default": 0.6,
          "slider": {"min": 0, "max": 2, "step": 0.1}
      },
      "top_p": {
          "name": "Top-p",
          "description": "Top-p 采样",
          "hint": "核采样参数，范围通常为 0-1。控制模型考虑的概率质量。",
          "type": "float",
          "default": 1.0,
          "slider": {"min": 0, "max": 1, "step": 0.01}
      },
      "max_tokens": {
          "name": "Max Tokens",
          "description": "最大令牌数",
          "hint": "生成的最大令牌数。",
          "type": "int",
          "default": 8192
      }
  }
}
```

### 5.4 `template_list` 类型

```json
"field_id": {
  "type": "template_list",
  "description": "Template List Field",
  "templates": {
    "template_1": {
      "name": "Template One",
      "hint": "hint",
      "items": {
        "attr_a": {
          "description": "Attribute A",
          "type": "int",
          "default": 10
        },
        "attr_b": {
          "description": "Attribute B",
          "hint": "This is a boolean attribute",
          "type": "bool",
          "default": true
        }
      }
    },
    "template_2": {
      "name": "Template Two",
      "hint": "hint",
      "items": {
        "attr_c": {
          "description": "Attribute A",
          "type": "int",
          "default": 10
        },
        "attr_d": {
          "description": "Attribute B",
          "hint": "This is a boolean attribute",
          "type": "bool",
          "default": true
        }
      }
    }
  }
}
```

保存后的配置示例：

```json
"field_id": [
  {
    "__template_key": "template_1",
    "attr_a": 10,
    "attr_b": true
  },
  {
    "__template_key": "template_2",
    "attr_c": 10,
    "attr_d": true
  }
]
```

### 5.5 在插件中使用配置

AstrBot 会自动检测 `_conf_schema.json`，解析后把配置实体保存到：

`data/config/<plugin_name>_config.json`

```python
from astrbot.api import AstrBotConfig


class ConfigPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        print(self.config)
```

`AstrBotConfig` 继承自 `Dict`，支持字典的所有方法。

### 5.6 配置更新

当 Schema 发生变化时，AstrBot 会递归检查配置：

- 自动补齐缺失字段的默认值
- 自动移除已不存在的字段

---

## 6. AI

来源：https://docs.astrbot.app/dev/star/guides/ai.html

AstrBot 内置多种 LLM 提供商支持，并提供统一接口。文档注明：`v4.5.7` 之后推荐使用新的 LLM / Agent 调用方式。

### 6.1 获取当前会话使用的聊天模型 ID

```python
umo = event.unified_msg_origin
provider_id = await self.context.get_current_chat_provider_id(umo=umo)
```

### 6.2 直接调用大模型

```python
llm_resp = await self.context.llm_generate(
    chat_provider_id=provider_id,
    prompt="Hello, world!",
)
```

返回结果中可读取 `llm_resp.completion_text`。

### 6.3 定义 Tool

```python
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class BilibiliTool(FunctionTool[AstrAgentContext]):
    name: str = "bilibili_videos"
    description: str = "A tool to fetch Bilibili videos."
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Keywords to search for Bilibili videos.",
                }
            },
            "required": ["keywords"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        return "1. 视频标题：如何使用AstrBot\n 视频链接：xxxxxx"
```

### 6.4 注册 Tool 到 AstrBot

```python
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(BilibiliTool(), SecondTool(), ...)

        # 旧写法（< v4.5.1）
        tool_mgr = self.context.provider_manager.llm_tools
        tool_mgr.func_list.append(BilibiliTool())
```

### 6.5 用装饰器定义 Tool

```python
@filter.llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, location: str) -> MessageEventResult:
    """获取天气信息。

    Args:
        location(string): 地点
    """
    resp = self.get_weather_from_api(location)
    yield event.plain_result("天气信息: " + resp)
```

支持的参数类型：

- `string`
- `number`
- `object`
- `boolean`
- `array`

### 6.6 调用 Agent

```python
llm_resp = await self.context.tool_loop_agent(
    event=event,
    chat_provider_id=prov_id,
    prompt="搜索一下 bilibili 上关于 AstrBot 的相关视频。",
    tools=ToolSet([BilibiliTool()]),
    max_steps=30,
    tool_call_timeout=60,
)
```

`tool_loop_agent()` 会自动处理工具调用和模型请求的循环，直到模型不再调用工具，或者达到最大步骤数。

### 6.7 Multi-Agent

文档示例使用 `agent-as-tool` 模式，将主 Agent 与多个子 Agent 组合。

#### 分配工具示例

```python
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class AssignAgentTool(FunctionTool[AstrAgentContext]):
    name: str = "assign_agent"
    description: str = "Assign an agent to a task based on the given query"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to call the sub-agent with.",
                }
            },
            "required": ["query"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        return "Based on the query, you should assign agent 1."
```

#### 子 Agent 示例

```python
@dataclass
class SubAgent1(FunctionTool[AstrAgentContext]):
    name: str = "subagent1_name"
    description: str = "subagent1_description"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to call the sub-agent with.",
                }
            },
            "required": ["query"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        ctx = context.context.context
        event = context.context.event
        llm_resp = await ctx.tool_loop_agent(
            event=event,
            chat_provider_id=await ctx.get_current_chat_provider_id(
                event.unified_msg_origin
            ),
            prompt=kwargs["query"],
            tools=ToolSet([WeatherTool()]),
            max_steps=30,
        )
        return llm_resp.completion_text
```

主 Agent 调用：

```python
@filter.command("test")
async def test(self, event: AstrMessageEvent):
    umo = event.unified_msg_origin
    prov_id = await self.context.get_current_chat_provider_id(umo)
    llm_resp = await self.context.tool_loop_agent(
        event=event,
        chat_provider_id=prov_id,
        prompt="Test calling sub-agent for Beijing's weather information.",
        system_prompt=(
            "You are the main agent. Your task is to delegate tasks to sub-agents based on user queries."
            "Before delegating, use the 'assign_agent' tool to determine which sub-agent is best suited for the task."
        ),
        tools=ToolSet([SubAgent1(), SubAgent2(), AssignAgentTool()]),
        max_steps=30,
    )
    yield event.plain_result(llm_resp.completion_text)
```

### 6.8 对话管理器

获取当前对话：

```python
from astrbot.core.conversation_mgr import Conversation

uid = event.unified_msg_origin
conv_mgr = self.context.conversation_manager
curr_cid = await conv_mgr.get_curr_conversation_id(uid)
conversation = await conv_mgr.get_conversation(uid, curr_cid)
```

`Conversation` 结构：

```python
@dataclass
class Conversation:
    platform_id: str
    user_id: str
    cid: str
    history: str = ""
    title: str | None = ""
    persona_id: str | None = ""
    created_at: int = 0
    updated_at: int = 0
```

写入一组对话记录：

```python
from astrbot.core.agent.message import (
    AssistantMessageSegment,
    UserMessageSegment,
    TextPart,
)

curr_cid = await conv_mgr.get_curr_conversation_id(event.unified_msg_origin)
user_msg = UserMessageSegment(content=[TextPart(text="hi")])
llm_resp = await self.context.llm_generate(
    chat_provider_id=provider_id,
    contexts=[user_msg],
)
await conv_mgr.add_message_pair(
    cid=curr_cid,
    user_message=user_msg,
    assistant_message=AssistantMessageSegment(
        content=[TextPart(text=llm_resp.completion_text)]
    ),
)
```

主要方法：

- `new_conversation(unified_msg_origin, platform_id=None, content=None, title=None, persona_id=None) -> str`
- `switch_conversation(unified_msg_origin, conversation_id) -> None`
- `delete_conversation(unified_msg_origin, conversation_id=None) -> None`
- `get_curr_conversation_id(unified_msg_origin) -> str | None`
- `get_conversation(unified_msg_origin, conversation_id, create_if_not_exists=False) -> Conversation | None`
- `get_conversations(unified_msg_origin=None, platform_id=None) -> list[Conversation]`
- `update_conversation(unified_msg_origin, conversation_id=None, history=None, title=None, persona_id=None) -> None`

### 6.9 PersonaManager

```python
persona_mgr = self.context.persona_manager
```

主要方法：

- `get_persona(persona_id)`
- `get_all_personas()`
- `create_persona(persona_id, system_prompt, begin_dialogs=None, tools=None)`
- `update_persona(persona_id, system_prompt=None, begin_dialogs=None, tools=None)`
- `delete_persona(persona_id)`
- `get_default_persona_v3(umo=None)`

类型定义摘要：

```python
class Persona(SQLModel, table=True):
    id: int
    persona_id: str
    system_prompt: str
    begin_dialogs: Optional[list]
    tools: Optional[list]
    created_at: datetime
    updated_at: datetime


class Personality(TypedDict):
    prompt: str
    name: str
    begin_dialogs: list[str]
    mood_imitation_dialogs: list[str]
    tools: list[str] | None
```

说明：

- `Persona` 是 `v4.0.0` 之后推荐使用的格式
- `Personality` 为旧版兼容格式
- `mood_imitation_dialogs` 在 `v4.0.0` 之后已废弃

---

## 7. 插件存储

来源：https://docs.astrbot.app/dev/star/guides/storage.html

### 7.1 简单 KV 存储

需要 AstrBot `>= 4.9.2`。

```python
class Main(star.Star):
    @filter.command("hello")
    async def hello(self, event: AstrMessageEvent):
        await self.put_kv_data("greeted", True)
        greeted = await self.get_kv_data("greeted", False)
        await self.delete_kv_data("greeted")
```

该 KV 存储按插件维度隔离，不同插件之间互不干扰。

### 7.2 大文件存储规范

大文件建议存放到：

`data/plugin_data/{plugin_name}/`

```python
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

plugin_data_path = get_astrbot_data_path() / "plugin_data" / self.name
```

---

## 8. 文转图

来源：https://docs.astrbot.app/dev/star/guides/html-to-pic.html

在线模板调试工具：

- https://t2i-playground.astrbot.app

### 8.1 基本用法

```python
@filter.command("image")
async def on_aiocqhttp(self, event: AstrMessageEvent, text: str):
    url = await self.text_to_image(text)
    yield event.image_result(url)
```

### 8.2 自定义 HTML 模板

```python
TMPL = """
<div style="font-size: 32px;">
<h1 style="color: black">Todo List</h1>

<ul>
{% for item in items %}
    <li>{{ item }}</li>
{% endfor %}
</div>
"""


@filter.command("todo")
async def custom_t2i_tmpl(self, event: AstrMessageEvent):
    options = {}
    url = await self.html_render(
        TMPL,
        {"items": ["吃饭", "睡觉", "玩原神"]},
        options=options,
    )
    yield event.image_result(url)
```

### 8.3 截图选项

支持的常用 `options`：

- `timeout`
- `type`
- `quality`
- `omit_background`
- `full_page`
- `clip`
- `animations`
- `caret`
- `scale`

---

## 9. 会话控制

来源：https://docs.astrbot.app/dev/star/guides/session-control.html

适用版本：`>= v3.4.36`

```python
import astrbot.api.message_components as Comp
from astrbot.core.utils.session_waiter import (
    session_waiter,
    SessionController,
)
```

基本示例：

```python
@filter.command("成语接龙")
async def handle_empty_mention(self, event: AstrMessageEvent):
    yield event.plain_result("请发送一个成语~")

    @session_waiter(timeout=60, record_history_chains=False)
    async def empty_mention_waiter(controller: SessionController, event: AstrMessageEvent):
        idiom = event.message_str
        if idiom == "退出":
            await event.send(event.plain_result("已退出成语接龙~"))
            controller.stop()
            return

        if len(idiom) != 4:
            await event.send(event.plain_result("成语必须是四个字的呢~"))
            return

        message_result = event.make_result()
        message_result.chain = [Comp.Plain("先见之明")]
        await event.send(message_result)
        controller.keep(timeout=60, reset_timeout=True)

    await empty_mention_waiter(event)
```

要点：

- 激活控制器后，发送人的后续消息会优先进入当前 waiter
- 在 waiter 内发送消息不能使用 `yield`
- 超时会抛出 `TimeoutError`

`SessionController` 主要方法：

- `keep(timeout, reset_timeout=True)`
- `stop()`
- `get_history_chains()`

自定义会话 ID 示例：

```python
from astrbot.core.utils.session_waiter import SessionFilter


class CustomFilter(SessionFilter):
    def filter(self, event: AstrMessageEvent) -> str:
        return event.get_group_id() if event.get_group_id() else event.unified_msg_origin
```

---

## 10. 杂项

来源：https://docs.astrbot.app/dev/star/guides/other.html

### 10.1 获取消息平台实例

```python
platform = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
```

### 10.2 调用 QQ 协议端 API

```python
if event.get_platform_name() == "aiocqhttp":
    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
        AiocqhttpMessageEvent,
    )

    assert isinstance(event, AiocqhttpMessageEvent)
    client = event.bot
    payloads = {"message_id": event.message_obj.message_id}
    ret = await client.api.call_action("delete_msg", **payloads)
```

协议端 API 参考：

- Napcat: https://napcat.apifox.cn/
- Lagrange: https://lagrange-onebot.apifox.cn/

### 10.3 获取载入的所有插件

```python
plugins = self.context.get_all_stars()
```

### 10.4 获取加载的所有平台

```python
platforms = self.context.platform_manager.get_insts()
```

---

## 11. 发布插件到插件市场

来源：https://docs.astrbot.app/dev/star/plugin-publish.html

发布流程：

1. 把插件代码推送到 GitHub 仓库
2. 打开插件市场：`https://plugins.astrbot.app`
3. 点击右下角 `+`
4. 填写插件、作者、仓库等信息
5. 点击 `提交到 GTIHUB`
6. 页面会跳转到 AstrBot 仓库的 Issue 提交页
7. 确认无误后点击 `Create`

---

## 附注

- 本文为官方插件开发文档的单文件整理版。
- 若需要最新修订，建议仍以官方站点原页面为准。
- 官方页面中若包含配图说明，本文件仅保留文字和代码，不再重复截图资源。
```
