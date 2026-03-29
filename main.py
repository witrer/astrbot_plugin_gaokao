import os
import json
import random
import re
import string
import html as html_mod
import time
import asyncio
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from astrbot.core.utils.session_waiter import session_waiter, SessionController

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 艾宾浩斯复习间隔 (立即, 12h, 1d, 2d, 4d, 7d, 15d)
EBBINGHAUS_INTERVALS = [0, 43200, 86400, 172800, 345600, 604800, 1296000]

# 意图识别：用户想继续刷题的关键词
CONTINUE_KEYWORDS = {"继续", "下一题", "再来一题", "继续刷", "next", "接着来", "再来", "来", "继续做题", "再做一题", "来一道"}

SUBJECT_FILE_MAP = {
    "数学": [
        "2010-2022_Math_I_MCQs.json", "2010-2022_Math_II_MCQs.json",
        "2010-2022_Math_I_Fill-in-the-Blank.json", "2010-2022_Math_I_Open-ended_Questions.json",
        "2010-2022_Math_II_Fill-in-the-Blank.json", "2010-2022_Math_II_Open-ended_Questions.json",
        "2023_Math_MCQs.json", "2024_Math_MCQs.json",
        "AGIEval_Math_MCQs.json", "AGIEval_Math_Fill-in-the-Blank.json"
    ],
    "语文": [
        "2010-2022_Chinese_Lang_and_Usage_MCQs.json", "2010-2022_Chinese_Modern_Lit.json",
        "2010-2022_Chinese_Language_Ancient_Poetry_Reading.json",
        "2010-2022_Chinese_Language_Classical_Chinese_Reading.json",
        "2010-2022_Chinese_Language_Famous_Passages_and_Sentences_Dictation.json",
        "2010-2022_Chinese_Language_Language_and_Writing_Skills_Open-ended_Questions.json",
        "2010-2022_Chinese_Language_Literary_Text_Reading.json",
        "2010-2022_Chinese_Language_Practical_Text_Reading.json",
        "2023_Chinese_Lang_and_Usage_MCQs.json", "2023_Chinese_Modern_Lit.json",
        "2024_Chinese_Lang_and_Usage_MCQs.json", "2024_Chinese_Modern_Lit.json",
        "AGIEval_Chinese_MCQs.json"
    ],
    "英语": [
        "2010-2013_English_MCQs.json", "2010-2022_English_Fill_in_Blanks.json",
        "2010-2022_English_Reading_Comp.json", "2012-2022_English_Cloze_Test.json",
        "2012-2022_English_Language_Error_Correction.json", "2014-2022_English_Language_Cloze_Passage.json",
        "2023_English_Cloze_Test.json", "2023_English_Fill_in_Blanks.json", "2023_English_Reading_Comp.json",
        "2024_English_Cloze_Test.json", "2024_English_Fill_in_Blanks.json", "2024_English_Reading_Comp.json",
        "AGIEval_English_MCQs.json"
    ],
    "物理": ["2010-2022_Physics_MCQs.json", "2010-2022_Physics_Open-ended_Questions.json", "2023_Physics_MCQs.json", "2024_Physics_MCQs.json", "AGIEval_Physics_MCQs.json"],
    "化学": ["2010-2022_Chemistry_MCQs.json", "2010-2022_Chemistry_Open-ended_Questions.json", "2023_Chemistry_MCQs.json", "2024_Chemistry_MCQs.json", "AGIEval_Chemistry_MCQs.json"],
    "生物": ["2010-2022_Biology_MCQs.json", "2010-2022_Biology_Open-ended_Questions.json", "2023_Biology_MCQs.json", "2024_Biology_MCQs.json", "AGIEval_Biology_MCQs.json"],
    "历史": ["2010-2022_History_MCQs.json", "2010-2022_History_Open-ended_Questions.json", "2023_History_MCQs.json", "2024_History_MCQs.json", "AGIEval_History_MCQs.json"],
    "地理": ["2010-2022_Geography_MCQs.json", "2010-2022_Geography_Open-ended_Questions.json", "2023_Geography_MCQs.json", "2024_Geography_MCQs.json", "AGIEval_Geography_MCQs.json"],
    "政治": ["2010-2022_Political_Science_MCQs.json", "2010-2022_Political_Science_Open-ended_Questions.json", "2023_Political_Science_MCQs.json", "2024_Political_Science_MCQs.json"]
}


@register("astrbot_plugin_gaokao", "202704948-design", "高考金牌私教", "2.0.0")
class GaokaoTutor(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.cfg_render = self.config.get("render_as_image", True)
        self.cfg_gaokao_date = self.config.get("gaokao_date", "2026-06-07")
        self.cfg_quiz_timeout = self.config.get("quiz_timeout", 300)
        self.cfg_rush_count = self.config.get("rush_mode_count", 20)
        self.cfg_page_size = self.config.get("wrong_book_page_size", 5)
        self.cfg_llm_provider = self.config.get("llm_provider", "")
        self.cfg_continuous_quiz = self.config.get("continuous_quiz_mode", True)
        self.cfg_leaderboard_size = self.config.get("leaderboard_page_size", 10)
        self.cfg_mix_challenge_count = self.config.get("mix_challenge_count", 20)

        self.cfg_daily_push_time = self.config.get("daily_push_time", "08:00")
        self.cfg_exam_select_count = self.config.get("exam_select_count", 5)
        self.cfg_exam_subject_count = self.config.get("exam_subjective_count", 1)

        self.question_banks = {}
        self._load_question_banks()
        self._push_task = asyncio.create_task(self._daily_push_loop())

    async def terminate(self):
        """插件卸载时清理"""
        if hasattr(self, '_push_task'):
            self._push_task.cancel()

    # ─── 数据层：KV 存储 ───────────────────────────────────────

    async def _get_user(self, uid, key, default=None):
        return await self.get_kv_data(f"{uid}:{key}", default)

    async def _set_user(self, uid, key, value):
        await self.put_kv_data(f"{uid}:{key}", value)

    async def _get_progress(self, uid):
        return await self._get_user(uid, "progress", {"done_ids": [], "wrong_book": {}, "last_question": None})

    async def _set_progress(self, uid, data):
        await self._set_user(uid, "progress", data)

    async def _get_scores(self, uid):
        return await self._get_user(uid, "scores", {"current_subject": "数学", "subjects": {}, "overall": {"total_done": 0, "total_correct": 0}})

    async def _set_scores(self, uid, data):
        await self._set_user(uid, "scores", data)

    # ─── User Key 系统 ─────────────────────────────────────────

    async def _get_or_create_key(self, uid, nickname=""):
        """获取或创建用户的唯一 Key"""
        uid_to_key = await self.get_kv_data("uid_to_key", {})
        if uid in uid_to_key:
            return uid_to_key[uid]
        # 生成 8 位唯一 key
        user_keys = await self.get_kv_data("user_keys", {})
        while True:
            key = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            if key not in user_keys:
                break
        user_keys[key] = {
            "platform_uid": uid,
            "nickname": nickname,
            "created_at": time.time(),
            "bind_platforms": [uid]
        }
        uid_to_key[uid] = key
        await self.put_kv_data("user_keys", user_keys)
        await self.put_kv_data("uid_to_key", uid_to_key)
        return key

    async def _get_key_for_uid(self, uid):
        """通过 platform uid 查找 user_key"""
        uid_to_key = await self.get_kv_data("uid_to_key", {})
        return uid_to_key.get(uid)

    # ─── 排行榜系统 ────────────────────────────────────────────

    async def _update_leaderboard(self, uid, nickname="", streak=None, mix_streak=None):
        """答题后更新排行榜数据"""
        lb = await self.get_kv_data("leaderboard", {})
        user_key = await self._get_or_create_key(uid, nickname)
        scores = await self._get_scores(uid)
        ov = scores.get("overall", {})
        today = datetime.now().strftime("%Y-%m-%d")

        entry = lb.get(user_key, {
            "nickname": nickname,
            "total_done": 0,
            "total_correct": 0,
            "best_streak": 0,
            "mix_best_streak": 0,
            "today_done": 0,
            "today_date": today,
            "last_active": time.time()
        })

        # 更新昵称
        if nickname:
            entry["nickname"] = nickname

        # 同步总做题数据
        entry["total_done"] = ov.get("total_done", 0)
        entry["total_correct"] = ov.get("total_correct", 0)
        entry["last_active"] = time.time()

        # 今日做题计数
        if entry.get("today_date") != today:
            entry["today_done"] = 0
            entry["today_date"] = today
        entry["today_done"] = entry.get("today_done", 0) + 1

        # 更新闯关最高连击
        if streak is not None and streak > entry.get("best_streak", 0):
            entry["best_streak"] = streak

        # 更新混合挑战最高连击
        if mix_streak is not None and mix_streak > entry.get("mix_best_streak", 0):
            entry["mix_best_streak"] = mix_streak

        lb[user_key] = entry
        await self.put_kv_data("leaderboard", lb)

    def _format_leaderboard(self, lb_data, sort_key, title, emoji, min_done=0):
        """格式化排行榜文本"""
        entries = []
        for key, data in lb_data.items():
            if sort_key == "accuracy":
                if data.get("total_done", 0) < max(min_done, 20):
                    continue
                val = data["total_correct"] / data["total_done"] * 100 if data["total_done"] > 0 else 0
                entries.append((key, data, val))
            else:
                val = data.get(sort_key, 0)
                entries.append((key, data, val))

        entries.sort(key=lambda x: x[2], reverse=True)
        entries = entries[:self.cfg_leaderboard_size]

        if not entries:
            return f"{emoji} {title}\n\n暂无数据，快来冲榜！"

        medals = ["🥇", "🥈", "🥉"]
        r = f"{emoji} 【{title}】\n" + "=" * 28 + "\n"
        for i, (key, data, val) in enumerate(entries):
            rank = medals[i] if i < 3 else f" {i+1}."
            name = data.get("nickname", key[:4] + "**")
            if sort_key == "accuracy":
                r += f"{rank} {name}  {val:.1f}% ({data['total_correct']}/{data['total_done']})\n"
            elif sort_key in ("best_streak", "mix_best_streak"):
                r += f"{rank} {name}  连击 ×{int(val)}\n"
            elif sort_key == "today_done":
                r += f"{rank} {name}  今日 {int(val)} 题\n"
            else:
                r += f"{rank} {name}  {int(val)} 题\n"
        r += "=" * 28
        return r

    # ─── LLM 调用 ─────────────────────────────────────────────

    async def _get_provider_id(self, event: AstrMessageEvent):
        """获取 LLM provider id：优先使用配置中选择的，否则用当前会话的"""
        if self.cfg_llm_provider:
            return self.cfg_llm_provider
        return await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)

    async def _llm_call(self, event, prompt):
        provider_id = await self._get_provider_id(event)
        resp = await self.context.llm_generate(chat_provider_id=provider_id, prompt=prompt)
        return resp.completion_text

    # ─── 数据加载 ──────────────────────────────────────────────

    def _load_question_banks(self):
        obj_dir = os.path.join(BASE_DIR, 'Data', 'Objective_Questions')
        sub_dir = os.path.join(BASE_DIR, 'Data', 'Subjective_Questions')
        for subject, files in SUBJECT_FILE_MAP.items():
            self.question_banks[subject] = []
            for fname in files:
                fpath = os.path.join(obj_dir, fname)
                if not os.path.exists(fpath):
                    fpath = os.path.join(sub_dir, fname)
                if not os.path.exists(fpath):
                    continue
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        questions = data.get("example", data.get("questions", []))
                    else:
                        questions = data
                    valid_qs = []
                    for q in questions:
                        if not isinstance(q, dict):
                            continue
                        q["_subject"] = subject
                        q["_file"] = fname
                        ans = q.get("answer", "")
                        is_obj = isinstance(ans, list) and len(ans) > 0 and len(str(ans[0])) <= 4
                        q["_is_subjective"] = not is_obj
                        valid_qs.append(q)
                    self.question_banks[subject].extend(valid_qs)
                except Exception as e:
                    logger.error(f"[GaokaoTutor] Error loading {fname}: {e}")

    # ─── HTML 渲染 ─────────────────────────────────────────────

    @staticmethod
    def _latex_to_html(text: str) -> str:
        """将 LaTeX 公式转换为 HTML 可读格式（Unicode + HTML 标签）"""

        def _convert_formula(m):
            f = m.group(1)
            # 希腊字母
            greek = {
                'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
                'epsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ',
                'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'pi': 'π',
                'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'phi': 'φ',
                'omega': 'ω', 'Alpha': 'Α', 'Beta': 'Β', 'Gamma': 'Γ',
                'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Pi': 'Π',
                'Sigma': 'Σ', 'Phi': 'Φ', 'Omega': 'Ω',
            }
            for k, v in greek.items():
                f = f.replace(f'\\{k}', v)
            # 数学符号
            replacements = {
                '\\triangle': '△', '\\angle': '∠', '\\perp': '⊥',
                '\\parallel': '∥', '\\infty': '∞', '\\partial': '∂',
                '\\nabla': '∇', '\\forall': '∀', '\\exists': '∃',
                '\\in': '∈', '\\notin': '∉', '\\subset': '⊂',
                '\\supset': '⊃', '\\cup': '∪', '\\cap': '∩',
                '\\emptyset': '∅', '\\times': '×', '\\cdot': '·',
                '\\div': '÷', '\\pm': '±', '\\mp': '∓',
                '\\leq': '≤', '\\geq': '≥', '\\neq': '≠',
                '\\approx': '≈', '\\equiv': '≡', '\\sim': '∼',
                '\\propto': '∝', '\\rightarrow': '→', '\\leftarrow': '←',
                '\\Rightarrow': '⇒', '\\Leftarrow': '⇐',
                '\\leftrightarrow': '↔', '\\Leftrightarrow': '⇔',
                '\\therefore': '∴', '\\because': '∵',
                '\\sqrt': '√', '\\sum': '∑', '\\prod': '∏',
                '\\int': '∫', '\\iint': '∬', '\\iiint': '∭',
                '\\overline': '', '\\underline': '', '\\hat': '',
                '\\vec': '', '\\bar': '', '\\tilde': '',
                '\\quad': '  ', '\\qquad': '    ', '\\,': ' ',
                '\\;': ' ', '\\!': '', '\\text': '', '\\mathrm': '',
                '\\mathbf': '', '\\mathit': '', '\\left': '',
                '\\right': '', '\\big': '', '\\Big': '',
                '\\bigg': '', '\\Bigg': '',
                '\\lfloor': '⌊', '\\rfloor': '⌋',
                '\\lceil': '⌈', '\\rceil': '⌉',
                '\\langle': '⟨', '\\rangle': '⟩',
                '\\circ': '°', '\\degree': '°',
            }
            for k, v in replacements.items():
                f = f.replace(k, v)
            # 三角函数等
            for fn in ['sin', 'cos', 'tan', 'cot', 'sec', 'csc',
                        'arcsin', 'arccos', 'arctan', 'ln', 'lg', 'log',
                        'lim', 'max', 'min', 'sup', 'inf', 'det']:
                f = f.replace(f'\\{fn}', fn)
            # \frac{a}{b} → a/b
            f = re.sub(r'\\frac\s*\{([^}]*)\}\s*\{([^}]*)\}', r'(\1)/(\2)', f)
            # \sqrt{x} → √(x)  and \sqrt[n]{x} → ⁿ√(x)
            f = re.sub(r'\\sqrt\[([^\]]*)\]\{([^}]*)\}', r'\1√(\2)', f)
            f = re.sub(r'\\sqrt\{([^}]*)\}', r'√(\1)', f)
            # 上标 ^{...} → <sup>...</sup>
            f = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', f)
            f = re.sub(r'\^(\w)', r'<sup>\1</sup>', f)
            # 下标 _{...} → <sub>...</sub>
            f = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', f)
            f = re.sub(r'_(\w)', r'<sub>\1</sub>', f)
            # 清理残余的 \xx 和多余的花括号
            f = re.sub(r'\\[a-zA-Z]+', '', f)
            f = f.replace('{', '').replace('}', '')
            return f'<span style="font-style:italic;font-family:serif;">{f}</span>'

        # 处理 $$...$$ (display math)
        text = re.sub(r'\$\$(.+?)\$\$', _convert_formula, text, flags=re.DOTALL)
        # 处理 $...$ (inline math)
        text = re.sub(r'\$(.+?)\$', _convert_formula, text, flags=re.DOTALL)
        # 处理未被 $ 包裹的常见 LaTeX 命令
        text = text.replace('\\triangle', '△').replace('\\angle', '∠')
        text = text.replace('\\perp', '⊥').replace('\\times', '×')
        text = text.replace('\\pm', '±').replace('\\leq', '≤').replace('\\geq', '≥')
        return text

    async def _render_html(self, item, include_answer=False, extra=""):
        q_text = self._latex_to_html(item.get("question", "")).replace('\n', '<br>')
        ans_raw = item.get("answer", "")
        ans_text = "".join(str(x) for x in ans_raw) if isinstance(ans_raw, list) else str(ans_raw)
        ans_text = self._latex_to_html(ans_text).replace('\n', '<br>')
        analysis = self._latex_to_html(item.get("analysis", "")).replace('\n', '<br>')

        body = f"<div style='font-size:18px;line-height:1.9;letter-spacing:0.3px;'>{q_text}</div>"
        if include_answer:
            body += f"<div style='margin-top:20px;padding:15px;background:#e8f4f8;border-radius:8px;'><b>正确答案：</b><br>{ans_text}</div>"
            if analysis:
                body += f"<div style='margin-top:15px;padding:15px;background:#f0fdf4;border-radius:8px;'><b>解析：</b><br>{analysis}</div>"
        if extra:
            body += f"<div style='margin-top:20px;padding:15px;background:#fff2f2;border-radius:8px;'>{extra.replace(chr(10), '<br>')}</div>"

        q_type = '主观题' if item.get('_is_subjective') else '客观题'
        year = item.get('year', '未知')
        cat = item.get('category', '')
        score = item.get('score', '?')

        tmpl = """
        <div style="font-family:'Microsoft YaHei','PingFang SC','Segoe UI',Tahoma,sans-serif;padding:20px;line-height:1.8;background:#f8f9fa;color:#333;width:100%;box-sizing:border-box;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;">
          <div style="background:#fff;padding:24px;border-radius:12px;box-shadow:0 8px 16px rgba(0,0,0,.05);">
            <div style="margin-bottom:16px;display:flex;flex-wrap:wrap;gap:6px;">
              <span style="padding:4px 10px;background:#e2e8f0;border-radius:6px;font-size:14px;color:#475569;font-weight:600;">{{ q_type }}</span>
              <span style="padding:4px 10px;background:#e2e8f0;border-radius:6px;font-size:14px;color:#475569;font-weight:600;">{{ year }}</span>
              <span style="padding:4px 10px;background:#e2e8f0;border-radius:6px;font-size:14px;color:#475569;font-weight:600;">{{ cat }}</span>
              <span style="padding:4px 10px;background:#e2e8f0;border-radius:6px;font-size:14px;color:#475569;font-weight:600;">{{ score }}分</span>
            </div>
            {{ body }}
          </div>
        </div>"""
        render_options = {"viewport": {"width": 480, "height": 800}}
        try:
            url = await self.html_render(tmpl, {"q_type": q_type, "year": year, "cat": cat, "score": score, "body": body}, options=render_options)
            return url
        except Exception as e:
            logger.error(f"[GaokaoTutor] Render Error: {e}")
            return None

    # ─── 成绩记录 ──────────────────────────────────────────────

    async def _record(self, uid, subject, is_correct, category, year):
        scores = await self._get_scores(uid)
        subs = scores.setdefault("subjects", {})
        sd = subs.setdefault(subject, {"total_done": 0, "total_correct": 0, "by_year": {}, "by_category": {}})
        sd["total_done"] += 1
        if is_correct:
            sd["total_correct"] += 1
        yr = sd["by_year"].setdefault(year, {"done": 0, "correct": 0})
        yr["done"] += 1
        if is_correct:
            yr["correct"] += 1
        ct = sd["by_category"].setdefault(category, {"done": 0, "correct": 0})
        ct["done"] += 1
        if is_correct:
            ct["correct"] += 1
        ov = scores.setdefault("overall", {"total_done": 0, "total_correct": 0})
        ov["total_done"] += 1
        if is_correct:
            ov["total_correct"] += 1
        await self._set_scores(uid, scores)

    async def _update_wrong_book(self, uid, item, is_correct):
        prog = await self._get_progress(uid)
        wb = prog.setdefault("wrong_book", {})
        qid = str(item.get("index", int(time.time())))
        if qid not in wb:
            if is_correct:
                # 新题答对，不需要加入错题本
                return
            wb[qid] = {"subject": item.get("_subject", ""), "question": item, "add_time": time.time(), "stage": 0, "next_review": time.time(), "wrong_count": 0}
        if not is_correct:
            wb[qid]["wrong_count"] += 1
            wb[qid]["stage"] = 0
            wb[qid]["next_review"] = time.time()
        else:
            stage = wb[qid]["stage"]
            if stage < len(EBBINGHAUS_INTERVALS) - 1:
                wb[qid]["stage"] += 1
                wb[qid]["next_review"] = time.time() + EBBINGHAUS_INTERVALS[wb[qid]["stage"]]
            else:
                del wb[qid]
        await self._set_progress(uid, prog)

    # ─── 批改逻辑 ──────────────────────────────────────────────

    def _grade_objective(self, item, user_ans):
        correct = item.get("answer", [])
        correct_str = "".join(str(x) for x in correct).strip().upper()
        # 提取用户答案中的字母，排序后比较（支持 "AB" "A,B" "A B" 等格式）
        ua_letters = sorted(re.findall(r'[A-Za-z]', user_ans.upper()))
        correct_letters = sorted(re.findall(r'[A-Za-z]', correct_str))
        if ua_letters and correct_letters and ua_letters == correct_letters:
            return True, correct_str
        # 对于非字母型答案（如数字填空），做 strip 后精确比较
        ua_clean = user_ans.strip()
        if ua_clean == correct_str:
            return True, correct_str
        return False, correct_str

    async def _grade_subjective(self, event, item, user_ans, subject):
        max_score = item.get('score', 10)
        try:
            max_score = float(max_score)
        except (ValueError, TypeError):
            max_score = 10.0
        prompt = f"""你是一名高中{subject}老师，正在批改高考{subject}试卷。请根据下面的【题目】、【分析过程】、【标准答案】、【分值】、【学生分析与答案】，对【学生分析与答案】进行判分并给出理由。输出格式为：【判分理由】...\\n【得分】...\\n【总分】...分
其中【总分】直接给出最终分数，不要超过【分值】。

【题目】{item.get('question')}
【分析过程】{item.get('analysis', '无')}
【标准答案】{item.get('answer')}
【分值】{max_score}
【学生分析与答案】{user_ans}"""
        llm_text = await self._llm_call(event, prompt)
        match = re.search(r"【总分】.*?(\d+(?:\.\d+)?)\s*分?", llm_text)
        earned = float(match.group(1)) if match else 0.0
        is_correct = earned >= (max_score * 0.6)
        return is_correct, llm_text

    # ─── 指令：帮助 ────────────────────────────────────────────

    @filter.command("高考帮助", alias={"帮助", "help", "gkhelp"})
    async def show_help(self, event: AstrMessageEvent):
        today = datetime.now()
        try:
            exam = datetime.strptime(self.cfg_gaokao_date, "%Y-%m-%d")
            days = max(0, (exam - today).days)
            ds = f"距 {exam.year} 高考还有 {days} 天！"
        except Exception:
            ds = "高考倒计时配置有误"

        r = f"🎓 【 高考金牌私教 v2.1 】 🎓\n🔥 {ds} 🔥\n"
        r += "=" * 28 + "\n"
        r += "📘 刷题模块\n"
        r += " /选科 [科目]    切换主刷科目\n"
        r += " /选科组合 [组合]设置混合挑战科\n"
        r += " /刷题           连续刷题(自动)\n"
        r += " /专项 [科目] [年份] 专项练习\n"
        r += " /模考 [科目]    全真模拟考试\n"
        r += " /闯关           单科闯关榜\n"
        r += " /混合挑战 [组合]跨科目混合闯关\n\n"
        r += "🏆 排行榜\n"
        r += " /排行榜       查看综合排行(总做题)\n"
        r += " /排行榜 正确率  按正确率排行\n"
        r += " /排行榜 连击   闯关最高连击榜\n"
        r += " /排行榜 混合   混合挑战连击榜\n"
        r += " /排行榜 今日   今日活跃榜\n\n"
        r += "🧠 AI 名师\n"
        r += " /解析   AI深度解析上一题\n"
        r += " /知识点 [内容]  AI梳理知识点\n"
        r += " /诊断   AI分析薄弱环节\n\n"
        r += "📒 统计与提醒\n"
        r += " /错题 [页码]   错题本(翻页)\n"
        r += " /错题 复习     重做错题\n"
        r += " /每日打卡      复习到期错题\n"
        r += " /订阅          每天定时推题倒计时\n"
        r += " /我的成绩      全科成绩单\n"
        r += " /报告          可视化学习报告\n\n"
        r += "🔑 身份系统\n"
        r += " /我的Key       查看个人标识码\n"
        r += " /绑定 [Key]    多平台绑定同一身份\n"
        yield event.plain_result(r)

    # ─── 指令：选科 ────────────────────────────────────────────

    @filter.command("选科", alias={"切换科目"})
    async def select_subject(self, event: AstrMessageEvent, subject: str = ""):
        uid = event.get_sender_id()
        if not subject or subject not in SUBJECT_FILE_MAP:
            yield event.plain_result(f"⚠️ 支持的科目：{', '.join(SUBJECT_FILE_MAP.keys())}\n用法：/选科 数学")
            return
        scores = await self._get_scores(uid)
        scores["current_subject"] = subject
        await self._set_scores(uid, scores)
        count = len(self.question_banks.get(subject, []))
        yield event.plain_result(f"✅ 已切换到【{subject}】(题库共 {count} 题)，发 /刷题 开始！")

    # ─── 指令：刷题（交互式 SessionWaiter）──────────────────────

    @filter.command("刷题", alias={"做题", "来一题", "抽题"})
    async def quiz(self, event: AstrMessageEvent, filter_arg: str = ""):
        uid = event.get_sender_id()
        scores = await self._get_scores(uid)
        subject = scores.get("current_subject", "数学")
        bank = self.question_banks.get(subject, [])

        prog = await self._get_progress(uid)
        done_ids = prog.get("done_ids", [])
        avail = [q for q in bank if q.get("index") not in done_ids]
        if filter_arg:
            avail = [q for q in avail if filter_arg in str(q.get("year", "")) or filter_arg in str(q.get("category", ""))]

        if not avail:
            yield event.plain_result(f"🎉 你已刷完 {subject} 的所有题！太强了！")
            return

        item = random.choice(avail)
        session_done = 0
        session_correct = 0

        # 发送题目
        if self.cfg_render:
            url = await self._render_html(item)
            if url:
                yield event.image_result(url)
            else:
                yield event.plain_result(self._format_question_text(item, subject))
        else:
            yield event.plain_result(self._format_question_text(item, subject))

        # 尝试发送 Telegram 按钮（客观题）
        tg_btn_sent = await self._try_send_tg_buttons(event, item)
        if not tg_btn_sent:
            if self.cfg_continuous_quiz:
                yield event.plain_result("✏️ 直接发送答案，发「退出」结束刷题")
            else:
                yield event.plain_result("✏️ 请直接发送答案（客观题发选项如 A，主观题发解答文字），发 '跳过' 可跳过")

        # 交互式等待答案
        @session_waiter(timeout=self.cfg_quiz_timeout, record_history_chains=False)
        async def wait_answer(controller: SessionController, ev: AstrMessageEvent):
            nonlocal item, session_done, session_correct, avail
            ans = ev.message_str.strip()

            if ans in ("跳过",):
                await self._remove_tg_buttons(ev)
                await ev.send(ev.plain_result("⏭️ 已跳过本题"))
                if self.cfg_continuous_quiz:
                    session_done += 1
                    # 刷新可用题并出下一题
                    p = await self._get_progress(uid)
                    d_ids = p.get("done_ids", [])
                    avail = [q for q in bank if q.get("index") not in d_ids]
                    if filter_arg:
                        avail = [q for q in avail if filter_arg in str(q.get("year", "")) or filter_arg in str(q.get("category", ""))]
                    if avail:
                        item = random.choice(avail)
                        await self._send_question(ev, item, subject)
                        await self._try_send_tg_buttons(ev, item)
                        controller.keep(timeout=self.cfg_quiz_timeout, reset_timeout=True)
                    else:
                        await ev.send(ev.plain_result(f"🎉 全部刷完！本轮: {session_done} 题，答对 {session_correct} 题"))
                        controller.stop()
                    return
                controller.stop()
                return

            if ans in ("退出", "结束", "不做了"):
                await self._remove_tg_buttons(ev)
                if self.cfg_continuous_quiz and session_done > 0:
                    await ev.send(ev.plain_result(f"📊 本轮刷题结束！共 {session_done} 题，答对 {session_correct} 题"))
                else:
                    await ev.send(ev.plain_result("📒 已退出刷题"))
                controller.stop()
                return

            await self._remove_tg_buttons(ev)
            is_correct = await self._process_answer(ev, uid, item, subject, ans)
            session_done += 1
            if is_correct:
                session_correct += 1

            if self.cfg_continuous_quiz:
                # 连续模式：自动出下一题
                p = await self._get_progress(uid)
                d_ids = p.get("done_ids", [])
                avail = [q for q in bank if q.get("index") not in d_ids]
                if filter_arg:
                    avail = [q for q in avail if filter_arg in str(q.get("year", "")) or filter_arg in str(q.get("category", ""))]
                if avail:
                    item = random.choice(avail)
                    await ev.send(ev.plain_result(f"📌 第 {session_done + 1} 题  (本轮 {session_correct}/{session_done} 正确)  发「退出」结束"))
                    await self._send_question(ev, item, subject)
                    await self._try_send_tg_buttons(ev, item)
                    controller.keep(timeout=self.cfg_quiz_timeout, reset_timeout=True)
                else:
                    await ev.send(ev.plain_result(f"🎉 全部刷完！本轮: {session_done} 题，答对 {session_correct} 题"))
                    controller.stop()
            else:
                controller.stop()

        try:
            await wait_answer(event)
        except TimeoutError:
            await self._remove_tg_buttons(event)
            if self.cfg_continuous_quiz and session_done > 0:
                yield event.plain_result(f"⏰ 超时！本轮: {session_done} 题，答对 {session_correct} 题")
            else:
                yield event.plain_result("⏰ 答题超时！下次要抓紧哦～")
        finally:
            event.stop_event()

    async def _send_question(self, event, item, subject):
        """发送题目（在 session_waiter 内使用 event.send）"""
        if self.cfg_render:
            url = await self._render_html(item)
            if url:
                await event.send(event.image_result(url))
                return
        await event.send(event.plain_result(self._format_question_text(item, subject)))

    def _format_question_text(self, item, subject):
        tp = '主观题' if item.get('_is_subjective') else '客观题'
        r = f"📝 【{subject}】{item.get('year', '')} {item.get('category', '')}\n"
        r += f"[{tp}] 分值: {item.get('score', '?')}分\n"
        r += "=" * 25 + "\n" + item.get("question", "") + "\n" + "=" * 25
        return r

    async def _process_answer(self, event, uid, item, subject, user_ans):
        prog = await self._get_progress(uid)
        done_ids = prog.setdefault("done_ids", [])
        qidx = item.get("index")
        if qidx is not None and qidx not in done_ids:
            done_ids.append(qidx)
        prog["last_question"] = {"subject": subject, "question_data": item}
        prog["last_answer_time"] = time.time()
        await self._set_progress(uid, prog)

        nickname = event.get_sender_name() if hasattr(event, 'get_sender_name') else ""

        if not item.get("_is_subjective"):
            is_correct, correct_str = self._grade_objective(item, user_ans)
            await self._record(uid, subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
            await self._update_leaderboard(uid, nickname)
            if not is_correct:
                await self._update_wrong_book(uid, item, False)
            res = f"{'✅ 回答正确！' if is_correct else '❌ 回答错误！'}"
            if self.cfg_render:
                safe_ans = html_mod.escape(user_ans.strip().upper())
                url = await self._render_html(item, True, f"【批改结果】{res}\n您的答案：{safe_ans}")
                if url:
                    await event.send(event.image_result(url))
                    return is_correct
            txt = f"{res}\n正确答案：{correct_str}"
            if item.get("analysis"):
                txt += f"\n📖 解析：\n{item['analysis'][:300]}..."
            await event.send(event.plain_result(txt))
            return is_correct
        else:
            await event.send(event.plain_result("⏳ AI名师正在批改主观解答..."))
            try:
                is_correct, llm_text = await self._grade_subjective(event, item, user_ans, subject)
                await self._record(uid, subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
                await self._update_leaderboard(uid, nickname)
                await self._update_wrong_book(uid, item, is_correct)
                if self.cfg_render:
                    url = await self._render_html(item, True, f"【AI 名师点评】\n{llm_text}")
                    if url:
                        await event.send(event.image_result(url))
                        return is_correct
                await event.send(event.plain_result(f"🤖 【AI 名师点评】\n{llm_text}"))
                return is_correct
            except Exception as e:
                logger.error(f"[GaokaoTutor] LLM grading error: {e}")
                await event.send(event.plain_result(f"⚠️ AI批改失败，参考答案：\n{item.get('answer')}"))
                return False

    # ─── Telegram 按钮支持 ─────────────────────────────────────

    async def _try_send_tg_buttons(self, event: AstrMessageEvent, item) -> bool:
        """对于客观题，在 Telegram 平台发送 reply keyboard 按钮。按钮按下后会发送文字消息，兼容 session_waiter。"""
        if item.get("_is_subjective"):
            return False
        try:
            if event.get_platform_name() != "telegram":
                return False
            from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
            raw = event.message_obj.raw_message
            bot = raw.get_bot() if hasattr(raw, 'get_bot') else None
            chat_id = raw.chat.id if hasattr(raw, 'chat') else None
            if not bot or not chat_id:
                return False
            # 构建选项按钮（一行4个选项 + 一行跳过）
            options = [KeyboardButton(text=opt) for opt in ["A", "B", "C", "D"]]
            markup = ReplyKeyboardMarkup(
                [options, [KeyboardButton(text="跳过")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await bot.send_message(chat_id=chat_id, text="👇 请选择答案：", reply_markup=markup)
            return True
        except Exception as e:
            logger.debug(f"[GaokaoTutor] TG buttons fallback: {e}")
            return False

    async def _remove_tg_buttons(self, event: AstrMessageEvent):
        """清除 Telegram 的 ReplyKeyboard 按钮"""
        try:
            if event.get_platform_name() != "telegram":
                return
            from telegram import ReplyKeyboardRemove
            raw = event.message_obj.raw_message
            bot = raw.get_bot() if hasattr(raw, 'get_bot') else None
            chat_id = raw.chat.id if hasattr(raw, 'chat') else None
            if not bot or not chat_id:
                return
            await bot.send_message(chat_id=chat_id, text="👇 （键盘已收起）", reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            logger.debug(f"[GaokaoTutor] TG remove buttons fallback: {e}")

    # ─── 每日推送 ──────────────────────────────────────────────

    async def _daily_push_loop(self):
        while True:
            try:
                now = datetime.now()
                target_time_str = self.cfg_daily_push_time
                target_hour, target_minute = map(int, target_time_str.split(':'))
                
                if now.hour == target_hour and now.minute == target_minute:
                    subscribers = await self.get_kv_data("subscribers", {})
                    for uid, umo in subscribers.items():
                        await self._push_to_user(uid, umo)
                    await asyncio.sleep(60)
                else:
                    await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[GaokaoTutor] Daily push loop error: {e}")
                await asyncio.sleep(60)

    async def _push_to_user(self, uid: str, umo: str):
        from astrbot.api.event import MessageChain
        
        try:
            exam = datetime.strptime(self.cfg_gaokao_date, "%Y-%m-%d")
        except:
            exam = datetime.now()
        days = max(0, (exam - datetime.now()).days)
        
        prog = await self._get_progress(uid)
        wb = prog.get("wrong_book", {})
        now = time.time()
        due = [(k, v) for k, v in wb.items() if now >= v.get("next_review", 0)]
        
        chain = MessageChain()
        chain.message(f"🌅 早上好！距 {exam.year} 高考还有 {days} 天！\n\n📌 每日错题打卡：\n")
        
        if not due:
            chain.message("🎉 你今天没有待复习的错题！非常棒！随时发 /刷题 保持手感吧。")
            await self.context.send_message(umo, chain)
            return
            
        qid, data = due[0]
        item = data["question"]
        subject = data["subject"]
        
        if self.cfg_render:
            url = await self._render_html(item, extra="每天做对一道错题，离梦想更进一步！\n请发送 /每日打卡 进行答题。")
            if url:
                chain.file_image(url)
            else:
                chain.message(self._format_question_text(item, subject) + "\n\n请发送 /每日打卡 开始作答。")
        else:
            chain.message(self._format_question_text(item, subject) + "\n\n请发送 /每日打卡 开始作答。")
            
        try:
            await self.context.send_message(umo, chain)
        except Exception as e:
            logger.error(f"[GaokaoTutor] Failed to send push message to {umo}: {e}")

    @filter.command("订阅")
    async def subscribe(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        uid = event.get_sender_id()
        subscribers = await self.get_kv_data("subscribers", {})
        if uid in subscribers:
            yield event.plain_result("✅ 您已经订阅过啦！每天会按时推送打卡内容。")
            return
        subscribers[uid] = umo
        await self.put_kv_data("subscribers", subscribers)
        yield event.plain_result(f"✅ 订阅成功！系统将于每日 {self.cfg_daily_push_time} 为您推送一道专属错题复习。")

    @filter.command("取消订阅")
    async def unsubscribe(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        subscribers = await self.get_kv_data("subscribers", {})
        if uid in subscribers:
            del subscribers[uid]
            await self.put_kv_data("subscribers", subscribers)
            yield event.plain_result("❎ 取消订阅成功，不再发送每日打卡。")
        else:
            yield event.plain_result("⚠️ 您还没有订阅呢。")

    # ─── 指令：专项 ────────────────────────────────────────────

    @filter.command("专项")
    async def specialized(self, event: AstrMessageEvent, subject: str = "", tag: str = ""):
        uid = event.get_sender_id()
        if not subject or subject not in SUBJECT_FILE_MAP:
            yield event.plain_result(f"⚠️ 用法：/专项 数学 2023\n支持科目：{', '.join(SUBJECT_FILE_MAP.keys())}")
            return
        bank = self.question_banks.get(subject, [])
        if tag:
            bank = [q for q in bank if tag in str(q.get("year", "")) or tag in str(q.get("category", ""))]
        if not bank:
            yield event.plain_result(f"😅 没有符合条件的题目")
            return
        item = random.choice(bank)
        if self.cfg_render:
            url = await self._render_html(item)
            if url:
                yield event.image_result(url)
            else:
                yield event.plain_result(self._format_question_text(item, subject))
        else:
            yield event.plain_result(self._format_question_text(item, subject))

        yield event.plain_result("✏️ 请直接发送答案，发 '跳过' 可跳过")

        @session_waiter(timeout=self.cfg_quiz_timeout, record_history_chains=False)
        async def wait(controller: SessionController, ev: AstrMessageEvent):
            ans = ev.message_str.strip()
            if ans == "跳过":
                await self._remove_tg_buttons(ev)
                await ev.send(ev.plain_result("⏭️ 已跳过"))
                controller.stop()
                return
            await self._remove_tg_buttons(ev)
            await self._process_answer(ev, uid, item, subject, ans)
            controller.stop()

        try:
            await wait(event)
        except TimeoutError:
            await self._remove_tg_buttons(event)
            yield event.plain_result("⏰ 答题超时！")
        finally:
            event.stop_event()

    # ─── 指令：闯关 ────────────────────────────────────────────

    @filter.command("闯关", alias={"PK", "pk"})
    async def rush_mode(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        scores = await self._get_scores(uid)
        subject = scores.get("current_subject", "数学")
        bank = self.question_banks.get(subject, [])
        obj_bank = [q for q in bank if not q.get("_is_subjective")]
        if len(obj_bank) < 5:
            yield event.plain_result("😅 客观题不足，无法闯关")
            return

        random.shuffle(obj_bank)
        batch = obj_bank[:self.cfg_rush_count]
        streak = 0

        yield event.plain_result(f"🎮 【闯关模式】{subject}，答错即止，最多 {len(batch)} 题！\n第 1 题：")

        item = batch[0]
        if self.cfg_render:
            url = await self._render_html(item)
            if url:
                yield event.image_result(url)
            else:
                yield event.plain_result(self._format_question_text(item, subject))
        else:
            yield event.plain_result(self._format_question_text(item, subject))

        nickname = event.get_sender_name() if hasattr(event, 'get_sender_name') else ""

        @session_waiter(timeout=self.cfg_quiz_timeout, record_history_chains=False)
        async def rush_wait(controller: SessionController, ev: AstrMessageEvent):
            nonlocal streak, item
            ans = ev.message_str.strip()
            if ans == "退出":
                await self._remove_tg_buttons(ev)
                await self._update_leaderboard(uid, nickname, streak=streak)
                await ev.send(ev.plain_result(f"🏁 闯关结束！本次闯过 {streak} 关"))
                controller.stop()
                return
            is_correct, correct_str = self._grade_objective(item, ans)
            await self._record(uid, subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
            await self._update_leaderboard(uid, nickname)
            if not is_correct:
                await self._update_wrong_book(uid, item, False)
                await self._remove_tg_buttons(ev)
                await self._update_leaderboard(uid, nickname, streak=streak)
                await ev.send(ev.plain_result(f"❌ 答错了！正确答案：{correct_str}\n🏁 闯关结束！本次闯过 {streak} 关"))
                controller.stop()
                return

            streak += 1
            if streak >= len(batch):
                await self._remove_tg_buttons(ev)
                await self._update_leaderboard(uid, nickname, streak=streak)
                await ev.send(ev.plain_result(f"🎉 全部通关！共 {streak} 题全对！太强了！"))
                controller.stop()
                return
            item = batch[streak]
            msg = f"✅ 正确！连击 x{streak}\n\n第 {streak+1} 题："
            await ev.send(ev.plain_result(msg))
            if self.cfg_render:
                url = await self._render_html(item)
                if url:
                    await ev.send(ev.image_result(url))
                else:
                    await ev.send(ev.plain_result(self._format_question_text(item, subject)))
            else:
                await ev.send(ev.plain_result(self._format_question_text(item, subject)))
            await self._try_send_tg_buttons(ev, item)
            controller.keep(timeout=self.cfg_quiz_timeout, reset_timeout=True)

        try:
            await rush_wait(event)
        except TimeoutError:
            await self._remove_tg_buttons(event)
            await self._update_leaderboard(uid, nickname, streak=streak)
            yield event.plain_result(f"⏰ 超时！闯关结束，本次闯过 {streak} 关")
        finally:
            event.stop_event()

    # ─── 指令：解析 ────────────────────────────────────────────

    @filter.command("解析", alias={"讲解", "分析"})
    async def llm_explain(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        prog = await self._get_progress(uid)
        last = prog.get("last_question")
        if not last:
            yield event.plain_result("🤔 没有最近做的题，先去 /刷题 吧！")
            return
        q = last["question_data"]
        sub = last["subject"]
        yield event.plain_result("⏳ AI名师正在解析...")
        try:
            prompt = f"""你是一位高考{sub}名师。请对以下真题深度解析。

【题目】{q.get('question')}
【答案】{q.get('answer')}
【官方解析】{q.get('analysis', '无')}

请按以下结构讲解：
1. 📚 核心考点
2. 💡 解题思路（详细步骤）
3. ⚠️ 易错提醒
4. 🔗 举一反三"""
            text = await self._llm_call(event, prompt)
            if self.cfg_render:
                url = await self._render_html(q, True, f"【AI 深度解析】\n{text}")
                if url:
                    yield event.image_result(url)
                    return
            yield event.plain_result(f"🤖 【AI 深度解析】\n{text}")
        except Exception as e:
            logger.error(f"[GaokaoTutor] explain error: {e}")
            yield event.plain_result("⚠️ AI解析失败，请检查模型配置。")
        event.stop_event()

    # ─── 指令：知识点 ──────────────────────────────────────────

    @filter.command("知识点")
    async def knowledge(self, event: AstrMessageEvent, topic: str = ""):
        if not topic:
            yield event.plain_result("⚠️ 请提供知识点，例如：/知识点 椭圆标准方程")
            return
        uid = event.get_sender_id()
        scores = await self._get_scores(uid)
        sub = scores.get("current_subject", "未知")
        yield event.plain_result(f"⏳ 正在整理【{topic}】...")
        try:
            prompt = f"""作为{sub}特级教师，请系统讲解：【{topic}】
包含：定义与核心公式、常见考察题型、易错点、一个示例"""
            text = await self._llm_call(event, prompt)
            yield event.plain_result(f"📘 【{topic} 知识梳理】\n{text}")
            event.stop_event()
            return
        except Exception:
            yield event.plain_result("⚠️ 生成知识点失败。")
        event.stop_event()

    # ─── 指令：诊断 ────────────────────────────────────────────

    @filter.command("诊断", alias={"AI诊断", "薄弱分析"})
    async def diagnose(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        scores = await self._get_scores(uid)
        subs = scores.get("subjects", {})
        if not subs:
            yield event.plain_result("📊 做题数据不足，先多刷点题再来诊断吧！")
            return
        summary = ""
        for s, d in subs.items():
            t = d.get("total_done", 0)
            c = d.get("total_correct", 0)
            if t == 0:
                continue
            summary += f"{s}: 做{t}题，对{c}题({c/t*100:.0f}%)"
            cats = d.get("by_category", {})
            weak = [(k, v) for k, v in cats.items() if v.get("done", 0) > 0 and v.get("correct", 0)/v["done"] < 0.5]
            if weak:
                summary += f"，薄弱：{','.join(w[0] for w in weak)}"
            summary += "\n"
        yield event.plain_result("⏳ AI正在分析你的学习数据...")
        try:
            prompt = f"""你是高考学习规划师。根据以下做题数据，分析薄弱环节并给出具体复习建议：
{summary}
请输出：1.各科情况总结 2.最薄弱的2-3个知识领域 3.具体的复习计划建议"""
            text = await self._llm_call(event, prompt)
            yield event.plain_result(f"🔍 【AI 薄弱诊断】\n{text}")
            event.stop_event()
            return
        except Exception:
            yield event.plain_result("⚠️ AI诊断失败。")
        event.stop_event()

    # ─── 指令：错题本(翻页) ────────────────────────────────────

    @filter.command("错题", alias={"错题本", "我的错题"})
    async def wrong_book(self, event: AstrMessageEvent, arg: str = ""):
        uid = event.get_sender_id()
        prog = await self._get_progress(uid)
        wb = prog.get("wrong_book", {})
        if not wb:
            yield event.plain_result("🎉 错题本是空的！继续保持！")
            return

        if arg == "复习":
            items = list(wb.values())
            if not items:
                yield event.plain_result("🎈 没有需要复习的错题！")
                return
            item = items[0]["question"]
            subject = items[0]["subject"]
            yield event.plain_result(f"📌 错题复习 ({len(items)} 道待复习)")
            if self.cfg_render:
                url = await self._render_html(item)
                if url:
                    yield event.image_result(url)
                else:
                    yield event.plain_result(self._format_question_text(item, subject))
            else:
                yield event.plain_result(self._format_question_text(item, subject))
            yield event.plain_result("✏️ 请直接发送答案")

            @session_waiter(timeout=self.cfg_quiz_timeout, record_history_chains=False)
            async def review_wait(controller: SessionController, ev: AstrMessageEvent):
                ans = ev.message_str.strip()
                if ans == "退出":
                    await self._remove_tg_buttons(ev)
                    await ev.send(ev.plain_result("📒 已退出错题复习"))
                    controller.stop()
                    return
                await self._remove_tg_buttons(ev)
                await self._process_answer(ev, uid, item, subject, ans)
                controller.stop()

            try:
                await review_wait(event)
            except TimeoutError:
                await self._remove_tg_buttons(event)
                yield event.plain_result("⏰ 复习超时！")
            finally:
                event.stop_event()
            return

        # 翻页显示
        page = 1
        if arg.isdigit():
            page = max(1, int(arg))
        items = list(wb.items())
        total = len(items)
        pages = (total + self.cfg_page_size - 1) // self.cfg_page_size
        page = min(page, pages)
        start = (page - 1) * self.cfg_page_size
        end = min(start + self.cfg_page_size, total)

        r = f"📒 【错题本】第 {page}/{pages} 页 (共 {total} 题)\n"
        r += "=" * 25 + "\n"
        for i in range(start, end):
            qid, data = items[i]
            q = data.get("question", {})
            r += f"{i+1}. [{data.get('subject','')}] {q.get('year','')} {q.get('category','')}\n"
            r += f"   错 {data.get('wrong_count',0)} 次 | 复习阶段 {data.get('stage',0)}/{len(EBBINGHAUS_INTERVALS)-1}\n"
        r += "=" * 25 + "\n"
        r += f"💡 /错题 {page+1} 翻页 | /错题 复习 进入复习模式"
        yield event.plain_result(r)

    # ─── 指令：每日打卡 ────────────────────────────────────────

    @filter.command("每日打卡", alias={"打卡", "复习"})
    async def daily_review(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        prog = await self._get_progress(uid)
        wb = prog.get("wrong_book", {})
        now = time.time()
        due = [(k, v) for k, v in wb.items() if now >= v.get("next_review", 0)]
        if not due:
            yield event.plain_result("🎈 今天没有需要复习的错题！可以去刷点新题。")
            return
        qid, data = due[0]
        item = data["question"]
        subject = data["subject"]
        yield event.plain_result(f"⏰ 【复习打卡】待复习: {len(due)} 道")
        if self.cfg_render:
            url = await self._render_html(item, extra="📌 这是一道你需要复习的错题！")
            if url:
                yield event.image_result(url)
            else:
                yield event.plain_result(self._format_question_text(item, subject))
        else:
            yield event.plain_result(self._format_question_text(item, subject))
        yield event.plain_result("✏️ 请直接发送答案")

        @session_waiter(timeout=self.cfg_quiz_timeout, record_history_chains=False)
        async def review_wait(controller: SessionController, ev: AstrMessageEvent):
            ans = ev.message_str.strip()
            if ans == "跳过":
                await self._remove_tg_buttons(ev)
                await ev.send(ev.plain_result("⏭️ 已跳过"))
                controller.stop()
                return
            await self._remove_tg_buttons(ev)
            await self._process_answer(ev, uid, item, subject, ans)
            controller.stop()

        try:
            await review_wait(event)
        except TimeoutError:
            await self._remove_tg_buttons(event)
            yield event.plain_result("⏰ 打卡超时！")
        finally:
            event.stop_event()

    # ─── 指令：我的成绩 ────────────────────────────────────────

    @filter.command("我的成绩", alias={"成绩", "分数"})
    async def my_scores(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        scores = await self._get_scores(uid)
        subs = scores.get("subjects", {})
        if not subs:
            yield event.plain_result("🤷 还没有做题记录，快去 /刷题 吧！")
            return
        r = "📊 【 高考备考成绩单 】\n" + "=" * 25 + "\n"
        best_acc, best_sub = 0, "无"
        for s, d in subs.items():
            t = d.get("total_done", 0)
            c = d.get("total_correct", 0)
            if t == 0:
                continue
            acc = c / t
            if t >= 5 and acc > best_acc:
                best_acc, best_sub = acc, s
            bar = "█" * int(acc * 10) + "░" * (10 - int(acc * 10))
            r += f"📘 {s}: {bar} {acc*100:.1f}% ({c}/{t})\n"
        ov = scores.get("overall", {})
        ot, oc = ov.get("total_done", 0), ov.get("total_correct", 0)
        r += "=" * 25 + "\n"
        r += f"📈 累计做题：{ot} 题\n"
        r += f"✨ 综合正确率：{oc/ot*100:.1f}%\n" if ot > 0 else "✨ 综合正确率：0%\n"
        r += f"🏆 优势科目：{best_sub}"
        yield event.plain_result(r)

    # ─── 指令：报告(可视化) ────────────────────────────────────

    @filter.command("报告", alias={"学习报告"})
    async def report(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        scores = await self._get_scores(uid)
        subs = scores.get("subjects", {})
        if not subs:
            yield event.plain_result("📊 数据不足，先做点题再看报告！")
            return
        ov = scores.get("overall", {})
        ot, oc = ov.get("total_done", 0), ov.get("total_correct", 0)
        oa = (oc / ot * 100) if ot > 0 else 0
        # 竖屏卡片式布局，每科一个卡片
        cards = ""
        for s, d in subs.items():
            t = d.get("total_done", 0)
            c = d.get("total_correct", 0)
            acc = (c / t * 100) if t > 0 else 0
            color = "#22c55e" if acc >= 60 else "#f59e0b" if acc >= 40 else "#ef4444"
            cards += f"""<div style="background:#fff;padding:16px 20px;border-radius:12px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-size:16px;font-weight:600;">{s}</span>
                <span style="font-size:18px;font-weight:700;color:{color};">{acc:.0f}%</span>
              </div>
              <div style="background:#e5e7eb;border-radius:6px;overflow:hidden;height:8px;margin-bottom:6px;"><div style="background:linear-gradient(90deg,{color},{color}88);height:100%;width:{acc}%;border-radius:6px;"></div></div>
              <div style="font-size:12px;color:#94a3b8;">做题 {t} · 正确 {c} · 错误 {t-c}</div>
            </div>"""
        tmpl = """
        <div style="font-family:'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif;padding:20px;background:#f1f5f9;color:#1e293b;width:100%;box-sizing:border-box;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;">
          <div style="text-align:center;margin-bottom:20px;">
            <div style="font-size:22px;font-weight:700;margin-bottom:4px;">📊 学习报告</div>
            <div style="font-size:14px;color:#64748b;">累计 {{ total }} 题 · 正确率 {{ overall_acc }}%</div>
          </div>
          <div style="background:linear-gradient(135deg,#6366f1,#818cf8);padding:20px;border-radius:14px;color:#fff;text-align:center;margin-bottom:16px;">
            <div style="font-size:40px;font-weight:800;line-height:1;">{{ overall_acc }}%</div>
            <div style="font-size:14px;margin-top:6px;opacity:.9;">综合正确率</div>
          </div>
          {{ cards }}
        </div>"""
        report_options = {"viewport": {"width": 420, "height": 800}, "scale": 2}
        try:
            url = await self.html_render(tmpl, {"total": ot, "overall_acc": f"{oa:.1f}", "cards": cards}, options=report_options)
            yield event.image_result(url)
        except Exception:
            # 文字降级方案
            r = f"📊 【学习报告】\n综合正确率：{oa:.1f}% (共 {ot} 题)\n" + "=" * 25 + "\n"
            for s, d in subs.items():
                t = d.get("total_done", 0)
                c = d.get("total_correct", 0)
                acc = (c / t * 100) if t > 0 else 0
                bar = "█" * int(acc / 10) + "░" * (10 - int(acc / 10))
                r += f"{s}: {bar} {acc:.0f}% ({c}/{t})\n"
            yield event.plain_result(r)

    @filter.command("模考", alias={"模拟考试"})
    async def mock_exam(self, event: AstrMessageEvent, subject: str = ""):
        uid = event.get_sender_id()
        if not subject:
            scores = await self._get_scores(uid)
            subject = scores.get("current_subject", "数学")
            
        if subject not in SUBJECT_FILE_MAP:
            yield event.plain_result(f"⚠️ 支持的科目：{', '.join(SUBJECT_FILE_MAP.keys())}\n用法：/模考 数学")
            return
            
        bank = self.question_banks.get(subject, [])
        obj_bank = [q for q in bank if not q.get("_is_subjective")]
        sub_bank = [q for q in bank if q.get("_is_subjective")]
        
        sel_c = min(self.cfg_exam_select_count, len(obj_bank))
        sub_c = min(self.cfg_exam_subject_count, len(sub_bank))
        
        if sel_c == 0 and sub_c == 0:
            yield event.plain_result("😅 题库中该科目题目不足！")
            return
        
        exam_questions = random.sample(obj_bank, sel_c) + random.sample(sub_bank, sub_c)
        
        yield event.plain_result(f"📝 【模拟考试】开始！\n科目：{subject}\n题量：客观题 {sel_c} 道，主观题 {sub_c} 道。\n你可以随时发 '退出' 结束模考，发 '跳过' 放弃本题。\n祝你好运！")
        
        curr_idx = 0
        total = len(exam_questions)
        correct_count = 0
        earned_score = 0
        total_score = 0
        results_log = []
        
        # 发送第一题
        item = exam_questions[curr_idx]
        q_score = item.get("score", 5 if not item.get("_is_subjective") else 12)
        try:
            total_score += float(q_score)
        except:
            total_score += 5
            
        await self._send_exam_question(event, item, subject, curr_idx, total)
        await self._try_send_tg_buttons(event, item)

        @session_waiter(timeout=self.cfg_quiz_timeout, record_history_chains=False)
        async def exam_wait(controller: SessionController, ev: AstrMessageEvent):
            nonlocal curr_idx, correct_count, earned_score, total_score, results_log, item
            ans = ev.message_str.strip()
            
            if ans == "退出":
                await self._remove_tg_buttons(ev)
                await ev.send(ev.plain_result("🏁 已退出模拟考试。"))
                controller.stop()
                return

            if ans == "跳过":
                results_log.append((item, False, 0, "跳过"))
                await ev.send(ev.plain_result("⏭️ 已跳过本题"))
            else:
                if not item.get("_is_subjective"):
                    is_correct, correct_str = self._grade_objective(item, ans)
                    await self._record(uid, subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
                    if not is_correct:
                        await self._update_wrong_book(uid, item, False)
                    sc = float(item.get("score", 5))
                    earned = sc if is_correct else 0
                    if is_correct:
                        correct_count += 1
                        earned_score += earned
                    results_log.append((item, is_correct, earned, f"你的答案:{html_mod.escape(ans.upper())} 正确答案:{correct_str}"))
                    
                    await ev.send(ev.plain_result(f"{'✅ 回答正确！' if is_correct else '❌ 回答错误！'} (得分: {earned})"))
                else:
                    await ev.send(ev.plain_result("⏳ 收到主观题作答，继续下一题... (将在交卷后统一展示评分)"))
                    is_correct, llm_text = await getattr(self, "_grade_subjective")(ev, item, ans, subject)
                    await self._record(uid, subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
                    await self._update_wrong_book(uid, item, is_correct)
                    match = re.search(r"【总分】.*?(\d+(?:\.\d+)?)\s*分?", llm_text)
                    earned = float(match.group(1)) if match else 0.0
                    earned_score += earned
                    results_log.append((item, is_correct, earned, f"【AI名师点评】：\n{llm_text}"))

            curr_idx += 1
            if curr_idx >= total:
                await self._remove_tg_buttons(ev)
                await self._show_exam_report(ev, subject, earned_score, total_score, results_log)
                controller.stop()
                return
                
            item = exam_questions[curr_idx]
            q_score = item.get("score", 5 if not item.get("_is_subjective") else 12)
            try:
                total_score += float(q_score)
            except:
                total_score += 5
                
            await self._send_exam_question(ev, item, subject, curr_idx, total)
            await self._try_send_tg_buttons(ev, item)
            controller.keep(timeout=self.cfg_quiz_timeout, reset_timeout=True)

        try:
            await exam_wait(event)
        except TimeoutError:
            await self._remove_tg_buttons(event)
            yield event.plain_result("⏰ 模考超时，自动交卷！")
            # 超时也可以显示已有成绩，此处为简略处理
        finally:
            event.stop_event()

    async def _send_exam_question(self, event, item, subject, curr_idx, total):
        title = f"📝 模考 第 {curr_idx+1}/{total} 题\n"
        if self.cfg_render:
            url = await getattr(self, "_render_html")(item, extra=title)
            if url:
                await event.send(event.image_result(url))
                return
        await event.send(event.plain_result(title + "\n" + self._format_question_text(item, subject)))

    async def _show_exam_report(self, event, subject, earned, total_s, results):
        acc = (earned / total_s * 100) if total_s > 0 else 0
        r = f"📋 【{subject} 模考成绩单】\n"
        r += f"总得分：{earned} / {total_s} 分\n"
        r += f"得分率：{acc:.1f}%\n"
        r += "=" * 25 + "\n"
        for i, (item, is_ok, score, msg) in enumerate(results):
            r += f"第{i+1}题 [{item.get('category','')}] {'✅' if is_ok else '❌'}  得 {score}分\n"
        r += "=" * 25 + "\n"
        r += "💡 发送 /错题 可查看你做错的题目。若有主观题，上方评分别忘了仔细看哦！\n"
        await event.send(event.plain_result(r))
        for i, (item, is_ok, score, msg) in enumerate(results):
            if not is_ok and item.get("_is_subjective"):
                await event.send(event.plain_result(f"—— 第{i+1}题主观题扣分点还原 ——\n{msg}"))

    # ─── 指令：排行榜 ──────────────────────────────────────────

    @filter.command("排行榜", alias={"排行", "leaderboard"})
    async def leaderboard(self, event: AstrMessageEvent, mode: str = ""):
        lb = await self.get_kv_data("leaderboard", {})
        if not lb:
            yield event.plain_result("🏆 还没有人上榜呢！快去 /刷题 或 /闯关 冲榜吧！")
            return

        mode = mode.strip()
        if mode in ("正确率", "准确率", "accuracy"):
            text = self._format_leaderboard(lb, "accuracy", "正确率排行榜", "🎯", min_done=20)
        elif mode in ("连击", "闯关", "streak"):
            text = self._format_leaderboard(lb, "best_streak", "闯关连击排行榜", "🔥")
        elif mode in ("混合", "混合挑战", "mix"):
            text = self._format_leaderboard(lb, "mix_best_streak", "混合挑战连击榜", "🌈")
        elif mode in ("今日", "today", "活跃"):
            # 重置非今日的数据
            today = datetime.now().strftime("%Y-%m-%d")
            for k, v in lb.items():
                if v.get("today_date") != today:
                    v["today_done"] = 0
            text = self._format_leaderboard(lb, "today_done", "今日活跃榜", "📅")
        else:
            text = self._format_leaderboard(lb, "total_done", "总刷题排行榜", "🏆")

        yield event.plain_result(text)

    # ─── 指令：混合挑战 ────────────────────────────────────────

    def _parse_subjects(self, input_str: str) -> list:
        if not input_str:
            return []
        input_str = input_str.replace(" ", "").replace(",", "").replace("，", "").replace("、", "")
        res = set()
        if "理综" in input_str:
            res.update(["物理", "化学", "生物"])
        if "文综" in input_str:
            res.update(["历史", "政治", "地理"])
        if "全科" in input_str:
            res.update(SUBJECT_FILE_MAP.keys())
        
        mapping = {"物": "物理", "化": "化学", "生": "生物", "政": "政治", "史": "历史", "历": "历史", "地": "地理", "语": "语文", "数": "数学", "英": "英语", "外": "英语"}
        for k, v in mapping.items():
            if k in input_str:
                res.add(v)
                
        for subj in SUBJECT_FILE_MAP.keys():
            if subj in input_str:
                res.add(subj)
                
        return list(res)

    @filter.command("选科组合", alias={"设置组合", "我的组合"})
    async def set_mix_combo(self, event: AstrMessageEvent, combo: str = ""):
        uid = event.get_sender_id()
        if not combo:
            scores = await self._get_scores(uid)
            mix_subs = scores.get("mix_subjects", [])
            if mix_subs:
                yield event.plain_result(f"🎯 你当前的混合挑战组合是：{', '.join(mix_subs)}\n重新设置请发送：/选科组合 物化生 等")
            else:
                yield event.plain_result("⚠️ 你还没有设置混合挑战组合！\n用法：/选科组合 [你想挑战的科目]\n如：/选科组合 物化生、/选科组合 理综、/选科组合 语数英物化政 等")
            return
            
        parsed = self._parse_subjects(combo)
        if not parsed:
            yield event.plain_result("😅 没有识别出有效的科目，请检查输入规则~")
            return
            
        scores = await self._get_scores(uid)
        scores["mix_subjects"] = parsed
        await self._set_scores(uid, scores)
        yield event.plain_result(f"✅ 混合挑战组合设置成功！\n🎯 当前挑战科目：{', '.join(parsed)}\n发 /混合挑战 试试看吧！")

    @filter.command("混合挑战", alias={"混合闯关", "综合挑战"})
    async def mix_challenge(self, event: AstrMessageEvent, combo: str = ""):
        uid = event.get_sender_id()
        nickname = event.get_sender_name() if hasattr(event, 'get_sender_name') else ""

        scores = await self._get_scores(uid)
        
        # 确定挑战科目
        if combo:
            mix_subs = self._parse_subjects(combo)
            if not mix_subs:
                yield event.plain_result("😅 未识别出有效的临时挑战科目，请检查输入")
                return
        else:
            mix_subs = scores.get("mix_subjects", [])
            
        if not mix_subs:
            yield event.plain_result("⚠️ 你还没有设置混合挑战科目范围！\n你可以使用:\n1. /混合挑战 物化政 (临时混合这三科)\n2. /选科组合 语数英物化生 (系统长期保存该组合偏好)")
            return

        # 从选定科目中汇集客观题
        all_obj = []
        for subject, questions in self.question_banks.items():
            if subject in mix_subs:
                for q in questions:
                    if not q.get("_is_subjective"):
                        all_obj.append(q)

        if len(all_obj) < 10:
            yield event.plain_result(f"😅 【{', '.join(mix_subs)}】的中可用客观题不足十道，请扩大科目范围")
            return

        random.shuffle(all_obj)
        batch = all_obj[:self.cfg_mix_challenge_count]
        streak = 0

        yield event.plain_result(f"🌈 【混合挑战】当前已选科目：{', '.join(mix_subs)}\n答错即止，最多 {len(batch)} 题！\n\n第 1 题：")

        item = batch[0]
        item_subject = item.get("_subject", "未知")
        await self._send_question(event, item, item_subject)
        await self._try_send_tg_buttons(event, item)

        @session_waiter(timeout=self.cfg_quiz_timeout, record_history_chains=False)
        async def mix_wait(controller: SessionController, ev: AstrMessageEvent):
            nonlocal streak, item, item_subject
            ans = ev.message_str.strip()
            if ans == "退出":
                await self._remove_tg_buttons(ev)
                await self._update_leaderboard(uid, nickname, mix_streak=streak)
                await ev.send(ev.plain_result(f"🏁 混合挑战结束！本次闯过 {streak} 关"))
                controller.stop()
                return
            is_correct, correct_str = self._grade_objective(item, ans)
            await self._record(uid, item_subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
            await self._update_leaderboard(uid, nickname)
            if not is_correct:
                await self._update_wrong_book(uid, item, False)
                await self._remove_tg_buttons(ev)
                await self._update_leaderboard(uid, nickname, mix_streak=streak)
                await ev.send(ev.plain_result(f"❌ 答错了！正确答案：{correct_str}\n📘 科目: {item_subject}\n🏁 混合挑战结束！本次闯过 {streak} 关"))
                controller.stop()
                return

            streak += 1
            if streak >= len(batch):
                await self._remove_tg_buttons(ev)
                await self._update_leaderboard(uid, nickname, mix_streak=streak)
                await ev.send(ev.plain_result(f"🎉 全部通关！共 {streak} 题全对！你是全科之王！"))
                controller.stop()
                return
            item = batch[streak]
            item_subject = item.get("_subject", "未知")
            msg = f"✅ 正确！连击 ×{streak}  [{item_subject}]\n\n第 {streak+1} 题："
            await ev.send(ev.plain_result(msg))
            await self._send_question(ev, item, item_subject)
            await self._try_send_tg_buttons(ev, item)
            controller.keep(timeout=self.cfg_quiz_timeout, reset_timeout=True)

        try:
            await mix_wait(event)
        except TimeoutError:
            await self._remove_tg_buttons(event)
            await self._update_leaderboard(uid, nickname, mix_streak=streak)
            yield event.plain_result(f"⏰ 超时！混合挑战结束，本次闯过 {streak} 关")
        finally:
            event.stop_event()

    # ─── 指令：我的Key ─────────────────────────────────────────

    @filter.command("我的Key", alias={"我的key", "mykey", "MyKey"})
    async def my_key(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        nickname = event.get_sender_name() if hasattr(event, 'get_sender_name') else ""
        key = await self._get_or_create_key(uid, nickname)
        user_keys = await self.get_kv_data("user_keys", {})
        info = user_keys.get(key, {})
        bind_count = len(info.get("bind_platforms", []))

        r = "🔑 【个人标识码】\n"
        r += "=" * 28 + "\n"
        r += f"🆔 Key: {key}\n"
        r += f"👤 昵称: {nickname}\n"
        r += f"🔗 已绑定 {bind_count} 个平台\n"
        r += "=" * 28 + "\n"
        r += "💡 此 Key 是你的唯一身份标识\n"
        r += "📲 未来可用于微信小程序绑定同步数据\n"
        r += "🔗 在其他平台发送 /绑定 " + key + " 关联同一账号"
        yield event.plain_result(r)

    # ─── 指令：绑定 ────────────────────────────────────────────

    @filter.command("绑定", alias={"bind"})
    async def bind_key(self, event: AstrMessageEvent, target_key: str = ""):
        uid = event.get_sender_id()
        if not target_key:
            yield event.plain_result("⚠️ 用法：/绑定 <Key>\n💡 在原平台发送 /我的Key 获取你的 Key")
            return

        # 检查目标 key 是否存在
        user_keys = await self.get_kv_data("user_keys", {})
        if target_key not in user_keys:
            yield event.plain_result("❌ Key 不存在，请检查后重试")
            return

        uid_to_key = await self.get_kv_data("uid_to_key", {})
        existing_key = uid_to_key.get(uid)

        if existing_key == target_key:
            yield event.plain_result("✅ 你已经绑定了这个 Key")
            return

        if existing_key and existing_key != target_key:
            yield event.plain_result(f"⚠️ 你当前已绑定 Key: {existing_key}\n暂不支持更换绑定（防止数据丢失）")
            return

        # 执行绑定
        uid_to_key[uid] = target_key
        user_keys[target_key]["bind_platforms"].append(uid)
        await self.put_kv_data("uid_to_key", uid_to_key)
        await self.put_kv_data("user_keys", user_keys)

        yield event.plain_result(f"✅ 绑定成功！已关联到 Key: {target_key}\n你的做题数据将与原账号同步")

    # ─── 智能意图识别：自动继续刷题 ────────────────────────────

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def intent_catcher(self, event: AstrMessageEvent):
        """捕获'继续''下一题'等关键词，自动触发刷题"""
        msg = event.message_str.strip()
        if msg not in CONTINUE_KEYWORDS:
            return  # 不匹配则不干预

        uid = event.get_sender_id()
        prog = await self._get_progress(uid)
        last_time = prog.get("last_answer_time", 0)

        # 只在最近5分钟内有做题记录时才拦截
        if time.time() - last_time > 300:
            return

        # 自动触发刷题
        async for result in self.quiz(event):
            yield result

