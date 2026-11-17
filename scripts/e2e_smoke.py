"""端到端冒烟：登录 → 检索 → AI 生成 → 提交审核 → 审核发布 → 学生可检索 → 问答。

运行前请先启动后端：
    cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000
然后：
    backend/.venv/Scripts/python scripts/e2e_smoke.py
"""

import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def login(client: httpx.Client, username: str) -> str:
    response = client.post(
        f"{BASE}/auth/login",
        json={"username": username, "password": "123456"},
    )
    response.raise_for_status()
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]["token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    with httpx.Client(timeout=60) as client:
        student = login(client, "student01")
        teacher = login(client, "teacher01")
        admin = login(client, "admin01")

        cases = client.get(f"{BASE}/cases", params={"size": 2}).json()
        assert cases["data"]["records"], cases

        with client.stream(
            "POST",
            f"{BASE}/ai/generate",
            headers=headers(teacher),
            json={
                "ideological": "科技报国",
                "knowledge": "系统工程",
                "profession": ["航空航天工程"],
            },
        ) as response:
            generated = "".join(response.iter_text())
        assert "event: done" in generated, generated[:200]

        created = client.post(
            f"{BASE}/cases",
            headers=headers(teacher),
            json={
                "title": "端到端冒烟案例",
                "category": "行业案例",
                "background": "冒烟测试背景",
            },
        ).json()
        assert created["code"] == 0, created
        case_id = created["data"]["id"]

        submitted = client.post(
            f"{BASE}/cases/{case_id}/submit",
            headers=headers(teacher),
        ).json()
        assert submitted["data"]["status"] == "待审核", submitted

        reviewed = client.post(
            f"{BASE}/admin/cases/{case_id}/review",
            headers=headers(admin),
            json={"status": "已发布", "opinion": ""},
        ).json()
        assert reviewed["code"] == 0, reviewed

        found = client.get(
            f"{BASE}/cases",
            params={"keyword": "端到端冒烟案例"},
        ).json()
        assert found["data"]["total"] >= 1, found

        with client.stream(
            "POST",
            f"{BASE}/ai/ask/case_001",
            headers=headers(student),
            json={"question": "这个案例的思政元素是什么？"},
        ) as response:
            answer = "".join(response.iter_text())
        assert "event: done" in answer, answer[:200]

        statistics = client.get(
            f"{BASE}/admin/statistics/home",
            headers=headers(admin),
        ).json()
        assert statistics["data"]["totalCases"] >= 12, statistics

        print("e2e smoke ok")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001  冒烟脚本需要打印失败原因
        print(f"e2e smoke failed: {exc}")
        sys.exit(1)
