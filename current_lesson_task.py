import json
from datetime import datetime, time
from task_generator import TaskGenerator

class LessonManager:
    def __init__(self, ktp_file: str):
        with open(ktp_file, 'r', encoding='utf-8') as f:
            self.ktp_data = json.load(f)
        self.task_generator = TaskGenerator()

    def get_current_lesson(self) -> dict:
        """Determine the current lesson based on date and time"""
        now = datetime.now()
        current_time = now.time()
        current_date = now.strftime("%Y-%m-%d")

        for lesson in self.ktp_data["lessons"]:
            lesson_date = lesson["date"]
            if lesson_date == current_date:
                start_time = datetime.strptime(lesson["start_time"], "%H:%M").time()
                end_time = datetime.strptime(lesson["end_time"], "%H:%M").time()
                
                if start_time <= current_time <= end_time:
                    return lesson
        
        # If no current lesson found, return the next upcoming lesson
        for lesson in self.ktp_data["lessons"]:
            lesson_date = lesson["date"]
            if lesson_date >= current_date:
                start_time = datetime.strptime(lesson["start_time"], "%H:%M").time()
                if lesson_date > current_date or start_time > current_time:
                    return lesson
        
        return None

    def generate_task_with_llm(self, lesson: dict) -> dict:
        """Generate a task based on the lesson topic using TaskGenerator"""
        return self.task_generator.generate_task_for_lesson(lesson)

def main():
    # Create lesson manager
    manager = LessonManager("ktp.json")
    
    # Get current lesson
    current_lesson = manager.get_current_lesson()
    
    if current_lesson:
        print("\nТекущее занятие:")
        print("=" * 50)
        print(f"Дата: {current_lesson['date']}")
        print(f"Время: {current_lesson['start_time']} - {current_lesson['end_time']}")
        print(f"Тема: {current_lesson['topic']}")
        print(f"Задание: {current_lesson['assignment']}")
        
        # Generate task
        print("\nСгенерированное задание:")
        print("=" * 50)
        task = manager.generate_task_with_llm(current_lesson)
        
        # Save the generated task
        with open("current_lesson_task.json", 'w', encoding='utf-8') as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        
        # Print the task
        print(f"\nЗадание: {task['title']}")
        print("=" * 50)
        print(task['description'])
        
        print("\nТребования:")
        for req in task['requirements']:
            print(f"- {req}")
        
        print("\nПримеры:")
        for example in task['examples']:
            print(f"Входные данные: {example['input']}")
            print(f"Выходные данные: {example['output']}")
            print()
        
        print("\nШаги выполнения:")
        for i, step in enumerate(task['steps'], 1):
            print(f"{i}. {step}")
    else:
        print("На данный момент нет активных занятий")

if __name__ == "__main__":
    main() 