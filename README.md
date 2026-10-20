# 忆音谱 · 家族数字生命记忆系统（演示版）

> 用「跨年龄数字人」记录一个人一生的故事，让家属随时能和 TA 对话。
> 本项目为 **第十四届全国大学生数字媒体科技作品及创意竞赛** 参赛作品演示版。

## ✨ 功能

- **跨年龄数字人对话**：接入豆包 `doubao-seed-character-260628` 角色模型，自由对话。
- **年龄阶段自动切换**：问起「小时候 / 年轻时 / 中年 / 现在」的事，自动切换到对应的**形象**与**音色**（童年 / 青年 / 中年 / 老年）。
- **人格可自定义**：可修改称呼、本名、年龄、关系、人生故事；可上传老人近照。
- **生成寄语**：让数字人以某个年龄阶段的口吻给家人说一段话，支持下载文本。
- **数字族谱**：家族记忆结构示意。

> 说明：演示版使用**预设音色**与**预设年龄形象**示意「音色 / 画像随年龄切换」；
> 真实音色克隆、年龄画像生成、视频生成（数字人口型驱动）为正式版功能。

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

浏览器会自动打开 `http://localhost:8501`。

> 也可以不配置 Key，直接在左侧边栏手动粘贴 ARK API Key；
> 不配置 Key 时应用会进入「演示模式」，用内置话术兜底，界面不会报错。

## 🌐 部署成「任何人都能打开」的公网链接（Streamlit Community Cloud）

1. 把本目录上传到 GitHub 仓库（**注意**：`.streamlit/secrets.toml` 已被 `.gitignore` 忽略，不会被上传，请勿把 Key 写进代码）。
2. 打开 [share.streamlit.io](https://share.streamlit.io) → 「New app」→ 选择你的仓库与 `app.py`。
3. 在 App 的 **Settings → Secrets** 中填入：

```toml
ARK_API_KEY = "ark-你的-key"
ARK_MODEL = "doubao-seed-character-260628"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
```

4. Deploy 完成后，即可获得一个公开 URL，任何人打开都能直接对话。

## 🔑 密钥与安全

- 密钥通过 **Streamlit Secrets** 注入，不在代码中硬编码，也不会提交到 Git。
- 豆包（火山方舟）接口：`https://ark.cn-beijing.volces.com/api/v3/chat/completions`（OpenAI 兼容）。

## 📁 目录结构

```
yinyinpu_demo/
├── app.py                 # 主应用（Streamlit）
├── ark_client.py          # 豆包模型接入 + 人生阶段识别 + 人格提示词
├── assets/                # 四阶段形象图 + 四阶段音色 + 族谱示意图
├── requirements.txt
├── secrets.example.toml   # 密钥示例（复制为 .streamlit/secrets.toml）
├── .streamlit/config.toml # 主题
└── .gitignore
```
