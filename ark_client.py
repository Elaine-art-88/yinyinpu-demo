# -*- coding: utf-8 -*-
"""
忆音谱 · 跨年龄数字人 —— 豆包 character 模型接入与人生阶段识别。

包含：
1. 豆包(火山方舟) OpenAI 兼容接口的对话调用
2. 人生四阶段(童年/青年/中年/老年)的关键词识别
3. 默认人格设定与系统提示词构造
4. 演示模式下的兜底回复
"""

import base64
import json
import re
import time
import uuid

import requests

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DEFAULT_MODEL = "doubao-seed-character-260628"

# 豆包语音合成模型 2.0（seed-tts-2.0）
TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
TTS_RESOURCE_ID = "seed-tts-2.0"
TTS_VOICES = {
    "女声·Vivi": "zh_female_vv_uranus_bigtts",
    "男声·刘飞": "zh_male_liufei_uranus_bigtts",
    "男声·云舟": "zh_male_m191_uranus_bigtts",
}
DEFAULT_SPEAKER = "zh_female_vv_uranus_bigtts"

# ---------------------------------------------------------------------------
# 人生四阶段配置：label 用于展示，portrait/voice 对应 assets 里的素材文件
# ---------------------------------------------------------------------------
STAGES = {
    "childhood": {
        "label": "童年",
        "portrait": "assets/child.jpg",
        "voice": "assets/voice_child.mp3",
        "desc": "童年阶段 · 数字人形象",
        "keywords": [
            "小时候", "童年", "小学", "上学", "读书", "上学时", "幼儿园", "孩提",
            "儿时", "少年", "孩子时", "老师", "同桌", "放牛", "挑水", "捡柴",
            "过家家", "玩具", "糖果", "过年", "逃学", "捉迷藏", "山", "河里",
            "田里", "背着书包", "启蒙",
        ],
    },
    "youth": {
        "label": "青年",
        "portrait": "assets/young.jpg",
        "voice": "assets/voice_young.mp3",
        "desc": "青年阶段 · 数字人形象",
        "keywords": [
            "年轻", "青年", "工作", "上班", "进厂", "当兵", "参军", "结婚",
            "恋爱", "对象", "二十", "三十", "学徒", "师傅", "打工", "下海",
            "车间", "工厂", "初恋", "嫁", "娶", "成家", "毕业", "招工", "挣工分",
        ],
    },
    "middle": {
        "label": "中年",
        "portrait": "assets/middle.jpg",
        "voice": "assets/voice_middle.mp3",
        "desc": "中年阶段 · 数字人形象",
        "keywords": [
            "中年", "四十", "五十", "创业", "买房", "养家", "下岗", "单位",
            "事业", "带孩子", "供读书", "供孩子", "拉扯", "孩子还小",
            "上有老下有小", "分房", "改革开放", "下海经商",
        ],
    },
    "elderly": {
        "label": "老年",
        "portrait": "assets/old.jpg",
        "voice": "assets/voice_old.mp3",
        "desc": "老年阶段 · 数字人形象",
        "keywords": [
            "现在", "晚年", "退休", "养老", "孙子", "孙女", "外孙", "曾孙",
            "重孙", "孙辈", "寄语", "希望", "愿望", "身体", "健康", "平安",
            "老了", "年纪大", "以后", "如今", "现在呀", "这辈子", "长大了",
            "牵挂", "放心不下",
        ],
    },
}


def detect_stage(text: str) -> str:
    """根据用户的问题判断它问的是哪个年龄段，返回 STAGES 的键。

    先做关键词匹配（阶段越靠前越优先），再用数字年龄粗判，最后默认回到老年阶段。
    """
    text = text or ""
    for key in ("childhood", "youth", "middle", "elderly"):
        cfg = STAGES[key]
        for kw in cfg["keywords"]:
            if kw in text:
                return key

    # 数字年龄粗判：如「你 25 岁的时候」「60 岁那年」
    for m in re.finditer(r"(\d{1,3})\s*岁", text):
        age = int(m.group(1))
        if age < 12:
            return "childhood"
        if age < 30:
            return "youth"
        if age < 50:
            return "middle"
        return "elderly"

    return "elderly"


# ---------------------------------------------------------------------------
# 默认人格与系统提示词
# ---------------------------------------------------------------------------
DEFAULT_STORY = (
    "- 童年（贵州山村）：家里穷，上过几年小学，每天走五里山路去学校，放学还要放牛、挑水、捡柴火。"
    "最开心的是过年能吃到一块肉。\n"
    "- 青年（1950—60 年代）：二十岁进了县里纺织厂当学徒工，跟王师傅学技术，认识了后来的老伴，结婚生子，日子紧但有奔头。\n"
    "- 中年（70—90 年代）：拉扯三个孩子长大，供他们读书，白天上班晚上做针线活，省吃俭用熬过了最难的岁月。\n"
    "- 老年（现在）：退休在家，身体还算硬朗，喜欢和孙辈视频通话，最牵挂的就是一家人平安团圆。"
)


def format_memories(memories) -> str:
    """把记忆列表按人生阶段分组，格式化成可塞进提示词的文本。

    memories: [{"stage": "childhood", "content": "..."}, ...]
    """
    if not memories:
        return ""
    order = ("childhood", "youth", "middle", "elderly")
    grouped = {}
    for m in memories:
        grouped.setdefault(m.get("stage", "elderly"), []).append(m.get("content", ""))
    parts = []
    for s in order:
        if s in grouped:
            label = STAGES[s]["label"]
            parts.append(f"【{label}】" + "；".join(x for x in grouped[s] if x))
    return "\n".join(parts)


def build_system_prompt(persona: dict, memories=None, family=None, user_identity=None) -> str:
    """根据人格设定构造系统提示词，让模型始终以该人物身份、口吻说话。

    persona:        {"nickname", "name", "age", "relationship", "story"}
    memories:       记忆银行里的经历列表（塑造数字人的人格与记忆）
    family:         其他家庭成员列表（让数字人认识自己的家人）
    user_identity:  正在和数字人说话的人是谁（如「你的孙女小芳」）
    """
    nick = persona.get("nickname") or persona.get("name") or "张奶奶"
    name = persona.get("name") or nick
    age = persona.get("age") or "80"
    rel = persona.get("relationship") or "家属"
    story = persona.get("story") or ""

    mem_text = format_memories(memories or [])
    if not mem_text and story:
        mem_text = story
    if not mem_text:
        mem_text = DEFAULT_STORY

    blocks = [
        f"你是{nick}（本名{name}），今年{age}岁，是一位和蔼健谈、记性很好的老人。",
        f"你的人生经历（这些是家人记录下来的你的真实记忆，请自然地在对话中引用这些细节）：\n{mem_text}",
    ]
    if family:
        fam = "、".join((m.get("nickname") or m.get("name")) for m in family)
        blocks.append(f"你的家人：{fam}。你可以自然地提到他们。")
    if user_identity:
        blocks.append(f"现在正在和你说话的人是：{user_identity}。请用合适的称呼、以家人的口吻与 TA 聊天。")
    blocks.append(
        "说话要求：\n"
        "- 第一人称、口语化、亲切自然，像真人聊天，不像念稿。\n"
        "- 可以带一点点质朴的方言味，但不难懂，爱用「那时候」「咱」「乖孙」这类词。\n"
        "- 每次回答 100～250 字左右，简短有温度。\n"
        "- 聊到某个年龄段的事，就自然地讲那个年代的细节、场景和感受。\n"
        f"- 始终以「{nick}」的身份说话，不要跳出角色，不要说「我是 AI」。"
    )
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# 兜底回复（无 Key 或调用失败时的演示模式）
# ---------------------------------------------------------------------------
FALLBACK_REPLIES = {
    "childhood": "我小时候上学要走五里山路，天不亮就出发，书包是你太奶奶用碎布缝的……那时候虽然苦，但每天都特别开心。",
    "youth": "我二十岁进了县里的纺织厂，当学徒工，跟着王师傅学技术。那时候干劲足，天天泡在车间里，也不觉得累。",
    "middle": "中年那会儿最难的，就是拉扯几个孩子，白天上班晚上做针线活，就盼着孩子能把书读出来，别像我一样吃没文化的亏。",
    "elderly": "现在啊，就希望家里人都平平安安，好好过日子，互相照应，把咱们家的本分一代代传下去……",
}


def chat(messages, api_key, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL,
         temperature=0.7, max_tokens=800, timeout=60, max_retries=3):
    """调用豆包(火山方舟) OpenAI 兼容的 chat/completions 接口。

    messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
    返回模型生成的文本；出错时抛出 RuntimeError。
    对网络抖动（SSL 断连/连接重置）自动重试，提升演示稳定性。
    """
    if not api_key:
        raise RuntimeError("未配置 ARK_API_KEY")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(base_url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as e:
                    raise RuntimeError(f"API 返回结构异常: {e}")
            last_err = RuntimeError(f"API 返回 {resp.status_code}: {resp.text[:300]}")
        except requests.exceptions.RequestException as e:
            last_err = e
        if attempt < max_retries - 1:
            time.sleep(1.0 * (attempt + 1))

    if isinstance(last_err, RuntimeError):
        raise last_err
    raise RuntimeError(f"网络异常（已重试 {max_retries} 次）: {last_err}")


def tts(text, api_key, speaker=DEFAULT_SPEAKER, timeout=60, max_retries=3):
    """调用豆包语音合成模型 2.0，把文字合成 MP3，返回音频字节。

    走 V3 单向流式接口：响应为 NDJSON，逐行 code==0 的 data 为 base64 音频块，
    code==20000000 为收尾标记。出错抛出 RuntimeError。
    """
    if not api_key:
        raise RuntimeError("未配置 TTS_API_KEY")
    headers = {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": TTS_RESOURCE_ID,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    body = {
        "user": {"uid": "yinyinpu_demo"},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": {"format": "mp3", "sample_rate": 24000},
        },
    }

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(TTS_URL, headers=headers, data=json.dumps(body), timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"TTS HTTP {resp.status_code}: {resp.text[:200]}")
            chunks = []
            for line in resp.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                code = obj.get("code")
                if code == 0:
                    d = obj.get("data")
                    if isinstance(d, str):
                        chunks.append(d)
                    elif isinstance(d, list):
                        chunks.extend(d)
            if not chunks:
                raise RuntimeError(f"TTS 无音频返回: {resp.text[:200]}")
            return base64.b64decode("".join(chunks))
        except (requests.exceptions.RequestException, RuntimeError) as e:
            last_err = e
        if attempt < max_retries - 1:
            time.sleep(1.0 * (attempt + 1))
    if isinstance(last_err, RuntimeError):
        raise last_err
    raise RuntimeError(f"TTS 网络异常（已重试 {max_retries} 次）: {last_err}")
