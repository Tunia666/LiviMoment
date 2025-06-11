from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import random
import json
from pathlib import Path
from langchain_gigachat import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage

@dataclass
class TaskPart:
    title: str
    description: str
    steps: List[str]
    requirements: Optional[List[str]] = None
    input_output: Optional[List[Dict[str, Any]]] = None

@dataclass
class Task:
    number: int
    title: str
    description: str
    parts: List[TaskPart]
    requirements: Optional[List[str]] = None
    input_output: Optional[List[Dict[str, Any]]] = None

class TaskGenerator:
    def __init__(self):
        API_KEY = "ZjY3YjU3YzYtYzM5OS00NzAyLThjMDMtYTRlNTIzM2ZiNzE4OjQ4OGRkNjg0LWExNzItNGQ1MC1iOTIzLWI5YWM5ZDlkM2I1OQ=="
        self.llm = GigaChat(credentials=API_KEY, verify_ssl_certs=False)
        self.system_prompt = SystemMessage(content="""
Ты — помощник-преподаватель по программированию на Python. Твоя задача — генерировать задания для студентов.
Задание должно быть в формате JSON:
{
    "title": "Название задания",
    "description": "Подробное описание задания",
    "requirements": ["список требований"],
    "examples": [
        {
            "input": "пример входных данных",
            "output": "пример выходных данных"
        }
    ],
    "steps": ["шаги выполнения"]
}
Задание должно быть:
1. Соответствовать теме урока
2. Иметь четкие требования
3. Включать конкретные примеры входных и выходных данных
4. Содержать пошаговые инструкции
5. Быть выполнимым за время занятия
""")

    def generate_task_with_llm(self, topic: str) -> dict:
        """Generate a task using GigaChat API based on the lesson topic"""
        prompt = f"""
Сгенерируй задание по теме: {topic}

Задание должно быть в формате JSON:
{{
    "title": "Название задания",
    "description": "Подробное описание задания",
    "requirements": ["список требований"],
    "examples": [
        {{
            "input": "пример входных данных",
            "output": "пример выходных данных"
        }}
    ],
    "steps": ["шаги выполнения"]
}}

Важно:
1. Задание должно быть связано с темой урока
2. Должны быть конкретные примеры входных и выходных данных
3. Требования должны быть четкими и выполнимыми
4. Шаги должны быть понятными и последовательными
"""
        messages = [self.system_prompt, HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        
        try:
            task_data = json.loads(response.content)
            return task_data
        except Exception as e:
            print(f"Error parsing task data: {e}")
            # Return a default task if parsing fails
            return {
                "title": f"Задание по теме: {topic}",
                "description": "Создать программу, демонстрирующую понимание темы",
                "requirements": [
                    "Создать отдельный файл для решения",
                    "Добавить документацию",
                    "Протестировать на различных входных данных",
                    "Следовать PEP 8"
                ],
                "examples": [
                    {
                        "input": "Пример входных данных",
                        "output": "Пример выходных данных"
                    }
                ],
                "steps": [
                    "Создать новый файл с расширением .py",
                    "Написать необходимый код",
                    "Протестировать программу",
                    "Убедиться в корректности работы"
                ]
            }

    def generate_task_for_lesson(self, lesson: dict) -> dict:
        """Generate a task based on the lesson topic using GigaChat API"""
        topic = lesson["topic"]
        return self.generate_task_with_llm(topic)

    def generate_test_for_lesson(self, lesson: dict, num_questions: int = 5) -> dict:
        """Generate a test based on the lesson topic using GigaChat API"""
        topic = lesson.get('topic', 'Python')
        prompt = (
            f"Сгенерируй тест из {num_questions} вопросов по теме: {topic}.\n"
            "Каждый вопрос должен иметь 4 варианта ответа, только один из которых правильный.\n"
            "Верни результат в формате JSON:\n"
            "{\n"
            "  \"questions\": [\n"
            "    {\"q\": \"Вопрос?\", \"a\": [\"Вариант1\", \"Вариант2\", \"Вариант3\", \"Вариант4\"], \"correct\": 0},\n"
            "    ...\n"
            "  ]\n"
            "}\n"
        )
        messages = [self.system_prompt, HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        try:
            data = json.loads(response.content)
            if "questions" in data:
                return data
        except Exception:
            pass
        return {"questions": []} 