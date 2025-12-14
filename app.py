import os
import requests
import html
import difflib

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


@app.route("/")
def index():
    return render_template("index.html")


def call_yandex(text: str, system_prompt: str) -> str:
    """Универсальный вызов YandexGPT, возвращает text-ответ."""
    iam_token = os.environ["YANDEXIAMTOKEN"]
    folder_id = os.environ["YANDEXFOLDERID"]

    body = {
        "modelUri": f"gpt://{folder_id}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": "2000"
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": text}
        ]
    }

    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json"
    }

    resp = requests.post(YANDEX_API_URL, headers=headers, json=body, timeout=60)
    if not resp.ok:
        print("Yandex error status:", resp.status_code, resp.text)
    resp.raise_for_status()
    data = resp.json()
    return data["result"]["alternatives"][0]["message"]["text"].strip()



def call_yandex_optimize(code: str, language: str, goal: str, context: str) -> tuple[str, str, list[str]]:
    # ---------- 1. Оптимизация кода ----------
    optimize_system_prompt = (
        "You are a competitive programming code assistant. "
        "Rewrite the user's code in a more idiomatic and concise way.\n"
        f"Language: {language}.\n"
        f"Optimization goal: {goal}.\n"
        "Strict requirements:\n"
        "- Return ONLY pure source code, no markdown, no triple backticks, no natural language comments.\n"
        "- For C++: prefer 'using namespace std;' if it simplifies cout/cin usage.\n"
        "- Remove unused variables, unnecessary includes and dead code.\n"
        "- Keep the same input/output behavior and overall algorithm.\n"
    )
    if context:
        optimize_system_prompt += f"\nTask description: {context}"

    optimized = call_yandex(code, optimize_system_prompt)

    # защита от ```cpp / ```
    if optimized.startswith("```"):
        txt = optimized.strip("`")
        if "\n" in txt:
            parts = txt.split("\n")
            # убираем первую строку с ``````
            optimized = "\n".join(parts[1:-1]).strip()
        else:
            optimized = txt

    # ---------- 2. diff через difflib ----------
    safe_orig = html.escape(code)
    safe_opt = html.escape(optimized)

    orig_lines_raw = safe_orig.split("\n")
    opt_lines_raw = safe_opt.split("\n")

    def normalize(line: str) -> str:
        # не подсвечиваем различия только из-за пробелов/пустых строк
        return "" if line.strip() == "" else line

    orig_lines = [normalize(l) for l in orig_lines_raw]
    opt_lines = [normalize(l) for l in opt_lines_raw]

    sm = difflib.SequenceMatcher(a=orig_lines, b=opt_lines)
    rows: list[str] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                line_num = i1 + k + 1
                text = orig_lines[i1 + k]
                rows.append(
                    f'<div class="diff-row">'
                    f'<span class="diff-line-num">{line_num}</span>'
                    f'<span class="diff-code orig">{text}</span>'
                    f'<span class="diff-code opt">{text}</span>'
                    f'</div>'
                )
        elif tag == "replace":
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                line_num = i1 + k + 1
                o = orig_lines[i1 + k] if i1 + k < i2 else ""
                n = opt_lines[j1 + k] if j1 + k < j2 else ""
                if o == "" and n == "":
                    continue
                rows.append(
                    f'<div class="diff-row">'
                    f'<span class="diff-line-num">{line_num}</span>'
                    f'<span class="diff-code orig diff-del">{o}</span>'
                    f'<span class="diff-code opt diff-add">{n}</span>'
                    f'</div>'
                )
        elif tag == "delete":
            for k in range(i2 - i1):
                line_num = i1 + k + 1
                o = orig_lines[i1 + k]
                if o == "":
                    continue
                rows.append(
                    f'<div class="diff-row">'
                    f'<span class="diff-line-num">{line_num}</span>'
                    f'<span class="diff-code orig diff-del">{o}</span>'
                    f'<span class="diff-code opt diff-add"></span>'
                    f'</div>'
                )
        elif tag == "insert":
            for k in range(j2 - j1):
                n = opt_lines[j1 + k]
                if n == "":
                    continue
                rows.append(
                    f'<div class="diff-row">'
                    f'<span class="diff-line-num">+</span>'
                    f'<span class="diff-code orig diff-del"></span>'
                    f'<span class="diff-code opt diff-add">{n}</span>'
                    f'</div>'
                )

    annotated = "\n".join(rows) if rows else (
        '<div class="diff-row"><span class="diff-line-num"></span>'
        '<span class="diff-code orig">No changes</span>'
        '<span class="diff-code opt"></span></div>'
    )

    # ---------- 3. Настоящие комментарии от ИИ ----------
    review_system_prompt = (
        "You are a senior C++/Python competitive programming mentor. "
        "You are given ORIGINAL code and OPTIMIZED code.\n"
        "Task: briefly explain the changes and their effect.\n"
        "Output format:\n"
        "- 3 to 5 bullet-style sentences.\n"
        "- Each sentence must be short and concrete.\n"
        "- Do not repeat the code, only describe what changed and why it is better.\n"
        "- Language of explanation: English."
    )

    review_input = (
        "<<ORIGINAL CODE>>\n"
        f"{code}\n"
        "<<OPTIMIZED CODE>>\n"
        f"{optimized}\n"
    )

    review_text = call_yandex(review_input, review_system_prompt)

    raw_lines = [ln.strip("-• \t") for ln in review_text.split("\n")]
    comments = [ln for ln in raw_lines if ln]

    if context:
        comments.insert(0, f"Task: {context[:120]}...")

    if not comments:
        comments = [f"Goal: {goal}, language: {language}."]

    return optimized, annotated, comments


@app.route("/api/optimize", methods=["POST"])
def optimize():
    # поддерживаем и JSON, и formData (на будущее)
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        user_code = request.form.get("code", "")
        language = request.form.get("language", "cpp")
        goal = request.form.get("goal", "readability")
        context = request.form.get("context", "")
    else:
        data = request.get_json() or {}
        user_code = data.get("code", "")
        language = data.get("language", "cpp")
        goal = data.get("goal", "readability")
        context = data.get("context", "")

    optimized_code, annotated_code, comments = call_yandex_optimize(
        user_code, language, goal, context
    )

    return jsonify(
        optimizedcode=optimized_code,
        annotatedcode=annotated_code,
        comments=comments,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
