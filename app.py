import os
import requests
import html  # для экранирования спецсимволов в комбинированном коде

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"  # пример URL [web:209][web:206]


def call_yandex_optimize(code: str, language: str, goal: str, context: str) -> tuple[str, str, list[str]]:
    # исходный код
    original_code = code

    # простая демонстрационная "оптимизация"
    lines_raw = original_code.split("\n")
    cleaned = [ln for ln in lines_raw if ln.strip() != "" or ln.strip().startswith("//")]
    optimized_code = "\n".join(cleaned)

    # экранированный комбинированный код
    safe_orig = html.escape(original_code)
    safe_opt = html.escape(optimized_code)

    # пока без <del>/<ins>, можно указать как future work
    annotated = safe_opt

    comments = [
        f"Контекст задачи (кратко): {context[:120]}..." if context else "Контекст задачи не задан.",
        "Применена базовая очистка: удалены лишние пустые строки.",
        f"Режим оптимизации: {goal}, язык: {language}."
    ]
    return optimized_code, annotated, comments



@app.route("/api/optimize", methods=["POST"])
def optimize():
    data = request.get_json()
    user_code = data.get("code", "")
    language = data.get("language", "cpp")
    goal = data.get("goal", "readability")
    context = data.get("context", "")

    optimized_code, annotated_code, comments = call_yandex_optimize(
        user_code, language, goal, context
    )

    return jsonify({
        "optimized_code": optimized_code,
        "annotated_code": annotated_code,
        "comments": comments
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
