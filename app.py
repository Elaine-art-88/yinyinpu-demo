# -*- coding: utf-8 -*-
"""
忆音谱 · 家族数字生命记忆系统（演示版）

核心功能：
1. 记忆采集 —— 通过对话记录大家长一生的经历，这些记忆用于塑造数字人的人格与回答。
2. 数字人对话 —— 接入豆包 character 模型自由对话，问起某个年龄段自动切换形象与音色；
   预设音频仅作为「各年龄阶段音色样例」参考（真实语音合成 TTS 为正式版功能）。
3. 家族树 —— 可编辑，家族成员可增删改；成员之间可生成相互对话。

密钥来源优先级：Streamlit Secrets -> 侧边栏手动输入 -> 演示模式（兜底回复）。
"""

import json

import streamlit as st

__version__ = "1.2.0"  # 接入豆包语音合成 2.0（TTS 语音播报）

from ark_client import (
    chat,
    tts,
    asr,
    wav_to_pcm16k,
    detect_stage,
    STAGES,
    build_system_prompt,
    FALLBACK_REPLIES,
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
    TTS_VOICES,
    DEFAULT_SPEAKER,
)

# ---------------------------------------------------------------------------
# 常量与 session 初始化
# ---------------------------------------------------------------------------
STAGE_LABELS = {"childhood": "童年", "youth": "青年", "middle": "中年", "elderly": "老年"}
STAGE_TO_KEY = {v: k for k, v in STAGE_LABELS.items()}
STAGE_ORDER = ("childhood", "youth", "middle", "elderly")

st.set_page_config(page_title="忆音谱 · 跨年龄数字人", page_icon="👴", layout="wide")


def init_state():
    defaults = {
        # 家族成员：第一项固定为大家长（数字人主体）
        "members": [
            {
                "id": 0, "name": "张秀兰", "nickname": "张奶奶",
                "relationship": "大家长/母亲", "age": "80",
                "photo": None, "memory": "", "is_elder": True,
            }
        ],
        "next_member_id": 1,
        "memories": [],               # 记忆银行：{"stage","content"}
        "chat_histories": {},          # {target_id: [{"role","content","stage"}]}
        "last_warning": "",
        "last_question": "",           # 记忆采集里 AI 出的题
        "last_question_audio": None,   # 问题对应的 TTS 音频
        "mem_answer": "",              # 记忆采集里的回答文本
        "temperature": 0.7,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


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


def get_tts_key() -> str:
    try:
        return st.secrets.get("TTS_API_KEY", "")
    except Exception:
        return ""


def get_asr_key() -> str:
    try:
        return st.secrets.get("ASR_API_KEY", "") or st.secrets.get("TTS_API_KEY", "")
    except Exception:
        return ""


def get_tts_speaker() -> str:
    try:
        return st.secrets.get("TTS_SPEAKER", DEFAULT_SPEAKER)
    except Exception:
        return DEFAULT_SPEAKER


def member_by_id(tid: int):
    for m in st.session_state.members:
        if m["id"] == tid:
            return m
    return st.session_state.members[0]


def member_by_nickname(nick: str):
    for m in st.session_state.members:
        if m["nickname"] == nick:
            return m
    return None


def get_history(tid: int):
    return st.session_state.chat_histories.setdefault(tid, [])


def member_persona(m) -> dict:
    return {
        "nickname": m["nickname"],
        "name": m["name"],
        "age": m.get("age", ""),
        "relationship": m["relationship"],
        "story": m.get("memory", ""),
    }


def build_member_prompt(m, user_identity=None) -> str:
    persona = member_persona(m)
    memories = st.session_state.memories if m.get("is_elder") else None
    family = [x for x in st.session_state.members if x["id"] != m["id"]]
    return build_system_prompt(persona, memories=memories, family=family, user_identity=user_identity)


# ---------------------------------------------------------------------------
# 侧边栏
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🧭 忆音谱")
    st.caption("家族数字生命记忆系统 · 演示版")

    secret_key = get_api_key()
    secret_tts_key = get_tts_key()
    model = get_model()
    base_url = get_base_url()

    if secret_key:
        st.success("✅ 已接入豆包 character 模型")
    if secret_tts_key:
        st.success("✅ 已接入语音合成 2.0")
    if not secret_key and not secret_tts_key:
        st.warning("⚠️ 未配置密钥，可点下方「密钥设置」填写，或直接体验演示模式")

    api_key = secret_key
    tts_key = secret_tts_key

    # 隐藏式密钥设置（默认折叠，密钥不会直接显示）
    if not (secret_key and secret_tts_key):
        with st.expander("🔑 密钥设置（隐藏）", expanded=False):
            if not secret_key:
                api_key = st.text_input("ARK API Key", type="password", key="manual_key")
                st.caption("豆包 character 模型（对话）")
            if not secret_tts_key:
                tts_key = st.text_input("TTS API Key（可选）", type="password", key="manual_tts_key")
                st.caption("豆包语音合成 2.0（让数字人开口说话）")

    if api_key:
        st.caption(f"模型：{model}")
        st.session_state.temperature = st.slider("回复温度", 0.0, 1.2, st.session_state.temperature)

    # ---- 语音合成（TTS）设置 ----
    if tts_key:
        st.divider()
        st.subheader("🔊 语音合成")
        tts_enabled = st.toggle("开启语音播报", value=True, key="tts_enabled")
        default_speaker = get_tts_speaker()
        default_idx = list(TTS_VOICES.values()).index(default_speaker) if default_speaker in TTS_VOICES.values() else 0
        speaker_label = st.selectbox("音色", list(TTS_VOICES.keys()), index=default_idx, key="tts_speaker")
        speaker = TTS_VOICES[speaker_label]
    else:
        tts_enabled = False
        speaker = DEFAULT_SPEAKER

    st.divider()
    st.markdown("**📌 使用流程**")
    st.caption("1️⃣ 先到「记忆采集」记录大家长的经历\n2️⃣ 再到「家族树」添加家人\n3️⃣ 最后到「数字人对话」和家人聊天")
    st.divider()
    st.caption("🏆 第十四届全国大学生数字媒体科技作品竞赛")


# ---------------------------------------------------------------------------
# 主区域
# ---------------------------------------------------------------------------
tab_mem, tab_chat, tab_tree, tab_meet = st.tabs(
    ["📝 记忆采集", "💬 数字人对话", "🌳 家族树", "🗣️ 成员互聊"]
)

elder = member_by_id(0)

# ============================== 记忆采集 ====================================
with tab_mem:
    st.markdown("#### 记录大家长的一生经历")
    st.caption("通过对话记录老人的经历，这些记忆会「拷贝」给数字人，塑造 TA 的人格与回答。")

    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("**① AI 语音提问**")
        stage_sel = st.selectbox("选择要记录的人生阶段", list(STAGE_LABELS.values()), key="mem_stage")
        if st.button("🎤 让 AI 语音提问", type="primary", width="stretch"):
            with st.spinner("构思问题中…"):
                q_prompt = [
                    {"role": "system", "content": "你是一位耐心的口述史采访者，正在采访一位老人。你要提出具体、有画面感、能勾起回忆的问题。"},
                    {"role": "user", "content": f"请针对老人的【{stage_sel}】阶段，提 1 个能勾起回忆的具体问题（如上学、工作、家庭、生活细节）。只输出问题本身，不要任何解释。"},
                ]
                try:
                    q = chat(q_prompt, api_key, model=model, base_url=base_url, max_tokens=100)
                except Exception:
                    q = f"（演示模式）请讲讲您{stage_sel}时候印象最深的一件事吧。"
                st.session_state.last_question = q
                st.session_state.last_question_audio = None
                if tts_key:
                    with st.spinner("合成问题语音…"):
                        try:
                            st.session_state.last_question_audio = tts(q, tts_key, speaker=speaker)
                        except Exception:
                            st.session_state.last_question_audio = None
                st.session_state.mem_answer = ""
                st.rerun()

        if st.session_state.last_question:
            st.info(st.session_state.last_question)
            if st.session_state.last_question_audio:
                st.audio(st.session_state.last_question_audio, format="audio/mp3", autoplay=True)
                st.caption("🔊 上面是 AI 用语音提出的问题")

        st.markdown("**② 老人语音回答**")
        st.caption("老人点下方 🎤 录音说话，录音会自动转成文字（豆包语音识别 2.0）。")
        audio_file = st.audio_input("🎤 点击录音（老人直接说话）")
        if audio_file is not None:
            audio_bytes = audio_file.getvalue()
            st.audio(audio_bytes, format="audio/wav")
            asr_key = get_asr_key() or tts_key
            sig = len(audio_bytes)
            if asr_key and st.session_state.get("_audio_sig") != sig:
                st.session_state._audio_sig = sig
                with st.spinner("正在识别语音…"):
                    try:
                        pcm = wav_to_pcm16k(audio_bytes)
                        transcript = asr(pcm, asr_key)
                        st.session_state.mem_answer = transcript.strip()
                        st.session_state._asr_msg = ("ok", transcript.strip()) if transcript.strip() else ("empty", "")
                    except Exception as e:
                        st.session_state._asr_msg = ("err", str(e))
            msg = st.session_state.get("_asr_msg")
            if msg:
                if msg[0] == "ok":
                    st.success(f"✅ 识别结果：{msg[1]}")
                elif msg[0] == "empty":
                    st.warning("未识别到内容，请重试或手动输入")
                else:
                    st.warning(f"语音识别失败：{msg[1]}")
            elif not asr_key:
                st.info("未配置语音识别 Key，可手动录入文字")

        answer = st.text_area("回答内容（语音自动填入，可手动修改）", key="mem_answer", height=140)

        if st.button("💾 保存这段记忆", type="primary", width="stretch"):
            if answer.strip():
                st.session_state.memories.append(
                    {"stage": STAGE_TO_KEY[stage_sel], "content": answer.strip()}
                )
                st.session_state.mem_answer = ""
                st.rerun()
            else:
                st.warning("请先输入或说出内容")

    with c2:
        st.markdown("**已采集的记忆**")
        if not st.session_state.memories:
            st.info("还没有记录任何记忆。先从左侧开始采访吧。")
        for idx, it in enumerate(st.session_state.memories):
            ctxt, cbtn = st.columns([9, 1])
            with ctxt:
                st.markdown(f"**[{STAGE_LABELS[it['stage']]}]** {it['content']}")
            with cbtn:
                if st.button("🗑", key=f"delmem_{idx}", help="删除这条记忆"):
                    del st.session_state.memories[idx]
                    st.rerun()

    st.divider()
    col_export, col_import, col_clear = st.columns(3)
    with col_export:
        data = {
            "memories": st.session_state.memories,
            "members": [
                {k: v for k, v in m.items() if k != "photo"}
                for m in st.session_state.members
            ],
        }
        st.download_button(
            "⬇️ 导出数据（记忆+家族树）",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name="yinyinpu_data.json",
            mime="application/json",
            width="stretch",
        )
    with col_import:
        up = st.file_uploader("导入 JSON", type=["json"], key="import_json", label_visibility="collapsed")
        if up is not None:
            try:
                d = json.loads(up.read())
                st.session_state.memories = d.get("memories", [])
                st.session_state.members = d.get("members", st.session_state.members)
                ids = [m.get("id", 0) for m in st.session_state.members]
                st.session_state.next_member_id = (max(ids) + 1) if ids else 1
                st.rerun()
            except Exception as e:
                st.error(f"导入失败：{e}")
    with col_clear:
        if st.button("🗑 清空全部记忆", width="stretch"):
            st.session_state.memories = []
            st.rerun()


# ============================== 数字人对话 ==================================
with tab_chat:
    st.markdown("#### 与数字人对话")
    st.caption("问起某个年龄段的事，数字人会【自动切换】到对应的形象与音色；预设音频仅为「音色样例」。")

    if st.session_state.last_warning:
        st.warning(st.session_state.last_warning)

    # 顶部选择：对话对象 / 我是谁
    top1, top2 = st.columns(2)
    with top1:
        nicknames = [m["nickname"] for m in st.session_state.members]
        target_nick = st.selectbox("🎯 对话对象", nicknames, key="chat_target")
        target = member_by_nickname(target_nick) or elder
    with top2:
        me_opts = ["家属（不指定）"] + [m["nickname"] for m in st.session_state.members if m["id"] != target["id"]]
        me_sel = st.selectbox("🙋 我是谁", me_opts, key="my_identity")
        user_identity = None if me_sel == "家属（不指定）" else me_sel

    col_img, col_chat = st.columns([2, 3])

    with col_img:
        stage_choice = st.selectbox("人生阶段", ["自动检测", "童年", "青年", "中年", "老年"], index=0, key="stage_choice")

        history = get_history(target["id"])
        if stage_choice == "自动检测":
            cur = history[-1].get("stage", "elderly") if history else "elderly"
        else:
            cur = STAGE_TO_KEY[stage_choice]

        # 展示形象
        if target.get("is_elder"):
            cfg = STAGES[cur]
            if cur == "elderly" and target.get("photo"):
                st.image(target["photo"], caption="老年阶段 · 数字人形象（上传的照片）", width="stretch")
            else:
                st.image(cfg["portrait"], caption=cfg["desc"], width="stretch")
            st.markdown(f"### 🎭 当前：{cfg['label']}阶段")
            st.caption(f"🔊 音色样例（{cfg['label']}阶段的声音感觉）")
            try:
                st.audio(cfg["voice"])
            except Exception:
                st.caption("（音色文件缺失）")
        else:
            # 非大家长成员：展示其照片，不做阶段切换
            if target.get("photo"):
                st.image(target["photo"], caption=f"{target['nickname']} · 数字人形象", width="stretch")
            else:
                st.info(f"👤 {target['nickname']}（尚未上传照片）")
            st.markdown(f"### 🎭 {target['nickname']}")
            st.caption(f"关系：{target['relationship']}")

    with col_chat:
        # 历史消息
        for m in history:
            with st.chat_message(m["role"]):
                st.write(m["content"])
                if m.get("audio"):
                    st.audio(m["audio"], format="audio/mp3")
                if m.get("stage") and target.get("is_elder"):
                    st.caption(f"🎭 {STAGE_LABELS.get(m['stage'], '')}阶段")

        prompt = st.chat_input(f"和 {target['nickname']} 聊聊吧…")

        if prompt:
            stage = detect_stage(prompt) if target.get("is_elder") else "elderly"
            history.append({"role": "user", "content": prompt, "stage": stage})

            msgs = [{"role": "system", "content": build_member_prompt(target, user_identity)}]
            for m in history:
                msgs.append({"role": m["role"], "content": m["content"]})

            audio = None
            with st.chat_message("assistant"):
                with st.spinner("正在回忆…"):
                    try:
                        reply = chat(msgs, api_key, model=model, base_url=base_url, temperature=st.session_state.temperature)
                        st.session_state.last_warning = ""
                    except Exception as e:
                        reply = FALLBACK_REPLIES.get(stage, FALLBACK_REPLIES["elderly"])
                        st.session_state.last_warning = f"⚠️ 演示模式（未成功连接模型）：{e}"
                if tts_enabled and tts_key and reply:
                    with st.spinner("正在合成语音…"):
                        try:
                            audio = tts(reply, tts_key, speaker=speaker)
                        except Exception as e:
                            st.session_state.last_warning = f"{st.session_state.last_warning}\n⚠️ 语音合成失败：{e}"
            history.append({"role": "assistant", "content": reply, "stage": stage, "audio": audio})
            st.rerun()


# ============================== 家族树 ======================================
with tab_tree:
    st.markdown("#### 家族数字记忆族谱（可编辑）")
    st.caption("把家族成员都加进来；每位成员都能拥有自己的照片与人格，可被对话、可相互对话。")

    # 添加成员表单
    with st.expander("➕ 添加一位家族成员", expanded=False):
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            new_nick = st.text_input("称呼（如：建国）", key="new_nick")
        with f2:
            new_name = st.text_input("本名（如：王建国）", key="new_name")
        with f3:
            new_rel = st.text_input("与大家长的关系（如：大儿子）", key="new_rel")
        with f4:
            new_age = st.text_input("年龄", key="new_age")
        new_memory = st.text_area("TA 的简要人生/性格（用于塑造 TA 自己的数字人，可留空）", key="new_memory", height=80)
        new_photo = st.file_uploader("TA 的照片（可选）", type=["jpg", "jpeg", "png"], key="new_photo")
        if st.button("✅ 添加成员", type="primary"):
            if not new_nick.strip():
                st.warning("请至少填写「称呼」")
            elif member_by_nickname(new_nick.strip()):
                st.warning("这个称呼已存在，请换一个")
            else:
                st.session_state.members.append({
                    "id": st.session_state.next_member_id,
                    "name": new_name.strip() or new_nick.strip(),
                    "nickname": new_nick.strip(),
                    "relationship": new_rel.strip() or "家属",
                    "age": new_age.strip() or "",
                    "photo": new_photo.getvalue() if new_photo else None,
                    "memory": new_memory.strip(),
                    "is_elder": False,
                })
                st.session_state.next_member_id += 1
                st.rerun()

    # 成员列表
    for m in st.session_state.members:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                if m.get("photo"):
                    st.image(m["photo"], width=120)
                else:
                    st.markdown(f"<div style='font-size:64px;line-height:1'>👤</div>", unsafe_allow_html=True)
            with c2:
                tag = "👴 大家长" if m.get("is_elder") else "👥 成员"
                st.markdown(f"**{m['nickname']}** · {tag}")
                st.caption(f"本名 {m['name']} ｜ 关系：{m['relationship']}" + (f" ｜ 年龄：{m['age']}" if m.get('age') else ""))
                if m.get("memory"):
                    st.caption(f"人格/记忆：{m['memory'][:80]}{'…' if len(m['memory']) > 80 else ''}")
            with c3:
                if not m.get("is_elder"):
                    if st.button("🗑 删除", key=f"delmember_{m['id']}"):
                        st.session_state.members = [x for x in st.session_state.members if x["id"] != m["id"]]
                        st.rerun()

    st.divider()
    st.caption("💡 大家长（张奶奶）的身份与照片可在下方编辑；其他成员按需增删。")


# ============================== 成员互聊 ====================================
with tab_meet:
    st.markdown("#### 家族成员相互对话")
    st.caption("选择两位成员，生成一段他们之间的对话（各按各自身份与记忆说话）。")

    if len(st.session_state.members) < 2:
        st.info("请先到「家族树」添加至少一名家族成员，才能进行成员互聊。")
    else:
        nicks = [m["nickname"] for m in st.session_state.members]
        m1, m2 = st.columns(2)
        with m1:
            a_nick = st.selectbox("成员 A", nicks, key="meet_a")
        with m2:
            b_opts = [n for n in nicks if n != a_nick]
            b_nick = st.selectbox("成员 B", b_opts, key="meet_b")
        topic = st.text_input("聊什么（可留空，AI 自定家常话题）", placeholder="例如：聊一聊小时候 / 聊聊孩子")

        if st.button("🎬 生成对话", type="primary"):
            a = member_by_nickname(a_nick)
            b = member_by_nickname(b_nick)
            topic_txt = f"，围绕话题「{topic}」" if topic.strip() else "，聊家常、聊往事"
            meet_prompt = [
                {"role": "system", "content": "你会扮演两位家庭成员，生成一段自然、有温度的对话。"},
                {"role": "user", "content": (
                    f"请生成 {a['nickname']} 与 {b['nickname']} 之间的对话{topic_txt}。\n"
                    f"{a['nickname']}：{a['relationship']}，{a.get('memory') or '性格随和'}\n"
                    f"{b['nickname']}：{b['relationship']}，{b.get('memory') or '性格随和'}\n"
                    f"要求：各说 4~6 轮，语气贴合各自身份，口语化、有生活气息。"
                    f"输出格式：每行以「称呼：内容」开头。"
                )},
            ]
            with st.spinner("生成对话中…"):
                try:
                    dialog = chat(meet_prompt, api_key, model=model, base_url=base_url, max_tokens=1200, temperature=0.8)
                except Exception as e:
                    dialog = f"{a['nickname']}：{FALLBACK_REPLIES['elderly']}\n{b['nickname']}：是啊，一家人都平平安安就好。"
                    st.warning(f"演示模式：{e}")
            st.success(f"🎭 {a['nickname']} × {b['nickname']}")
            st.markdown(dialog)
            st.download_button(
                "⬇️ 下载对话文本",
                data=dialog.encode("utf-8"),
                file_name=f"对话_{a['nickname']}_{b['nickname']}.txt",
                mime="text/plain",
            )
