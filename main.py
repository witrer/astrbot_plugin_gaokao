import os
import json
import random
import time
from astrbot.api.all import *
from astrbot.api.event import filter  # 🚨 修复1：显式导入 filter
from astrbot.api import logger        # 🚨 修复1：使用官方规范的日志器

@register("cet6_tutor", "YourName", "四六级金牌私教", "1.0.0")
class CET6Tutor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.questions = []
        self.answers = {}
        self.user_sessions = {}       # 用户的答题状态
        self.vocab_random_list = []
        self.vocab_fast_dict = {}     # 🚨 修复4：GLaDOS 要求的极速 O(1) 单词哈希表
        
        self.load_data()

    def cleanup_sessions(self):
        """🚨 修复3：Gordon Ramsay 要求的内存清理，清空 2 小时前的僵尸会话"""
        now = time.time()
        # 找出超时（超过 7200 秒即 2 小时）的用户
        expired_users = [uid for uid, data in self.user_sessions.items() if now - data["time"] > 7200]
        for uid in expired_users:
            del self.user_sessions[uid]

    def load_data(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        q_path = os.path.join(current_dir, 'CET6_Perfect_Verified.json')
        a_path = os.path.join(current_dir, 'CET6_Answer.json')
        txt_path = os.path.join(current_dir, '4 六级-乱序.txt')
        json_path = os.path.join(current_dir, '4-CET6-顺序.json')
        
        # 🚨 修复5：精准的异常捕获，不再掩耳盗铃
        # 1. 加载阅读和答案
        try:
            with open(q_path, 'r', encoding='utf-8') as f:
                self.questions = json.load(f)
            with open(a_path, 'r', encoding='utf-8') as f:
                self.answers = json.load(f)
            logger.info(f"[CET6 Tutor] 成功加载 {len(self.questions)} 篇阅读真题！") # 替代 print
        except FileNotFoundError as e:
            logger.error(f"[CET6 Tutor] 找不到阅读数据文件：{e}")
        except json.JSONDecodeError as e:
            logger.error(f"[CET6 Tutor] 阅读 JSON 格式损坏：{e}")

        # 2. 加载单词表并构建 O(1) 极速哈希表
        try:
            if os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8') as f:
                    self.vocab_random_list = [line.strip() for line in f if line.strip()]
                logger.info(f"[CET6 Tutor] 成功加载 {len(self.vocab_random_list)} 个乱序单词！")
                
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    raw_vocab = json.load(f)
                    
                # 核心提速逻辑：在启动时直接将 JSON 拍平为字典
                if isinstance(raw_vocab, dict):
                    for k, v in raw_vocab.items():
                        self.vocab_fast_dict[k.lower()] = json.dumps(v, ensure_ascii=False, indent=2) if isinstance(v, (dict, list)) else str(v)
                elif isinstance(raw_vocab, list):
                    for item in raw_vocab:
                        if isinstance(item, dict):
                            # 把字典里所有的英文字母字符串都作为可能被查询的 key
                            for val in item.values():
                                val_str = str(val).lower().strip()
                                if val_str.isalpha():
                                    self.vocab_fast_dict[val_str] = json.dumps(item, ensure_ascii=False, indent=2)
                                    
                logger.info(f"[CET6 Tutor] 成功构建极速 O(1) 单词哈希表，词汇量：{len(self.vocab_fast_dict)}")
        except FileNotFoundError as e:
            logger.error(f"[CET6 Tutor] 找不到单词数据文件：{e}")
        except json.JSONDecodeError as e:
            logger.error(f"[CET6 Tutor] 单词 JSON 格式损坏：{e}")

    def get_answer_key(self, meta, sec_type):
        year = meta.get('year', '')
        month = meta.get('month', '')
        set_idx = meta.get('set_index', '1')
        
        matched_paper_id = None
        for paper_id in self.answers.keys():
            if year in paper_id and month in paper_id and str(set_idx) in paper_id:
                matched_paper_id = paper_id
                break
                
        if not matched_paper_id: return None
            
        ans_dict = self.answers[matched_paper_id].get('answers', {})
        raw_ans = ""
        expected_len = 0
        
        if "Section A" in sec_type:
            raw_ans, expected_len = ans_dict.get("Section A", ""), 10
        elif "Section B" in sec_type:
            raw_ans, expected_len = ans_dict.get("Section B", ""), 10
        elif "Passage 1" in sec_type or "C1" in sec_type:
            raw_ans, expected_len = ans_dict.get("Section C1", ""), 5
        elif "Passage 2" in sec_type or "C2" in sec_type:
            raw_ans, expected_len = ans_dict.get("Section C2", ""), 5
            
        if not raw_ans: return None
        clean_ans = "".join([char for char in raw_ans if char.isalpha()])
        return clean_ans[:expected_len]

    @filter.command("来篇阅读")
    async def draw_question(self, event: AstrMessageEvent):
        if not self.questions:
            yield event.plain_result("⚠️ 阅读题库未加载，请检查后台日志。")
            return

        # 每次有人抽题，顺手清理一下过期的僵尸内存
        self.cleanup_sessions()

        item = random.choice(self.questions)
        meta = item['meta']
        sec_type = item['type']
        
        correct_ans = self.get_answer_key(meta, sec_type)
        if not correct_ans:
            yield event.plain_result(f"⚠️ 抽到了 {meta.get('year')}年 {sec_type}，但这题暂时没答案，重抽一次吧！")
            return

        user_id = event.get_sender_id()
        self.user_sessions[user_id] = {
            "correct_ans": correct_ans,
            "sec_type": sec_type,
            "meta": meta,
            "time": time.time()  # 🚨 修复3：加入时间戳防内存泄漏
        }

        reply = f"📜 考卷锁定: {meta.get('year')}年 {meta.get('month')}月 第{meta.get('set_index')}套 | {sec_type}\n"
        reply += "=" * 25 + "\n"
        # 🚨 修复2：解决 Linus 骂的重复拼接问题，一次性输出全文
        reply += item['content'] 
        reply += f"\n\n💡 提示：本题共 {len(correct_ans)} 道题。\n👉 做完请回复：/答案 ABCD"
        
        yield event.plain_result(reply)

    @filter.command("答案")
    async def grade_question(self, event: AstrMessageEvent, user_ans: str):
        user_id = event.get_sender_id()
        self.cleanup_sessions() # 清理内存
        
        if user_id not in self.user_sessions:
            yield event.plain_result("🤔 你还没抽阅读题（或者会话已超时被清理），先发 '/来篇阅读' 吧！")
            return
            
        session = self.user_sessions[user_id]
        correct_ans = session["correct_ans"]
        sec_type = session["sec_type"]
        
        user_ans = user_ans.upper().replace(" ", "")
        correct_ans = correct_ans.upper()
        
        start_num = 26 if "A" in sec_type else (36 if "B" in sec_type else (46 if "1" in sec_type else 51))
        
        score = 0
        results = []
        for i in range(len(correct_ans)):
            u = user_ans[i] if i < len(user_ans) else "_"
            c = correct_ans[i]
            q_num = start_num + i
            if u == c:
                score += 1
                results.append(f"第 {q_num} 题: ✅")
            else:
                results.append(f"第 {q_num} 题: ❌ (你的:{u} -> 正确:{c})")
                
        reply = f"📊 【 批改报告 】 得分: {score} / {len(correct_ans)}\n"
        reply += "-" * 20 + "\n"
        reply += "\n".join(results)
        reply += "\n" + "-" * 20 + "\n继续加油！想再做一篇请发送 '/来篇阅读'。"
        
        del self.user_sessions[user_id]
        yield event.plain_result(reply)

    @filter.command("抽单词")
    async def random_vocab(self, event: AstrMessageEvent):
        if not self.vocab_random_list:
            yield event.plain_result("⚠️ 乱序单词表未加载，请联系管理员检查数据。")
            return
            
        words = random.sample(self.vocab_random_list, min(5, len(self.vocab_random_list)))
        reply = "🔥 【 单 词 闪 测 】 🔥\n"
        reply += "=" * 20 + "\n"
        for i, w in enumerate(words):
            reply += f"{i+1}. {w}\n"
        reply += "=" * 20 + "\n"
        reply += "👉 认识几个？在心里默写，或者大声读出来！"
        
        yield event.plain_result(reply)

    @filter.command("查单词")
    async def search_vocab(self, event: AstrMessageEvent, target_word: str):
        if not self.vocab_fast_dict:
            yield event.plain_result("⚠️ 顺序词库未加载，请联系管理员。")
            return
            
        target_word = target_word.strip().lower()
        
        # 🚨 修复4：极速 O(1) 哈希表直接定位，彻底干掉暴力遍历！
        if target_word in self.vocab_fast_dict:
            found_info = self.vocab_fast_dict[target_word]
            yield event.plain_result(f"📖 【 {target_word} 】的查询结果：\n{found_info}")
        else:
            yield event.plain_result(f"🙈 翻遍了词库，没找到 '{target_word}' 的详细记录哦。")
