import os
import re
import locale

def is_valid_hex_line(line):
    """Проверяет, является ли строка валидной записью Intel HEX, включая строки с P:, PA:, PAD:."""
    hex_pattern = r'^:([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})([0-9A-Fa-f]*)([0-9A-Fa-f]{2})$'
    p_pattern = r'^P:([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})([0-9A-Fa-f]*)([0-9A-Fa-f]{2})$'
    pa_pattern = r'^PA:([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})([0-9A-Fa-f]*)([0-9A-Fa-f]{2})$'
    pad_pattern = r'^PAD:([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})([0-9A-Fa-f]*)([0-9A-Fa-f]{2})$'
    return bool(
        re.match(hex_pattern, line.strip()) or
        re.match(p_pattern, line.strip()) or
        re.match(pa_pattern, line.strip()) or
        re.match(pad_pattern, line.strip())
    )

def extract_hex_data(input_file, output_hex_file, is_russian):
    """Извлекает Intel HEX записи (включая P:, PA:, PAD:) из файла и сохраняет их в выходной hex файл."""
    hex_lines = []
    
    # Читаем входной файл
    with open(input_file, 'r', errors='ignore') as f:
        lines = f.readlines()
    
    # Извлекаем только валидные Intel HEX строки, включая P:, PA:, PAD:
    for line in lines:
        line = line.strip()
        if line and is_valid_hex_line(line):
            hex_lines.append(line)
    
    # Сохраняем извлеченные HEX записи в выходной файл
    if hex_lines:
        with open(output_hex_file, 'w') as out:
            out.write('\n'.join(hex_lines) + '\n')
        return hex_lines
    else:
        print("Не найдено валидных Intel HEX записей в файле." if is_russian else
              "No valid Intel HEX records found in the file.")
        input("Нажмите Enter для выхода..." if is_russian else
              "Press Enter to exit...")
        return None

def split_hex_file(hex_file, is_russian):
    """Разделяет hex файл на отдельные прошивки по маркеру :00000001FF."""
    with open(hex_file, 'r') as f:
        lines = f.readlines()

    firmware_count = 0
    current_firmware = []
    output_files = []

    for line in lines:
        line = line.strip()
        if line:
            current_firmware.append(line)
        
        # Проверяем конец прошивки
        if line == ':00000001FF':
            firmware_count += 1
            output_filename = f'{firmware_count}.hex'
            output_files.append(output_filename)
            
            # Записываем прошивку в отдельный файл
            with open(output_filename, 'w') as out:
                out.write('\n'.join(current_firmware) + '\n')
            
            # Очищаем буфер для следующей прошивки
            current_firmware = []

    # Если остались строки после последней прошивки
    if current_firmware:
        firmware_count += 1
        output_filename = f'{firmware_count}.hex'
        output_files.append(output_filename)
        with open(output_filename, 'w') as out:
            out.write('\n'.join(current_firmware) + '\n')

    return firmware_count, output_files

def hex_to_bin(hex_file, bin_file, is_russian):
    """Преобразует Intel HEX файл в бинарный формат."""
    memory = {}
    current_segment = 0  # Для обработки расширенных адресов (04)
    
    try:
        with open(hex_file, 'r', errors='ignore') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line or not is_valid_hex_line(line):
                continue
            
            # Удаляем префиксы P:, PA:, PAD: для обработки
            data_line = line[1:] if line.startswith(':') else line[2:] if line.startswith('P:') else line[3:] if line.startswith('PA:') else line[4:]
            
            # Извлекаем компоненты строки
            byte_count = int(data_line[0:2], 16)
            address = int(data_line[2:6], 16)
            record_type = int(data_line[6:8], 16)
            data = data_line[8:-2]
            
            # Проверяем контрольную сумму
            checksum = int(data_line[-2:], 16)
            byte_values = [int(data_line[i:i+2], 16) for i in range(0, len(data_line)-2, 2)]
            calculated_checksum = (256 - (sum(byte_values) & 0xFF)) & 0xFF
            if calculated_checksum != checksum:
                print(f"Предупреждение: Неверная контрольная сумма в строке {line} файла {hex_file}" if is_russian else
                      f"Warning: Invalid checksum in line {line} of file {hex_file}")
                continue
            
            # Обработка типов записей
            if record_type == 0:  # Данные
                full_address = (current_segment << 16) + address
                for i in range(byte_count):
                    memory[full_address + i] = int(data[i*2:i*2+2], 16)
            
            elif record_type == 4:  # Расширенный линейный адрес
                if byte_count == 2:
                    current_segment = int(data[0:4], 16)
            
            elif record_type == 1:  # Конец файла
                break
        
        if not memory:
            print(f"Предупреждение: Нет данных для преобразования в файле {hex_file}" if is_russian else
                  f"Warning: No data to convert in file {hex_file}")
            return False
        
        # Определяем максимальный адрес для размера бинарного файла
        max_address = max(memory.keys()) + 1
        binary_data = bytearray(max_address)
        
        # Заполняем бинарный массив (0xFF для пустых адресов)
        for i in range(max_address):
            binary_data[i] = memory.get(i, 0xFF)
        
        # Сохраняем бинарный файл
        with open(bin_file, 'wb') as f:
            f.write(binary_data)
        return True
    
    except Exception as e:
        print(f"Ошибка при обработке файла {hex_file}: {str(e)}" if is_russian else
              f"Error processing file {hex_file}: {str(e)}")
        return False

def main():
    # Определяем язык системы
    system_locale = locale.getlocale()[0]
    is_russian = system_locale and 'ru' in system_locale.lower()
    
    # Сканируем текущую директорию
    folder_path = "."
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    
    if not files:
        print("В текущей директории нет файлов." if is_russian else
              "No files found in the current directory.")
        input("Нажмите Enter для выхода..." if is_russian else
              "Press Enter to exit...")
        return
    
    print("Найдены следующие файлы в текущей директории:" if is_russian else
          "The following files were found in the current directory:")
    for i, file in enumerate(files, 1):
        print(f"{i}. {file}")
    
    # Запрашиваем выбор файла
    while True:
        try:
            choice = input("Введите номер файла для обработки (или 'q' для выхода): " if is_russian else
                           "Enter the file number to process (or 'q' to exit): ")
            if choice.lower() == 'q':
                print("Программа завершена." if is_russian else
                      "Program terminated.")
                return
            choice = int(choice)
            if 1 <= choice <= len(files):
                input_file = files[choice - 1]
                break
            else:
                print(f"Пожалуйста, выберите номер от 1 до {len(files)}." if is_russian else
                      f"Please select a number from 1 to {len(files)}.")
        except ValueError:
            print("Пожалуйста, введите корректный номер или 'q' для выхода." if is_russian else
                  "Please enter a valid number or 'q' to exit.")
    
    input_file_path = os.path.join(folder_path, input_file)
    
    # Формируем имя выходного файла на основе входного
    output_hex_file = os.path.splitext(input_file)[0] + '.hex'
    
    try:
        # Извлекаем HEX данные
        hex_lines = extract_hex_data(input_file_path, output_hex_file, is_russian)
        
        if hex_lines:
            print(f"Intel HEX данные (включая P:, PA:, PAD: записи) извлечены и сохранены в {output_hex_file}" if is_russian else
                  f"Intel HEX data (including P:, PA:, PAD: records) extracted and saved to {output_hex_file}")
            
            # Спрашиваем, нужно ли разделить прошивки
            split_choice = input("Хотите разделить прошивки на отдельные файлы? (y/n): " if is_russian else
                                 "Do you want to split the firmware into separate files? (y/n): ").lower()
            
            output_files = []
            if split_choice == 'y':
                count, output_files = split_hex_file(output_hex_file, is_russian)
                print(f"Найдено прошивок: {count}" if is_russian else
                      f"Found {count} firmware(s)")
                if count > 0:
                    print("Созданы файлы:" if is_russian else
                          "Created files:")
                    for file in output_files:
                        print(f"- {file}")
                else:
                    print("Прошивки не найдены в извлеченных данных." if is_russian else
                          "No firmware found in the extracted data.")
                
                # Спрашиваем, нужно ли преобразовать разделенные файлы в .bin
                if output_files:
                    bin_choice = input("Хотите преобразовать разделенные .hex файлы в .bin формат? (y/n): " if is_russian else
                                       "Do you want to convert the split .hex files to .bin format? (y/n): ").lower()
                    if bin_choice == 'y':
                        print("\nПреобразование разделенных файлов в бинарный формат..." if is_russian else
                              "\nConverting split files to binary format...")
                        for hex_file in output_files:
                            bin_file = os.path.splitext(hex_file)[0] + '.bin'
                            print(f"Обработка файла {hex_file}..." if is_russian else
                                  f"Processing file {hex_file}...")
                            if hex_to_bin(hex_file, bin_file, is_russian):
                                print(f"Успешно создан бинарный файл: {bin_file}" if is_russian else
                                      f"Successfully created binary file: {bin_file}")
                            else:
                                print(f"Не удалось преобразовать файл {hex_file}" if is_russian else
                                      f"Failed to convert file {hex_file}")
            else:
                print(f"Разделение прошивок не выполнено. Все данные сохранены в {output_hex_file}." if is_russian else
                      f"Firmware splitting not performed. All data saved to {output_hex_file}.")
            
        else:
            print("Обработка завершена: HEX данные не найдены." if is_russian else
                  "Processing completed: No HEX data found.")
            
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}" if is_russian else
              f"An error occurred: {str(e)}")
        input("Нажмите Enter для выхода..." if is_russian else
              "Press Enter to exit...")

if __name__ == "__main__":
    main()