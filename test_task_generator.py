from task_generator import TaskGenerator

def test_task_generation():
    # Create task generator
    generator = TaskGenerator()
    
    # Test lesson data
    lesson = {
        "date": "2025-06-11",
        "start_time": "09:00",
        "end_time": "10:35",
        "topic": "Обработка исключений. try, except, finally.",
        "assignment": "Написать программу, которая принимает число и выводит его квадрат, если оно положительное, и квадратный корень, если оно отрицательное."
    }
    
    # Generate task
    task = generator.generate_task_for_lesson(lesson)
    
    # Print the generated task
    print("\nСгенерированное задание:")
    print("=" * 50)
    print(f"Название: {task['title']}")
    print(f"\nОписание:\n{task['description']}")
    
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

if __name__ == "__main__":
    test_task_generation() 