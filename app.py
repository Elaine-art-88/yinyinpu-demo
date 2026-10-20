# -*- coding: utf-8 -*-
"""
忆音谱 · 家族数字生命记忆系统（演示版）

功能：
1. 跨年龄数字人对话 —— 接入豆包 character 模型，自由对话；
   问起某个年龄段的事，自动切换到对应的形象与音色（童年/青年/中年/老年）。
2. 生成寄语 —— 让数字人以某个年龄阶段的口吻给家人说一段话。
3. 数字族谱 —— 家族记忆结构示意。

密钥来源优先级：Streamlit Secrets -> 侧边栏手动输入 -> 演示模式（兜底回复）。
"""

import streamlit as st

from ark_client import (
    chat,
    detect_stage,
    STAGES,
    build_system_prompt,
    FALLBACK_REPLIES,
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
)

# ---------------------------------------------------------------------------
# 页面与 session 初始化
# ---------------------------------------------------------------------------
st.set_page_config(page_title="忆音谱 · 跨年龄数字人", page_icon="👴", layout="wide")

for key, default in {
    "p_nickname": "张奶奶",
    "p_name": "张秀兰",
    "p_age": "80",
    "p_relationship": "家属",
    "p_story": "",
    "messages": [],
    "photo": None,
    "last_warning": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def get_api_key() -> str:
    try:
        return st.secrets.get("ARK_API_KEY", "")
    except Exception:
        return ""


def get_model() -> str:
    try:
        return st.secrets.get("ARK_MODEL", DEFAULT_MODEL)
    except Exception:
        return DEFAULT_MODEL


def get_base_url() -> str:
    try:
        return st.secrets.get("ARK_BASE_URL", DEFAULT_BASE_URL)
    except Exception:
        return DEFAULT_BASE_URL


def get_persona() -> dict:
    return {
        "nickname": st.session_state.p_nickname,
        "name": st.session_state.p_name,
        "age": st.session_state.p_age,
        "relationship": st.session_state.p_relationship,
        "story": st.session_state.p_story,
    }


STAGE_TO_KEY = {"童年": "childhood", "青年": "youth", "中年": "middle", "老年": "elderly"}


# ---------------------------------------------------------------------------
# 侧边栏：密钥、人格设定、照片上传
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🧭 忆音谱")
    st.caption("家族数字生命记忆系统 · 演示版")

    secret_key = get_api_key()
    model = get_model()
    base_url = get_base_url()

    if secret_key:
        st.success("✅ 已接入豆包 character 模型")
        api_key = secret_key
    else:
        st.warning("⚠️ 未检测到 Key，可手动填入，或直接体验演示模式")
        api_key = st.text_input("ARK API Key", type="password", key="manual_key")

    if api_key:
        st.caption(f"模型：{model}")
        st.caption("温度：")
        temperature = st.slider("temperature", 0.0, 1.2, 0.7, key="temperature")
    else:
        temperature = 0.7

    st.divider()

    st.subheader("👤 数字人设定")
    st.text_input("称呼（如：张奶奶）", key="p_nickname")
    st.text_input("本名", key="p_name")
    st.text_input("年龄", key="p_age")
    st.text_input("与你的关系（如：我的奶奶）", key="p_relationship")
    st.text_area(
        "人生故事（可留空，使用默认人物故事）",
        key="p_story",
        height=120,
        placeholder="例如：\n- 童年……\n- 青年……\n- 中年……\n- 老年……",
    )

    st.subheader("📷 上传老人近照")
    uploaded = st.file_uploader(
        "上传一张照片（作为当前老年阶段形象，可选）",
        type=["jpg", "jpeg", "png"],
        key="photo_uploader",
    )
    if uploaded is not None:
        st.session_state.photo = uploaded.getvalue()
        st.image(st.session_state.photo, caption="已上传照片", width="stretch")

    st.divider()
    st.caption("🏆 第十四届全国大学生数字媒体科技作品竞赛")


# ---------------------------------------------------------------------------
# 主区域
# ---------------------------------------------------------------------------
tab_dialog, tab_message, tab_tree = st.tabs(
    ["✨ 跨年龄数字人对话", "💝 生成寄语", "🌳 数字族谱"]
)


def current_stage() -> str:
    """取最近一条用户消息对应的阶段，无历史则默认老年。"""
    if st.session_state.messages:
        return st.session_state.messages[-1].get("stage", "elderly")
    return "elderly"


def render_portrait(stage: str):
    cfg = STAGES[stage]
    if stage == "elderly" and st.session_state.photo is not None:
        st.image(
            st.session_state.photo,
            caption="老年阶段 · 数字人形象（你上传的照片）",
            width="stretch",
        )
    else:
        st.image(cfg["portrait"], caption=cfg["desc"], width="stretch")
    st.markdown(f"### 🎭 当前：{cfg['label']}阶段")
    st.caption("🔊 该阶段音色（演示版为预设音色，正式版支持音色克隆）")
    try:
        st.audio(cfg["voice"])
    except Exception:
        st.caption("（音色文件缺失）")


# ------------------------------- 对话 Tab ---------------------------------
with tab_dialog:
    st.markdown("#### 跨年龄数字人对话")
    st.caption("问起 TA 某个年龄段的事，数字人会【自动切换】到对应的形象与音色 👇")

    if st.session_state.last_warning:
        st.warning(st.session_state.last_warning)

    col_img, col_chat = st.columns([2, 3])

    with col_img:
        stage_choice = st.selectbox(
            "人生阶段", ["自动检测", "童年", "青年", "中年", "老年"], index=0
        )
        if stage_choice == "自动检测":
            render_portrait(current_stage())
        else:
            render_portrait(STAGE_TO_KEY[stage_choice])

    with col_chat:
        # 历史消息
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])
                st.caption(f"🎭 {STAGES[m.get('stage', 'elderly')]['label']}阶段")

        prompt = st.chat_input("和 TA 聊聊吧，比如：讲讲你小时候上学的故事…")

        if prompt:
            stage = detect_stage(prompt)
            st.session_state.messages.append(
                {"role": "user", "content": prompt, "stage": stage}
            )

            # 组装 messages（system + 完整历史）
            msgs = [{"role": "system", "content": build_system_prompt(get_persona())}]
            for m in st.session_state.messages:
                msgs.append({"role": m["role"], "content": m["content"]})

            with st.chat_message("assistant"):
                with st.spinner(f"已切换到【{STAGES[stage]['label']}】阶段，正在回忆…"):
                    try:
                        reply = chat(
                            msgs,
                            api_key,
                            model=model,
                            base_url=base_url,
                            temperature=temperature,
                        )
                        st.session_state.last_warning = ""
                    except Exception as e:
                        reply = FALLBACK_REPLIES.get(stage, FALLBACK_REPLIES["elderly"])
                        st.session_state.last_warning = (
                            f"⚠️ 当前为演示模式（未成功连接模型）：{e}"
                        )
            st.session_state.messages.append(
                {"role": "assistant", "content": reply, "stage": stage}
            )
            st.rerun()


# ----------------------------- 生成寄语 Tab -------------------------------
with tab_message:
    st.markdown("#### 生成一段寄语")
    st.caption("让数字人以某个年龄阶段的口吻，给家人说一段话")

    c1, c2 = st.columns([2, 1])
    with c1:
        topic = st.text_input(
            "寄语主题", placeholder="例如：给孙女的祝福 / 对全家人的叮嘱"
        )
        stage_sel = st.selectbox("选择阶段", ["老年", "中年", "青年", "童年"], index=0)
    with c2:
        st.caption("预览")
        cfg = STAGES[STAGE_TO_KEY[stage_sel]]
        if stage_sel == "老年" and st.session_state.photo is not None:
            st.image(st.session_state.photo, width=180)
        else:
            st.image(cfg["portrait"], width=180)

    if st.button("✨ 生成寄语", type="primary"):
        if not topic.strip():
            st.warning("请先填写寄语主题")
        else:
            stage_key = STAGE_TO_KEY[stage_sel]
            stage_label = STAGES[stage_key]["label"]
            msgs = [
                {"role": "system", "content": build_system_prompt(get_persona())},
                {
                    "role": "user",
                    "content": (
                        f"请你以【{stage_label}阶段】的口吻，围绕「{topic}」"
                        f"给家人说一段 150～250 字的寄语，语气真挚、温暖、口语化。"
                    ),
                },
            ]
            with st.spinner("生成中…"):
                try:
                    msg = chat(msgs, api_key, model=model, base_url=base_url)
                except Exception as e:
                    msg = FALLBACK_REPLIES.get(stage_key, FALLBACK_REPLIES["elderly"])
                    st.warning(f"演示模式（未成功连接模型）：{e}")

            st.success(f"🎭 {stage_label}阶段寄语")
            st.markdown(msg)
            try:
                st.audio(cfg["voice"])
            except Exception:
                pass
            st.download_button(
                "⬇️ 下载寄语文本",
                data=msg.encode("utf-8"),
                file_name=f"寄语_{stage_label}.txt",
                mime="text/plain",
            )
            st.caption("🎬 视频生成与音色克隆为正式版功能（需接入 TTS 与数字人口型驱动）")


# ----------------------------- 数字族谱 Tab -------------------------------
with tab_tree:
    st.markdown("#### 家族数字记忆族谱")
    st.caption("以亲属关系为脉络，每位长辈对应一个数字生命节点")
    try:
        st.image("assets/family_tree.jpg", caption="家族数字族谱示意图", width="stretch")
    except Exception:
        st.info("（族谱示意图缺失）")

    st.markdown("### 📌 功能说明")
    st.write("- 每位长辈对应一个数字生命节点，可查看人生故事、留存影像、与数字人对话")
    st.write("- 问起某个年龄段的事，自动切换到该阶段的形象与音色")
    st.write("- 家族成员可共同补充记忆，实现代际文化传承")
