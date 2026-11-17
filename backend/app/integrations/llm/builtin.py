"""内置确定性生成器。

不依赖外网与模型密钥，按固定模板产出三稿候选与评分，保证演示环境在
断网时仍能完整走通"多稿生成 → 逐稿评分 → 择优"的流程。
"""

from typing import Any

from app.core.timeutil import today_compact
from app.integrations.llm.base import Draft

_ANGLES = ["教学环节", "实践任务", "研讨活动", "项目驱动", "案例分析", "反思总结"]

_ALL_TAGS = [
    "科技自立自强", "自主创新", "科技报国", "攻坚克难", "团结协作", "严谨求实",
    "工匠精神", "家国情怀", "责任担当", "国际合作", "人民至上", "创新驱动发展",
    "文化自信", "诚实守信", "法治精神", "生态文明", "艰苦奋斗", "开拓进取",
]


def _build_case(
    ideological: str,
    knowledge: str,
    profession: list[str],
    variant: int,
) -> dict[str, Any]:
    """按变体生成一稿完整案例字段。"""
    profession_name = profession[0] if profession else "相关专业"
    angle = _ANGLES[variant % len(_ANGLES)]
    paragraph_count = max(2, 4 + (variant - 1))

    paragraphs = [
        f'在第{index}阶段，围绕“{knowledge}”这一主题，教学团队以{angle}为载体，'
        f'将专业知识点与“{ideological}”有机融合，设计递进式教学环节，'
        "引导学生在分析问题、解决问题的过程中内化价值认同，"
        "实现知识传授与价值塑造的同向同行。"
        for index in range(1, paragraph_count + 1)
    ]

    extra_tags = [tag for tag in _ALL_TAGS if tag != ideological][:2]

    return {
        "id": f"case_{1000 + variant}",
        "title": f'基于“{ideological}”的{profession_name}教学案例',
        "source": "AI生成",
        "sourceType": "AI生成",
        "source_url": "",
        "publish_date": today_compact(),
        "collect_date": today_compact(),
        "version": "V1.0",
        "category": "行业案例",
        "review_status": "草稿",
        "background": (
            f"本案例面向{profession_name}领域，聚焦专业知识点“{knowledge}”，"
            "结合当前经济社会发展中的鲜活实践，挖掘其中蕴含的思政元素，"
            "使专业教学与价值引领深度融合。"
        ),
        "content": "https://case.example.com/files/generated.pdf",
        "process": "\n".join(paragraphs),
        "result": (
            f"通过本案例教学，学生能够运用专业知识分析现实问题，"
            f'深化对“{ideological}”的理解与认同，达到“润物细无声”的育人效果。'
        ),
        "profession": profession or ["软件工程"],
        "keywords": [knowledge, "课程思政", "教学案例"],
        "professional_knowledge": [knowledge],
        "ideological_elements": [ideological, *extra_tags],
        "teaching_value": (
            f"适用于{profession_name}等相关专业课程。结合“{knowledge}”知识点，"
            f"引导学生思考{ideological}的时代价值与实践路径，发挥课程思政育人作用。"
        ),
    }


def _evaluate(case: dict[str, Any], variant: int) -> dict[str, Any]:
    """按四个维度给候选稿打分。"""
    dimensions = [
        {"name": "思政相关性", "score": 80 + ((variant * 7) % 18)},
        {"name": "内容质量", "score": 78 + ((variant * 11) % 20)},
        {"name": "结构完整", "score": 82 + ((variant * 5) % 15)},
        {"name": "语言表达", "score": 76 + ((variant * 13) % 22)},
    ]
    total_score = round(sum(item["score"] for item in dimensions) / len(dimensions))
    knowledge = (case.get("professional_knowledge") or ["专业知识点"])[0]
    return {
        "totalScore": total_score,
        "dimensions": dimensions,
        "suggestions": [
            "建议补充原文来源链接，增强可追溯性。",
            f"可进一步结合“{knowledge}”细化实施过程。",
            "教学价值部分可补充具体课程与学情说明。",
        ],
        "issue": "整体质量良好" if total_score >= 88 else "部分字段可进一步充实",
    }


def generate(
    ideological: str,
    knowledge: str,
    profession: list[str],
) -> list[Draft]:
    """产出三稿候选，并逐稿评分。"""
    drafts: list[Draft] = []
    for variant in range(3):
        case = _build_case(ideological, knowledge, profession, variant)
        drafts.append(Draft(case=case, evaluation=_evaluate(case, variant)))
    return drafts


def ask(case_context: dict[str, Any], question: str) -> str:
    """基于案例上下文生成确定性回答。"""
    title = case_context.get("title") or "该案例"
    background = case_context.get("background") or "（暂无背景信息）"
    process = case_context.get("process") or "（暂无过程信息）"
    result = case_context.get("result") or "（暂无结果信息）"
    ideological = "、".join(case_context.get("ideological_elements") or []) or "无"
    knowledge = "、".join(case_context.get("professional_knowledge") or []) or "无"
    teaching_value = case_context.get("teaching_value") or "无"

    return "\n".join(
        [
            f"关于「{title}」的解答：",
            "",
            f"案例背景：{background}",
            "",
            f"实施过程要点：{process}",
            "",
            f"最终成效：{result}",
            "",
            f'针对您的问题“{question}”，建议结合思政元素（{ideological}）'
            f"与专业知识点（{knowledge}）思考，并参考教学价值（{teaching_value}）"
            "进行延伸分析。",
        ]
    )
