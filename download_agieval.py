"""
下载 AGIEval 高考数据并转换为 GAOKAO-Bench 兼容格式。
来源: https://github.com/ruixiangcui/AGIEval

AGIEval 格式 (JSONL):
  {"passage": ..., "question": ..., "options": ["(A)...", "(B)..."], "label": "C", "answer": null, "other": {"source": "2021年浙江卷—数学"}}

GAOKAO-Bench 格式 (JSON):
  {"example": [{"index": 1, "year": "2021", "category": "浙江卷", "score": 5, "question": "...", "answer": ["C"], "analysis": ""}]}
"""
import os
import re
import json
import urllib.request

AGIEVAL_BASE = "https://raw.githubusercontent.com/ruixiangcui/AGIEval/main/data/v1"

# AGIEval 高考文件 -> 我们的科目映射
AGIEVAL_FILES = {
    "gaokao-mathqa.jsonl":    ("数学", "AGIEval_Math_MCQs"),
    "gaokao-mathcloze.jsonl": ("数学", "AGIEval_Math_Fill-in-the-Blank"),
    "gaokao-chinese.jsonl":   ("语文", "AGIEval_Chinese_MCQs"),
    "gaokao-english.jsonl":   ("英语", "AGIEval_English_MCQs"),
    "gaokao-physics.jsonl":   ("物理", "AGIEval_Physics_MCQs"),
    "gaokao-chemistry.jsonl": ("化学", "AGIEval_Chemistry_MCQs"),
    "gaokao-biology.jsonl":   ("生物", "AGIEval_Biology_MCQs"),
    "gaokao-geography.jsonl": ("地理", "AGIEval_Geography_MCQs"),
    "gaokao-history.jsonl":   ("历史", "AGIEval_History_MCQs"),
}

def parse_source(source_str):
    """从 source 字符串中提取年份和分类。
    例: '2021年浙江卷—数学' -> ('2021', '浙江卷')
         '2018年新课标Ⅰ—理综化学' -> ('2018', '新课标Ⅰ')
    """
    year_match = re.search(r"(\d{4})", source_str or "")
    year = year_match.group(1) if year_match else "未知"
    # 提取年份后、科目前的部分作为category
    cat = re.sub(r"\d{4}年", "", source_str or "")
    cat = re.sub(r"[—\-].*$", "", cat).strip()
    return year, cat

def build_question_text(passage, question, options):
    """把 passage + question + options 合并为完整的题目文本"""
    parts = []
    if passage:
        parts.append(str(passage))
    if question:
        parts.append(str(question))
    if options:
        parts.append("\n".join(str(o) for o in options))
    return "\n".join(parts)

def convert_agieval_to_gaokao(jsonl_lines, is_cloze=False):
    """将 AGIEval JSONL 行列表转换为 GAOKAO-Bench 格式的 example 列表"""
    examples = []
    for idx, line in enumerate(jsonl_lines, start=1):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue

        source = d.get("other", {}).get("source", "") if isinstance(d.get("other"), dict) else ""
        year, category = parse_source(source)

        question_text = build_question_text(d.get("passage"), d.get("question"), d.get("options"))

        # 答案处理
        label = d.get("label", "")
        if is_cloze:
            # 填空题: answer 可能存在真实答案
            answer_text = d.get("answer") or label or ""
            answer = [str(answer_text)]
            is_subjective = True
        else:
            # 选择题
            answer = [str(label)] if label else []
            is_subjective = False

        entry = {
            "index": 10000 + idx,  # 偏移 index 避免和 GAOKAO-Bench 原始数据冲突
            "year": year,
            "category": f"AGIEval-{category}" if category else "AGIEval",
            "score": 5,
            "question": question_text,
            "answer": answer,
            "analysis": "",
            "_source": f"AGIEval:{source}",
        }
        examples.append(entry)
    return examples

def download_and_convert():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    obj_dir = os.path.join(base_dir, "Data", "Objective_Questions")
    sub_dir = os.path.join(base_dir, "Data", "Subjective_Questions")
    os.makedirs(obj_dir, exist_ok=True)
    os.makedirs(sub_dir, exist_ok=True)

    total_questions = 0
    for remote_file, (subject, local_name) in AGIEVAL_FILES.items():
        url = f"{AGIEVAL_BASE}/{remote_file}"
        print(f"Downloading {remote_file}...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp:
                content = resp.read().decode("utf-8")
            lines = [l for l in content.strip().split("\n") if l.strip()]
            print(f"  Got {len(lines)} questions")

            is_cloze = "cloze" in remote_file.lower() or "Fill-in" in local_name
            examples = convert_agieval_to_gaokao(lines, is_cloze=is_cloze)

            # 填空题放主观题目录，选择题放客观题目录
            out_name = f"{local_name}.json"
            if is_cloze:
                out_path = os.path.join(sub_dir, out_name)
            else:
                out_path = os.path.join(obj_dir, out_name)

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"example": examples}, f, ensure_ascii=False, indent=2)
            print(f"  Saved {len(examples)} questions to {out_path}")
            total_questions += len(examples)

        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n✅ AGIEval 下载完成！共转换 {total_questions} 道题目")

if __name__ == "__main__":
    download_and_convert()
