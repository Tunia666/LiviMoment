import subprocess
import tempfile
import os

def check_solution(task, solution_code):
    check_results = []
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as tmp:
        tmp.write(solution_code)
        tmp_path = tmp.name
    for example in task.get('examples', []):
        input_data = example['input']
        expected_output = example['output']
        try:
            proc = subprocess.run(
                ['python3', tmp_path],
                input=input_data.encode('utf-8'),
                capture_output=True,
                timeout=5
            )
            actual_output = proc.stdout.decode('utf-8').strip()
            error_output = proc.stderr.decode('utf-8').strip()
            success = (actual_output == expected_output)
        except Exception as e:
            actual_output = str(e)
            error_output = ''
            success = False
        check_results.append({
            'input': input_data,
            'expected': expected_output,
            'actual': actual_output,
            'error': error_output,
            'success': success
        })
    os.unlink(tmp_path)
    return check_results

if __name__ == "__main__":
    # Пример задачи и решения
    task = {
        'examples': [
            {'input': '2\n3', 'output': '5'},
            {'input': '10\n-2', 'output': '8'}
        ]
    }
    # Пример кода с ошибкой (например, синтаксическая ошибка)
    solution_code = 'a = int(input())\nb = int(input())\nprint(a + b'  # Пропущена скобка
    results = check_solution(task, solution_code)
    for i, res in enumerate(results, 1):
        print(f"Тест {i}:")
        print(f"Входные данные: {res['input']}")
        print(f"Ожидалось: {res['expected']}")
        print(f"Получено: {res['actual']}")
        if res['error']:
            print(f"Ошибка выполнения: {res['error']}")
        print(f"Результат: {'✅ Успех' if res['success'] else '❌ Ошибка'}\n") 