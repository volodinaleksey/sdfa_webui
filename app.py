import os
from flask import Flask, render_template, request
from collections import defaultdict
import math

app = Flask(__name__)

# Список корневых каталогов, которые можно задавать в приложении
ROOT_DIRECTORIES = ['/data/DDAM1', '/data/DDAM2']

def collect_data():
    """Собирает статистику по файлам _sdfa во всех указанных корневых каталогах"""
    statistics = defaultdict(int)  # Для project/version/ident
    root_statistics = defaultdict(int)  # Для корневых каталогов
    detail_statistics = defaultdict(lambda: defaultdict(int))  # Для детального распределения
    
    for root in ROOT_DIRECTORIES:
        if not os.path.exists(root):
            continue  # Пропускаем несуществующие каталоги
            
        for dirpath, dirnames, filenames in os.walk(root):
            # Получаем относительный путь от корневого каталога
            relative_path = os.path.relpath(dirpath, root)
            parts = relative_path.split(os.sep)
            
            # Проверяем, что путь начинается с SDS/data
            if len(parts) < 2 or parts[0] != 'SDS' or parts[1] != 'data':
                continue
                
            # Проверяем наличие необходимой структуры каталогов (project/version/ident)
            if len(parts) < 5:
                continue
                
            project = parts[2]
            version = parts[3]
            ident = parts[4]
            
            # Обрабатываем файлы с суффиксом _sdfa
            for filename in filenames:
                if filename.endswith('_sdfa'):
                    file_path = os.path.join(dirpath, filename)
                    try:
                        size = os.path.getsize(file_path)
                        statistics[(project, version, ident)] += size
                        root_statistics[root] += size
                        detail_statistics[(project, version, ident)][root] += size
                    except OSError:
                        continue  # Пропускаем файлы, к которым нет доступа
                        
    return statistics, root_statistics, detail_statistics

def build_hierarchy(project_version_ident_data, detail_statistics):
    """Строит иерархическую структуру данных по проектам, идентификаторам и версиям"""
    hierarchy = defaultdict(lambda: {
        'idents': defaultdict(lambda: {
            'versions': {},
            'total_size': 0,
            'distribution': []
        }),
        'total_size': 0,
        'distribution': []
    })

    # Инициализируем распределение по корневым каталогам для всех проектов
    for root in ROOT_DIRECTORIES:
        for project in project_version_ident_data:
            project_name = project[0]

            # Инициализируем распределение по корневым каталогам для проекта
            if len(hierarchy[project_name]['distribution']) < len(ROOT_DIRECTORIES):
                hierarchy[project_name]['distribution'].append({
                    'root': root,
                    'size': 0,
                    'percentage': 0
                })

            # Инициализируем распределение по корневым каталогам для идентификатора
            ident_name = project[2]
            if len(hierarchy[project_name]['idents'][ident_name]['distribution']) < len(ROOT_DIRECTORIES):
                hierarchy[project_name]['idents'][ident_name]['distribution'].append({
                    'root': root,
                    'size': 0,
                    'percentage': 0
                })

    # Заполняем данными
    for (project, version, ident), total_size in project_version_ident_data.items():
        # Добавляем данные о версии
        if 'versions' not in hierarchy[project]['idents'][ident]:
            hierarchy[project]['idents'][ident]['versions'] = {}

        hierarchy[project]['idents'][ident]['versions'][version] = {
            'total_size': total_size,
            'distribution': []
        }

        # Заполняем распределение по корневым каталогам для версии
        for i, root in enumerate(ROOT_DIRECTORIES):
            root_size = detail_statistics[(project, version, ident)].get(root, 0)
            percentage = (root_size / total_size * 100) if total_size > 0 else 0

            hierarchy[project]['idents'][ident]['versions'][version]['distribution'].append({
                'root': root,
                'size': root_size,
                'percentage': percentage
            })

            # Обновляем итоги по идентификатору
            if i < len(hierarchy[project]['idents'][ident]['distribution']):
                hierarchy[project]['idents'][ident]['total_size'] += root_size
                hierarchy[project]['idents'][ident]['distribution'][i]['size'] += root_size

            # Обновляем итоги по проекту
            if i < len(hierarchy[project]['distribution']):
                hierarchy[project]['total_size'] += root_size
                hierarchy[project]['distribution'][i]['size'] += root_size

    # Вычисляем проценты
    for project in hierarchy:
        total_project_size = hierarchy[project]['total_size']

        for i, root_data in enumerate(hierarchy[project]['distribution']):
            percentage = (root_data['size'] / total_project_size * 100) if total_project_size > 0 else 0
            hierarchy[project]['distribution'][i]['percentage'] = percentage

        for ident in hierarchy[project]['idents']:
            total_ident_size = hierarchy[project]['idents'][ident]['total_size']

            for i, root_data in enumerate(hierarchy[project]['idents'][ident]['distribution']):
                percentage = (root_data['size'] / total_ident_size * 100) if total_ident_size > 0 else 0
                hierarchy[project]['idents'][ident]['distribution'][i]['percentage'] = percentage

    return hierarchy

@app.route('/')
def index():
    """Основной маршрут, отображающий статистику"""
    # Получаем параметры сортировки из URL
    sort_by = request.args.get('sort', 'total_size')
    order = request.args.get('order', 'desc')
    
    stats, root_stats, detail_stats = collect_data()
    
    # Строим иерархическую структуру
    hierarchy = build_hierarchy(stats, detail_stats)
    
    # Преобразуем иерархию в список для шаблона
    projects = []
    for project_name, project_data in hierarchy.items():
        project_entry = {
            'name': project_name,
            'total_size': project_data['total_size'],
            'distribution': project_data['distribution'],
            'idents': []
        }
        
        for ident_name, ident_data in project_data['idents'].items():
            ident_entry = {
                'name': ident_name,
                'total_size': ident_data['total_size'],
                'distribution': ident_data['distribution'],
                'versions': []
            }
            
            for version_name, version_data in ident_data['versions'].items():
                version_entry = {
                    'name': version_name,
                    'total_size': version_data['total_size'],
                    'distribution': version_data['distribution']
                }
                ident_entry['versions'].append(version_entry)
            
            # Сортируем версии по размеру
            ident_entry['versions'].sort(key=lambda x: x['total_size'], reverse=True)
            project_entry['idents'].append(ident_entry)
        
        projects.append(project_entry)
    
    # Сортируем проекты
    def sort_key(item):
        if sort_by == 'name':
            return item['name'].lower()
        return item['total_size']
    
    reverse = (order == 'desc')
    projects.sort(key=lambda x: sort_key(x), reverse=reverse)
    
    # Вычисляем общее распределение по корневым каталогам
    total_size = sum(root_stats.values())
    root_distribution = []
    
    for root, size in root_stats.items():
        percentage = (size / total_size * 100) if total_size > 0 else 0
        root_distribution.append({
            'root': root,
            'size': size,
            'percentage': percentage
        })
    
    return render_template('index.html', 
                          projects=projects,  # Теперь это список, а не словарь
                          root_distribution=root_distribution,
                          total_size=total_size,
                          root_directories=ROOT_DIRECTORIES,
                          current_sort=sort_by,
                          current_order=order)

def human_readable_size(size_bytes):
    """Преобразует байты в человекочитаемый формат"""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"

# Регистрируем функцию для использования в шаблонах
app.jinja_env.globals.update(human_readable_size=human_readable_size)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
