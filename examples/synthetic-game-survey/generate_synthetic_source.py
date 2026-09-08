#!/usr/bin/env python3
"""Generate deterministic, de-identified game-survey data for the repository example."""

import json
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path


SEED = 8122026
VALID_N = 180


def option(index, title):
    return {"item_index": index, "item_title": title}


def clamp_score(value, low=1, high=5):
    return max(low, min(high, int(math.floor(value + 0.5))))


def weighted_choice(rng, values, weights):
    draw = rng.random() * sum(weights)
    running = 0.0
    for value, weight in zip(values, weights):
        running += weight
        if draw <= running:
            return value
    return values[-1]


def survey_definition():
    scale_satisfaction = [
        option(1, "很不满意"), option(2, "不满意"), option(3, "一般"),
        option(4, "满意"), option(5, "非常满意"),
    ]
    scale_ease = [
        option(1, "非常难"), option(2, "比较难"), option(3, "一般"),
        option(4, "比较容易"), option(5, "非常容易"),
    ]
    scale_continue = [
        option(1, "一定不会"), option(2, "可能不会"), option(3, "不确定"),
        option(4, "可能会"), option(5, "一定会"),
    ]
    matrix_scale = [
        option(1, "很差"), option(2, "较差"), option(3, "一般"),
        option(4, "较好"), option(5, "很好"),
    ]
    return {
        "title": "《星港计划》概念测试体验问卷（合成案例）",
        "vid": "DEMO-GAME-001",
        "answer_total": 192,
        "questions": [
            {"q_index": 1, "q_title": "本次测试主要使用的平台是？", "q_type": 3, "q_subtype": 3,
             "items": [option(1, "移动端"), option(2, "PC/主机")]},
            {"q_index": 2, "q_title": "以下哪类游戏经验最符合你？", "q_type": 3, "q_subtype": 3,
             "items": [option(1, "横版动作核心"), option(2, "二游ARPG"), option(3, "银河恶魔城"), option(4, "泛用户")]},
            {"q_index": 3, "q_title": "你对本次测试的整体满意度如何？", "q_type": 3, "q_subtype": 3, "items": scale_satisfaction},
            {"q_index": 4, "q_title": "你认为游戏是否容易上手？", "q_type": 3, "q_subtype": 3, "items": scale_ease},
            {"q_index": 5, "q_title": "正式上线后，你继续游玩的意愿如何？", "q_type": 3, "q_subtype": 3, "items": scale_continue},
            {"q_index": 6, "q_title": "本次体验中，你认为做得较好的部分有哪些？", "q_type": 4, "q_subtype": 4,
             "items": [option(1, "战斗手感"), option(2, "美术表现"), option(3, "角色设计"), option(4, "世界探索"), option(5, "剧情设定"), option(6, "社交体验"), option(7, "其他")]},
            {"q_index": 7, "q_title": "请评价以下体验模块。", "q_type": 7, "q_subtype": 7,
             "items": matrix_scale,
             "item_rows": [option(1, "战斗反馈"), option(2, "关卡节奏"), option(3, "视觉表现")]},
            {"q_index": 8, "q_title": "你有多大可能向朋友推荐这款游戏？", "q_type": 3, "q_subtype": 302,
             "items": [option(index + 1, str(index)) for index in range(11)]},
            {"q_index": 9, "q_title": "请选出最希望优先优化的三项并排序。", "q_type": 4, "q_subtype": 402,
             "items": [option(1, "新手引导"), option(2, "战斗反馈"), option(3, "关卡节奏"), option(4, "剧情演出"), option(5, "性能优化")]},
            {"q_index": 10, "q_title": "你对后续优化还有哪些建议？", "q_type": 5, "q_subtype": 1, "items": []},
        ],
    }


def add_single(answers, key, question, value, item_value=None):
    answers[key] = {
        "q_index": question,
        "q_column": 0,
        "item_index": [value],
        "item_value": str(value if item_value is None else item_value),
    }


def generate_records():
    rng = random.Random(SEED)
    records = []
    experience_effect = {1: 0.70, 2: 0.28, 3: 0.12, 4: -0.38}
    start = datetime(2026, 9, 1, 10, 0, 0)

    for respondent in range(1, VALID_N + 1):
        experience = weighted_choice(rng, [1, 2, 3, 4], [30, 28, 20, 22])
        pc_probability = {1: 0.44, 2: 0.32, 3: 0.72, 4: 0.36}[experience]
        platform = 2 if rng.random() < pc_probability else 1
        platform_effect = 0.10 if platform == 2 else 0.0

        satisfaction = clamp_score(3.08 + experience_effect[experience] + platform_effect + rng.gauss(0, 0.78))
        ease = clamp_score(3.03 + (0.48 if experience == 1 else 0.0) + (0.16 if platform == 1 else -0.04) + rng.gauss(0, 0.82))
        continue_score = clamp_score(2.82 + 0.56 * (satisfaction - 3) + (0.22 if experience == 1 else 0.0) + 0.12 * (ease - 3) + rng.gauss(0, 0.74))

        answers = {}
        add_single(answers, "q1", 1, platform)
        add_single(answers, "q2", 2, experience)
        add_single(answers, "q3", 3, satisfaction)
        if respondent % 29 != 0:
            add_single(answers, "q4", 4, ease)
        add_single(answers, "q5", 5, continue_score)

        probabilities = {
            1: 0.30 + (0.35 if experience == 1 else 0.0) + 0.06 * (satisfaction - 3),
            2: 0.44 + 0.05 * (satisfaction - 3),
            3: 0.39 + (0.13 if experience == 2 else 0.0),
            4: 0.24 + (0.23 if experience == 3 else 0.0),
            5: 0.27 + 0.04 * (satisfaction - 3),
            6: 0.11 + (0.09 if platform == 1 else 0.0),
            7: 0.04,
        }
        selected = [item for item, probability in probabilities.items() if rng.random() < max(0.02, min(0.90, probability))]
        if not selected:
            selected = [2]
        answers["q6"] = {"q_index": 6, "q_column": 0, "item_index": selected, "item_value": ""}

        matrix_scores = {
            1: clamp_score(satisfaction + (0.42 if experience == 1 else 0.0) + rng.gauss(0, 0.70)),
            2: clamp_score(satisfaction + (0.26 if experience == 3 else 0.0) + rng.gauss(0, 0.72)),
            3: clamp_score(satisfaction + 0.18 + rng.gauss(0, 0.66)),
        }
        for row_index, score in matrix_scores.items():
            answers[f"q7r{row_index}"] = {
                "q_index": 7, "q_column": 0, "q_row": row_index,
                "item_index": [score], "item_value": str(score),
            }

        nps = None
        if respondent % 31 != 0:
            nps_center = {1: 3.0, 2: 5.0, 3: 7.0, 4: 8.4, 5: 9.5}[satisfaction]
            nps = max(0, min(10, int(math.floor(nps_center + (0.30 if experience == 1 else 0.0) + rng.gauss(0, 1.12) + 0.5))))
            add_single(answers, "q8", 8, nps + 1, nps)

        priorities = {
            1: (6 - ease) * 1.25 + (0.7 if experience == 4 else 0.0) + rng.random(),
            2: (6 - matrix_scores[1]) * 1.15 + (0.5 if experience == 1 else 0.0) + rng.random(),
            3: (6 - matrix_scores[2]) * 1.10 + rng.random(),
            4: (6 - satisfaction) * 0.85 + rng.random() * 1.3,
            5: (0.65 if platform == 2 else 0.25) + rng.random() * 2.2,
        }
        ranked = sorted(priorities, key=lambda item: (-priorities[item], item))[:3]
        for position, item_index in enumerate(ranked, start=1):
            answers[f"q9p{position}"] = {
                "q_index": 9, "q_column": position,
                "item_index": [item_index], "item_value": str(position),
            }

        if rng.random() < 0.66:
            comments = [
                "希望优化新手引导与操作提示。",
                "希望进一步提升战斗反馈。",
                "希望改善部分关卡节奏。",
                "希望增加剧情演出的完整度。",
                "希望继续优化性能与发热表现。",
            ]
            comment_index = max(priorities, key=priorities.get) - 1
            answers["q10"] = {
                "q_index": 10, "q_column": 0, "item_index": [],
                "item_value": "", "answer_text": comments[comment_index], "answered": True,
            }

        records.append({
            "respondent_id": f"SYN-{respondent:04d}",
            "submit_time": (start + timedelta(minutes=respondent * 7)).isoformat(sep=" "),
            "answer_seconds": 360 + int(rng.random() * 540),
            "answer_items": answers,
        })
    return records


def main(output_dir):
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    survey = survey_definition()
    records = generate_records()
    receipt = {
        "source_type": "synthetic_example",
        "source_note": "仓库内合成演示数据，不来自真实问卷星账号",
        "vid": survey["vid"],
        "answer_total": survey["answer_total"],
        "answer_valid": len(records),
        "records_written": len(records),
        "seed": SEED,
        "deidentified": True,
        "fields_removed": ["IP", "设备标识", "外部联系方式"],
    }
    (destination / "survey.json").write_text(json.dumps(survey, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "responses.deidentified.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "fetch-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(destination), "records": len(records), "seed": SEED}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: generate_synthetic_source.py <output_dir>")
    main(sys.argv[1])
