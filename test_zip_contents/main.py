import os
import json
import random
import time
import asyncio
from datetime import datetime
from astrbot.api.all import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_PROGRESS_PATH = os.path.join(BASE_DIR, 'user_progress.json')
USER_SCORES_PATH = os.path.join(BASE_DIR, 'user_scores.json')
SUBSCRIBER_PATH = os.path.join(BASE_DIR, 'subscribers_gaokao.json')

# 艾宾浩斯复习间隔 (12h, 1d, 2d, 4d, 7d, 15d)
EBBINGHAUS_INTERVALS = [43200, 86400, 172800, 345600, 604800, 1296000]

SUBJECT_FILE_MAP = {
    "数学": [
        "2010-2022_Math_I_MCQs.json", "2010-2022_Math_II_MCQs.json",
        "2010-2022_Math_I_Fill-in-the-Blank.json", "2010-2022_Math_I_Open-ended_Questions.json",
        "2010-2022_Math_II_Fill-in-the-Blank.json", "2010-2022_Math_II_Open-ended_Questions.json",
        "2023_Math_MCQs.json", "2024_Math_MCQs.json"
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
        "2024_Chinese_Lang_and_Usage_MCQs.json", "2024_Chinese_Modern_Lit.json"
    ],
    "英语": [
        "2010-2013_English_MCQs.json", "2010-2022_English_Fill_in_Blanks.json",
        "2010-2022_English_Reading_Comp.json", "2012-2022_English_Cloze_Test.json",
        "2012-2022_English_Language_Error_Correction.json", "2014-2022_English_Language_Cloze_Passage.json",
        "2023_English_Cloze_Test.json", "2023_English_Fill_in_Blanks.json", "2023_English_Reading_Comp.json",
        "2024_English_Cloze_Test.json", "2024_English_Fill_in_Blanks.json", "2024_English_Reading_Comp.json"
    ],
    "物理": ["2010-2022_Physics_MCQs.json", "2010-2022_Physics_Open-ended_Questions.json", "2023_Physics_MCQs.json", "2024_Physics_MCQs.json"],
    "化学": ["2010-2022_Chemistry_MCQs.json", "2010-2022_Chemistry_Open-ended_Questions.json", "2023_Chemistry_MCQs.json", "2024_Chemistry_MCQs.json"],
    "生物": ["2010-2022_Biology_MCQs.json", "2010-2022_Biology_Open-ended_Questions.json", "2023_Biology_MCQs.json", "2024_Biology_MCQs.json"],
    "历史": ["2010-2022_History_MCQs.json", "2010-2022_History_Open-ended_Questions.json", "2023_History_MCQs.json", "2024_History_MCQs.json"],
    "地理": ["2010-2022_Geography_MCQs.json", "2010-2022_Geography_Open-ended_Questions.json", "2023_Geography_MCQs.json", "2024_Geography_MCQs.json"],
    "政治": ["2010-2022_Political_Science_MCQs.json", "2010-2022_Political_Science_Open-ended_Questions.json", "2023_Political_Science_MCQs.json", "2024_Political_Science_MCQs.json"]
}

@register("astrbot_plugin_gaokao", "202704948-design", "高考金牌私教", "1.0.0")
class GaokaoTutor(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        
        self.cfg_render = self.config.get("render_as_image", True)
        self.cfg_gaokao_date = self.config.get("gaokao_date", "2026-06-07")
        
        self.question_banks = {}
        self.user_progress = self._load_json(USER_PROGRESS_PATH, {"done_questions": [], "wrong_book": {}})
        self.user_scores = self._load_json(USER_SCORES_PATH, {"current_subject": "数学", "subjects": {}, "overall": {}})
        self.subscribers = self._load_json(SUBSCRIBER_PATH, {})
        self.user_sessions = {}
        
        self.load_data()
        asyncio.create_task(self.daily_push_task())

    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return default

    def _save_json(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_data(self):
        obj_dir = os.path.join(BASE_DIR, 'Data', 'Objective_Questions')
        sub_dir = os.path.join(BASE_DIR, 'Data', 'Subjective_Questions')
        
        for subject, files in SUBJECT_FILE_MAP.items():
            self.question_banks[subject] = []
            for fname in files:
                fpath = os.path.join(obj_dir, fname)
                if not os.path.exists(fpath):
                    fpath = os.path.join(sub_dir, fname)
                
                if os.path.exists(fpath):
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            if isinstance(data, dict):
                                if "example" in data: questions = data["example"]
                                elif "questions" in data: questions = data["questions"]
                                else: questions = []
                            else:
                                questions = data
                                
                            for q in questions:
                                q["_subject"] = subject
                                q["_file"] = fname
                                ans = q.get("answer", "")
                                # Check if objective (usually array of A/B/C/D)
                                is_obj = False
                                if isinstance(ans, list) and len(ans) > 0 and len(str(ans[0])) <= 4:
                                    is_obj = True
                                q["_is_subjective"] = not is_obj
                            
                            self.question_banks[subject].extend(questions)
                    except Exception as e:
                        print(f"[GaokaoTutor] Error loading {fname}: {e}")

    async def render_question_html(self, item, include_answer=False, additional_text=""):
        q_text = item.get("question", "").replace('\n', '<br>')
        ans_text = item.get("answer", "")
        if isinstance(ans_text, list):
            ans_text = "".join(str(x) for x in ans_text)
        ans_text = str(ans_text).replace('\n', '<br>')
        analysis_text = item.get("analysis", "").replace('\n', '<br>')
        
        content_html = f"<div style='font-size: 18px;'>{q_text}</div>"
        if include_answer:
            content_html += f"<div style='margin-top:20px; padding:15px; background:#e8f4f8; border-radius:8px;'><b>正确答案：</b><br>{ans_text}</div>"
            if analysis_text:
                content_html += f"<div style='margin-top:15px; padding:15px; background:#f0fdf4; border-radius:8px;'><b>解析：</b><br>{analysis_text}</div>"
        
        if additional_text:
            add_html = additional_text.replace('\n', '<br>')
            content_html += f"<div style='margin-top:20px; padding:15px; background:#fff2f2; border-radius:8px;'>{add_html}</div>"

        html_tmpl = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script>
                MathJax = {{
                    tex: {{inlineMath: [['$', '$'], ['\\\\(', '\\\\)']]}}
                }};
            </script>
            <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; line-height: 1.8; background-color: #f8f9fa; color: #333; }}
                .card {{ background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.05); }}
                .tag {{ display: inline-block; padding: 6px 12px; background-color: #e2e8f0; border-radius: 6px; font-size: 14px; margin-right: 10px; color: #475569; font-weight: 500; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div style="margin-bottom: 20px; display:flex; align-items: center; gap: 8px;">
                    <span class="tag">{'主观题' if item.get('_is_subjective') else '客观题'}</span>
                    <span class="tag">{item.get('year', '未知年份')}</span>
                    <span class="tag">{item.get('category', '')}</span>
                    <span class="tag">{item.get('score', '?')}分</span>
                </div>
                {content_html}
            </div>
        </body>
        </html>
        """
        try:
            url = await self.context.html_render(html_tmpl)
            return url
        except Exception as e:
            print(f"[GaokaoTutor] Render Error: {e}")
            return None

    @filter.command("高考帮助")
    async def show_help(self, event: AstrMessageEvent):
        today = datetime.now()
        try:
            exam_date = datetime.strptime(self.cfg_gaokao_date, "%Y-%m-%d")
            days_left = (exam_date - today).days
            days_str = f"距 {exam_date.year} 高考还有 {max(0, days_left)} 天！"
        except Exception:
            days_str = "高考倒计时配置有误"

        reply = f"🎓 【 高考金牌私教 】 🎓\n"
        reply += f"🔥 {days_str} 🔥\n"
        reply += "=" * 28 + "\n"
        reply += "📘 刷题模块\n"
        reply += " ▫️ /选科 [科目] : 切换当前科目(如 /选科 数学)\n"
        reply += " ▫️ /刷题 [年份/卷名] : 随机抽取一道真题\n"
        reply += " ▫️ /答 [你的答案] : 提交解答并自动批改\n\n"
        reply += "🧠 AI名师模块\n"
        reply += " ▫️ /解析 : 邀请 AI 深度解析上一道题\n"
        reply += " ▫️ /知识点 [内容] : 让 AI 梳理指定知识点\n\n"
        reply += "📒 统计与错题\n"
        reply += " ▫️ /错题本 : 查看各区错题数\n"
        reply += " ▫️ /每日打卡 : 重做今日到期错题\n"
        reply += " ▫️ /我的成绩 : 总结全科学习进度与维度评分\n"
        yield event.plain_result(reply)

    @filter.command("选科")
    async def select_subject(self, event: AstrMessageEvent, subject: str = ""):
        if not subject or subject not in SUBJECT_FILE_MAP:
            yield event.plain_result(f"⚠️ 支持的科目有：{', '.join(SUBJECT_FILE_MAP.keys())}\n用法：/选科 数学")
            return
            
        self.user_scores["current_subject"] = subject
        self._save_json(USER_SCORES_PATH, self.user_scores)
        yield event.plain_result(f"✅ 已切换到【{subject}】，可以开始发送 /刷题 啦！")

    @filter.command("刷题")
    async def quiz(self, event: AstrMessageEvent, filter_arg: str = ""):
        subject = self.user_scores.get("current_subject", "数学")
        bank = self.question_banks.get(subject, [])
        done_ids = [q["index"] for q in self.user_progress.get("done_questions", [])]

        available = [q for q in bank if q.get("index") not in done_ids]
        if filter_arg:
            available = [q for q in available if filter_arg in q.get("year", "") or filter_arg in q.get("category", "")]

        if not available:
            yield event.plain_result(f"🎉 你已经刷完了 {subject} 的所有题！太强了！")
            return

        item = random.choice(available)
        user_id = event.sender.user_id
        
        self.user_sessions[user_id] = {
            "question": item,
            "subject": subject,
            "time": time.time()
        }

        if self.cfg_render:
            url = await self.render_question_html(item)
            if url:
                yield event.image_result(url)
                yield event.plain_result("👉 请回复：/答 A (或文字解答)")
                return

        reply = f"📝 【{subject}】{item.get('year', '')} {item.get('category', '')}\n"
        reply += f"[{'主观题' if item.get('_is_subjective') else '客观题'}] 分值: {item.get('score', '?')}分\n"
        reply += "=" * 25 + "\n"
        reply += item["question"] + "\n"
        reply += "=" * 25 + "\n"
        reply += "👉 请回复：/答 A (或文字解答)"
        yield event.plain_result(reply)

    def _record_score(self, subject, is_correct, category, year):
        subs = self.user_scores.setdefault("subjects", {})
        sub_data = subs.setdefault(subject, {"total_done": 0, "total_correct": 0, "by_year": {}, "by_category": {}})
        
        sub_data["total_done"] += 1
        if is_correct:
            sub_data["total_correct"] += 1
            
        # By Year
        yr = sub_data["by_year"].setdefault(year, {"done": 0, "correct": 0})
        yr["done"] += 1
        if is_correct: yr["correct"] += 1
        
        # By Category
        cat = sub_data["by_category"].setdefault(category, {"done": 0, "correct": 0})
        cat["done"] += 1
        if is_correct: cat["correct"] += 1
        
        # Overall
        overall = self.user_scores.setdefault("overall", {"total_done": 0, "total_correct": 0})
        overall["total_done"] += 1
        if is_correct: overall["total_correct"] += 1
        
        self._save_json(USER_SCORES_PATH, self.user_scores)

    def _add_to_wrong_book(self, item, user_ans, is_correct=False):
        q_idx = str(item.get("index", time.time()))
        wb = self.user_progress.setdefault("wrong_book", {})
        
        if q_idx not in wb:
            wb[q_idx] = {
                "subject": item.get("_subject", ""),
                "question": item,
                "add_time": time.time(),
                "stage": 0,
                "next_review": time.time() + EBBINGHAUS_INTERVALS[0],
                "wrong_count": 0
            }
        
        if not is_correct:
            wb[q_idx]["wrong_count"] += 1
            # Reset stage on failure
            wb[q_idx]["stage"] = 0
            wb[q_idx]["next_review"] = time.time() + EBBINGHAUS_INTERVALS[0]
        else:
            stage = wb[q_idx]["stage"]
            if stage < len(EBBINGHAUS_INTERVALS) - 1:
                wb[q_idx]["stage"] += 1
                wb[q_idx]["next_review"] = time.time() + EBBINGHAUS_INTERVALS[wb[q_idx]["stage"]]
            else:
                del wb[q_idx]

    @filter.command("答")
    async def submit_answer(self, event: AstrMessageEvent, user_ans: str = ""):
        user_id = event.get_sender_id()
        session = self.user_sessions.get(user_id)
        
        if not session:
            yield event.plain_result("🤔 没有正在做的题目，先发 /刷题 抽一道吧！")
            return

        item = session["question"]
        subject = session["subject"]
        
        # Save to done questions
        done_list = self.user_progress.setdefault("done_questions", [])
        q_info = {"index": item.get("index")}
        if q_info not in done_list:
            done_list.append(q_info)
            
        self.user_progress["last_question"] = {
            "subject": subject,
            "question_data": item
        }

        if not item.get("_is_subjective"):
            # 客观题自动批改
            correct_ans = item.get("answer", [])
            correct_ans_str = "".join(str(x) for x in correct_ans).strip().upper()
            user_ans_fmt = user_ans.strip().upper()
            
            is_correct = False
            for ans_item in correct_ans:
                if str(ans_item).strip().upper() in user_ans_fmt:
                    is_correct = True
                    break

            self._record_score(subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
            if not is_correct:
                self._add_to_wrong_book(item, user_ans_fmt, False)
            
            self._save_json(USER_PROGRESS_PATH, self.user_progress)
            del self.user_sessions[user_id]
            
            res_text = f"{'✅ 回答正确！' if is_correct else '❌ 回答错误！'}"
            if self.cfg_render:
                url = await self.render_question_html(item, include_answer=True, additional_text=f"【批改结果】{res_text}\n您的答案：{user_ans_fmt}")
                if url:
                    yield event.image_result(url)
                    return
                    
            txt = f"{res_text}\n"
            txt += f"正确答案：{correct_ans_str}\n"
            if item.get("analysis"): 
                txt += f"\n📖 解析：\n{item.get('analysis')[:200]}..."
            yield event.plain_result(txt)

        else:
            # 主观题 LLM 批改
            yield event.plain_result("⏳ 正在请求 AI 名师批改主观解答，请稍候...")
            try:
                provider_id = await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)
                max_score = item.get('score', 10)
                if not str(max_score).isdigit():
                    max_score = 10
                max_score = float(max_score)
                
                prompt = f"""你是一名高中{subject}老师，正在批改高考{subject}试卷。请根据下面的【题目】、【分析过程】、【标准答案】、【分值】、【学生分析与答案】，对【学生分析与答案】进行判分并给出理由。请注意【学生分析与答案】可能为空。输出格式为：【判分理由】...\n 【得分】...\n...【总分】...分
其中【总分】直接给出这道题的最终分数，如【总分】5分，注意不要超过这道题的【分值】。请严格对照标准答案和学生答案给分。

【题目】{item.get('question')}
【分析过程】{item.get('analysis', '无')}
【标准答案】{item.get('answer')}
【分值】{max_score}
【学生分析与答案】{user_ans}
"""
                llm_res = await self.context.llm_generate(chat_provider_id=provider_id, prompt=prompt)
                llm_text = llm_res.completion_text
                
                import re
                score_match = re.search(r"【总分】.*?(\d+(?:\.\d+)?)\s*分", llm_text)
                if not score_match:
                    score_match = re.search(r"【总分】.*?(\d+(?:\.\d+)?)", llm_text)
                    
                earned_score = float(score_match.group(1)) if score_match else 0.0
                
                # 及格线为60%
                is_correct = earned_score >= (max_score * 0.6)

                self._record_score(subject, is_correct, item.get('category', '未知'), item.get('year', '未知'))
                self._add_to_wrong_book(item, user_ans, is_correct)
                self._save_json(USER_PROGRESS_PATH, self.user_progress)
                del self.user_sessions[user_id]
                
                if self.cfg_render:
                    url = await self.render_question_html(item, include_answer=True, additional_text=f"【AI 名师点评】\n{llm_text}")
                    if url:
                        yield event.image_result(url)
                        return
                
                yield event.plain_result(f"🤖 【AI 名师点评】\n{llm_text}")

            except Exception as e:
                del self.user_sessions[user_id]
                yield event.plain_result(f"⚠️ 无法调用AI，主观题参考答案为：\n{item.get('answer')}")

    @filter.command("解析")
    async def llm_explain(self, event: AstrMessageEvent):
        last_q = self.user_progress.get("last_question")
        if not last_q:
            yield event.plain_result("🤔 缓存中没有最近做的题目。")
            return

        q_data = last_q["question_data"]
        yield event.plain_result("⏳ AI名师正在奋力解析中，请稍候...")
        try:
            provider_id = await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)
            prompt = f"""你是一位高考{last_q['subject']}名师。请对以下高考真题进行深度解析。

【题目】{q_data.get('question')}
【答案】{q_data.get('answer')}
【官方解析】{q_data.get('analysis', '无')}

请按以下结构详细讲解（尽量用通俗易懂的方式）：
1. 📚 核心考点：本题考查了什么知识？
2. 💡 解题思路：详细的步骤推导和逻辑突破口。
3. ⚠️ 易错提醒：很多同学会踩什么坑？
4. 🔗 举一反三：还有哪些相似变体？
"""
            llm_res = await self.context.llm_generate(chat_provider_id=provider_id, prompt=prompt)
            
            if self.cfg_render:
                url = await self.render_question_html(q_data, include_answer=True, additional_text=f"【AI 深度解析】\n{llm_res.completion_text}")
                if url:
                    yield event.image_result(url)
                    return
                    
            yield event.plain_result(f"🤖 【AI 深度解析】\n{llm_res.completion_text}")
        except Exception as e:
            yield event.plain_result("⚠️ 调用AI解析失败，请检查模型配置。")

    @filter.command("知识点")
    async def knowledge_explain(self, event: AstrMessageEvent, topic: str = ""):
        if not topic:
            yield event.plain_result("⚠️ 请提供要查询的知识点，例如：/知识点 椭圆标准方程")
            return
            
        subject = self.user_scores.get("current_subject", "未知")
        yield event.plain_result(f"⏳ 正在整理【{topic}】知识网络...")
        try:
            provider_id = await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)
            prompt = f"""作为{subject}特级教师，请系统讲解知识点：【{topic}】
要求包含：
- 定义与核心公式
- 常见考察题型与方法
- 易错点与注意事项
- 一个简明的示例"""
            llm_res = await self.context.llm_generate(chat_provider_id=provider_id, prompt=prompt)
            yield event.plain_result(f"📘 【{topic} 知识梳理】\n{llm_res.completion_text}")
        except Exception as e:
             yield event.plain_result("⚠️ 生成知识点失败。")

    @filter.command("错题本")
    async def wrong_book_stats(self, event: AstrMessageEvent):
        wb = self.user_progress.get("wrong_book", {})
        if not wb:
            yield event.plain_result("🎉 你的错题本是空的！继续保持！")
            return
            
        stats = {}
        for qid, data in wb.items():
            sub = data.get("subject", "其他")
            stats[sub] = stats.get(sub, 0) + 1
            
        reply = "📒【我的错题本】\n"
        for sub, count in stats.items():
            reply += f" ▫️ {sub}: {count} 题\n"
        reply += "\n💡 发送 /每日打卡 可以复习到期的错题哦！"
        yield event.plain_result(reply)

    @filter.command("我的成绩")
    async def my_scores(self, event: AstrMessageEvent):
        subjects = self.user_scores.get("subjects", {})
        if not subjects:
            yield event.plain_result("🤷 目前还没有做题记录，快去 /刷题 吧！")
            return
            
        reply = "📊 【 高考备考成绩单 】\n" + "=" * 25 + "\n"
        best_acc = 0
        best_sub = "无"
        
        for subj, data in subjects.items():
            total = data.get("total_done", 0)
            correct = data.get("total_correct", 0)
            if total == 0: continue
            acc = correct / total
            if total >= 5 and acc > best_acc:
                best_acc = acc
                best_sub = subj
                
            acc_str = f"{acc*100:.1f}%"
            # 简单的能力槽
            bar = "█" * int(acc*10) + "░" * (10 - int(acc*10))
            reply += f"📘 {subj}: {bar} {acc_str} ({correct}/{total})\n"

        overall = self.user_scores.get("overall", {})
        o_t = overall.get("total_done", 0)
        o_c = overall.get("total_correct", 0)
        
        reply += "=" * 25 + "\n"
        reply += f"📈 累计做题：{o_t} 题\n"
        reply += f"✨ 综合正确率：{o_c/o_t*100:.1f}%" if o_t > 0 else "✨ 综合正确率：0%"
        reply += f"\n🏆 优势科目：{best_sub} (需刷5题以上)"
        yield event.plain_result(reply)

    @filter.command("每日打卡")
    async def daily_review(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        wb = self.user_progress.get("wrong_book", {})
        now = time.time()
        
        due_items = [v for k, v in wb.items() if now >= v.get("next_review", 0)]
        if not due_items:
            yield event.plain_result("🎈 今天没有需要复习的错题，干得漂亮！可以去刷点新题。")
            return
            
        item = due_items[0]["question"]
        subject = due_items[0]["subject"]
        self.user_sessions[user_id] = {
            "question": item,
            "subject": subject,
            "time": time.time(),
            "is_review": True
        }
        
        reply = f"⏰【复习打卡】待复习错题: {len(due_items)} 道\n"
        if self.cfg_render:
            url = await self.render_question_html(item, include_answer=False, additional_text=f"📌 这是一道你需要复习的错题！")
            if url:
                yield event.plain_result(reply)
                yield event.image_result(url)
                return
                
        reply += f"📝 【{subject}】\n{item.get('question')}\n👉 请回复 /答 您的答案"
        yield event.plain_result(reply)

    async def daily_push_task(self):
        while True:
            # Simple daily reminder check
            await asyncio.sleep(3600)
