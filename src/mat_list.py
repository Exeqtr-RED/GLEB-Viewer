import re
from collections import defaultdict
import os

def parse_material_report(file_path):
    """
    Парсит текстовый отчет с material name
    """
    materials = defaultdict(list)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Регулярное выражение для поиска путей к .mat файлам
        # Ищем строки типа: D:\путь\к\файлу.mat (совпадений: X)
        mat_files = re.findall(r'(.+?\.mat)\s+\(совпадений:\s*(\d+)\)', content)
        
        print(f"📁 Найдено .mat файлов: {len(mat_files)}")
        
        # Для каждого .mat файла ищем material name
        for mat_file, matches_count in mat_files:
            # Находим блок текста после этого пути до следующего пути или конца
            mat_pattern = re.escape(mat_file)
            next_mat = r'\n\s*D:\\'
            
            # Ищем блок для этого файла
            block_pattern = f'{mat_pattern}.*?(?={next_mat}|\\Z)'
            block_match = re.search(block_pattern, content, re.DOTALL)
            
            if block_match:
                block = block_match.group(0)
                # Ищем все строки с material name="..."
                material_names = re.findall(r'material name="([^"]+)"', block)
                
                for material in material_names:
                    materials[material].append({
                        'file': mat_file,
                        'occurrences': int(matches_count),
                        'line': block[:100]  # Сохраняем часть для контекста
                    })
        
        return materials
        
    except FileNotFoundError:
        print(f"❌ Файл не найден: {file_path}")
        return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def find_duplicates_in_report(file_path):
    """
    Находит дубликаты material name в отчете
    """
    materials = parse_material_report(file_path)
    
    if not materials:
        return
    
    # Находим дубликаты
    duplicates = {name: occurrences for name, occurrences in materials.items() 
                  if len(occurrences) > 1}
    
    print("\n" + "=" * 80)
    print("🔍 АНАЛИЗ ОТЧЕТА ПО MATERIAL NAME")
    print("=" * 80)
    
    if duplicates:
        print(f"\n⚠️ НАЙДЕНО {len(duplicates)} ДУБЛИКАТОВ:\n")
        
        for material_name, occurrences in sorted(duplicates.items()):
            print(f"📌 Material name: '{material_name}'")
            print(f"   Встречается в {len(occurrences)} файлах:")
            
            for occ in occurrences:
                # Извлекаем имя файла без полного пути
                file_name = os.path.basename(occ['file'])
                print(f"      • {file_name} (всего совпадений: {occ['occurrences']})")
            print()
    else:
        print("✅ Дубликатов material name не найдено")
    
    # Статистика
    print("\n📊 СТАТИСТИКА:")
    print(f"   Уникальных material name: {len(materials)}")
    print(f"   Всего вхождений: {sum(len(v) for v in materials.values())}")
    
    # Показываем топ-10 самых частых материалов
    sorted_materials = sorted(materials.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    if sorted_materials:
        print("\n🏆 ТОП-10 САМЫХ ЧАСТЫХ MATERIAL NAME:")
        for name, occurrences in sorted_materials:
            if len(occurrences) > 1:
                print(f"   • '{name}': {len(occurrences)} раз(а)")
    
    return duplicates

# Анализируем конкретные дубликаты из вашего файла
def analyze_specific_duplicates():
    """
    Анализирует конкретные дубликаты из отчета
    """
    print("=" * 80)
    print("🔍 АНАЛИЗ КОНКРЕТНЫХ ДУБЛИКАТОВ ИЗ ВАШЕГО ФАЙЛА")
    print("=" * 80)
    
    duplicates_found = {
        'aircraft_BPLA': [
            'aircraft_BPLA\\v3d\\aircraft_BPLA.mat',
            'aircraft_BPLA _REB\\v3d\\aircraft_BPLA _REB.mat',
            'aircraft_BPLA_scout\\v3d\\aircraft_BPLA_scout.mat'
        ],
        'recognition_base': [
            'aircraft_bomber_common\\v3d\\aircraft_bomber_common.mat',
            'aircraft_bpla_common\\v3d\\aircraft_bpla_common.mat',
            'aircraft_fighter_common\\v3d\\aircraft_fighter_common.mat',
            'aircraft_radar_common\\v3d\\aircraft_radar_common.mat',
            'aircraft_scout_common\\v3d\\aircraft_scout_common.mat',
            'aircraft_stormtrooper_common\\v3d\\aircraft_stormtrooper_common.mat',
            'helicopter_common\\v3d\\helicopter_common.mat'
        ],
        'recognition_red': [
            'aircraft_bomber_common\\v3d\\aircraft_bomber_common.mat',
            'aircraft_bpla_common\\v3d\\aircraft_bpla_common.mat',
            'aircraft_fighter_common\\v3d\\aircraft_fighter_common.mat',
            'aircraft_radar_common\\v3d\\aircraft_radar_common.mat',
            'aircraft_scout_common\\v3d\\aircraft_scout_common.mat',
            'aircraft_stormtrooper_common\\v3d\\aircraft_stormtrooper_common.mat',
            'helicopter_common\\v3d\\helicopter_common.mat'
        ],
        'samolet_specialnyy': [
            'a_100_335\\v3d\\a_100_335.mat',
            'a_50_u_334\\v3d\\a_50_u_334.mat'
        ],
        'samolet_transportnyy': [
            'samolet_transportnyy_31\\v3d\\samolet_transportnyy_31.mat',
            'samolet_transportnyy_gruzovoy_88\\v3d\\samolet_transportnyy_gruzovoy_88.mat',
            'samolet_transportnyy_sanitarnyy\\v3d\\samolet_transportnyy_sanitarnyy.mat'
        ],
        'kosm_apparat': [
            'kosmicheskiy_apparat_19\\v3d\\kosmicheskiy_apparat_19.mat',
            'spacecraft\\v3d\\spacecraft.mat'
        ],
        'raketa_obschego_naznacheniya': [
            'raketa_obschego_naznacheniya\\v3d\\raketa_obschego_naznacheniya.mat',
            'raketa_obschego_naznacheniya_24\\v3d\\raketa_obschego_naznacheniya_24.mat'
        ],
        'vertolet_gruzovoy_94': [
            'vertolet_desantnyy_95\\v3d\\vertolet_desantnyy_95.mat',
            'vertolet_gruzovoy_94\\v3d\\vertolet_gruzovoy_94.mat'
        ],
        'samolet_palubnyy': [
            'istrebitel_palubnyy_59\\v3d\\istrebitel_palubnyy_59.mat',
            'samolet_palubnyy_32\\v3d\\samolet_palubnyy_32.mat'
        ],
        'samolet_dozapravschik': [
            'samolet_dozapravschik_89\\v3d\\samolet_dozapravschik_89.mat',
            'samolet_dozapravschik_89_il_78\\v3d\\samolet_dozapravschik_89.mat'
        ]
    }
    
    print("\n🔴 НАЙДЕНЫ СЛЕДУЮЩИЕ ДУБЛИКАТЫ:\n")
    
    for material, files in duplicates_found.items():
        print(f"⚠️ '{material}' - встречается в {len(files)} файлах:")
        for file in files:
            print(f"   • {file}")
        print()
    
    print("\n💡 РЕКОМЕНДАЦИИ:")
    print("1. Унифицируйте названия материалов")
    print("2. Создайте общие материалы для recognition_base и recognition_red")
    print("3. Проверьте правильность написания aircraft_BPLA (есть пробел в одном из путей)")
    print("4. Объедините одинаковые материалы в справочник")

# Основная программа
if __name__ == "__main__":
    # Укажите путь к вашему файлу
    xml_filename = r"D:\temp\mat_list.xml"
    
    # Анализируем отчет
    duplicates = find_duplicates_in_report(xml_filename)
    
    # Детальный анализ конкретных дубликатов
    analyze_specific_duplicates()