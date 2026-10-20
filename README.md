# 忆音谱 · 家族数字生命记忆系统（演示版）

> 用「跨年龄数字人」记录一个人一生的故事，让家属随时能和 TA 对话。
> 本项目为 **第十四届全国大学生数字媒体科技作品及创意竞赛** 参赛作品演示版。

## ✨ 功能

1. **记忆采集**：通过「问老人的经历」的方式，把老人一生的故事记录成结构化记忆（童年 / 青年 / 中年 / 老年），这些记忆会「拷贝」给数字人，塑造 TA 的人格与回答。支持导出 / 导入 JSON。
2. **数字人对话**：接入豆包 `doubao-seed-character-260628` 角色模型，**自由对话**（不是播放预设音频）。问起某个年龄段的事，自动切换到对应的**形象**与**音色**；可指定「我是谁」，让数字人用正确称呼与你聊天。
3. **可编辑家族树**：家族成员可增删改，每位成员可上传照片、填写自己的性格 / 记忆，成为可对话的数字人。
4. **成员互聊**：选择两位家庭成员，生成一段他们之间的对话（各按各自身份与记忆说话）。

> **关于语音**：已接入**豆包语音合成模型 2.0**（`seed-tts-2.0`），数字人会用所选音色**朗读回复**（侧边栏可切换女声/男声、开关播报）。
> 4 段预设音频仍作为「各年龄阶段的**音色样例**」参考；真实音色随年龄变化（voice aging）、音色克隆、年龄画像生成、视频生成（数字人口型驱动）为正式版功能。

## 🚀 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置密钥：复制示例文件并填入你的 Key
cp secrets.example.toml .streamlit/secrets.toml
# 编辑 .streamlit/secrets.toml，填入真实的 ARK_API_KEY

# 3. 启动
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。

> 也可不配置 Key，直接在左侧边栏手动粘贴 ARK API Key；
> 不配置 Key 时进入「演示模式」，用内置话术兜底，界面不会报错。

## 🌐 部署成「任何人都能打开」的公网链接（Streamlit Community Cloud）

1. 把本目录上传到 GitHub 仓库（**注意**：`.streamlit/secrets.toml` 已被 `.gitignore` 忽略，不会被上传，请勿把 Key 写进代码）。
2. 打开 [share.streamlit.io](https://share.streamlit.io) → 「New app」→ 选择你的仓库与 `app.py`。
3. 在 App 的 **Settings → Secrets** 中填入：

```toml
ARK_API_KEY = "ark-你的-key"
ARK_MODEL = "doubao-seed-character-260628"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
TTS_API_KEY = "你的TTS-key"
TTS_SPEAKER = "zh_female_vv_uranus_bigtts"
```

4. Deploy 完成后即可获得公开 URL，任何人打开都能直接对话。

## 🔑 密钥与安全

- 密钥通过 **Streamlit Secrets** 注入，不在代码中硬编码，也不会提交到 Git。
- 豆包（火山方舟）接口：`https://ark.cn-beijing.volces.com/api/v3/chat/completions`（OpenAI 兼容）。
- 公开部署后，任何人调用都会消耗你的 API 额度，请务必在[火山方舟控制台](https://console.volcengine.com/ark)设置**额度上限与告警**。

## 📁 目录结构

```
yinyinpu_demo/
├── app.py                 # 主应用（记忆采集 / 对话 / 家族树 / 成员互聊）
├── ark_client.py          # 豆包模型接入 + 人生阶段识别 + 记忆格式化 + 人格提示词
├── assets/                # 四阶段形象图 + 四阶段音色样例 + 族谱示意图
├── requirements.txt
├── secrets.example.toml   # 密钥示例（复制为 .streamlit/secrets.toml）
├── .streamlit/config.toml # 主题
└── .gitignore
```
