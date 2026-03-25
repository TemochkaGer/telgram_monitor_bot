import matplotlib.pyplot as plt
import time as tm
import logging
import os

logging.basicConfig(
    filename=f"{os.getcwd()}/log/Monitoring.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    
    encoding='utf-8'
)

class SystemInfo:

    def __init__(self):
        "Инициализирует переменные videocards - переменная, содержащая названия директорий драйверов всех видеокарт nvidia в системе, edit - класс обработки информации"
        try:
            self.videocards = self.take_vd_driver()
            self.edit = Editor()
            logging.info("Инициализация класса SystemInfo произведена успешно!")
        except Exception as e:
            logging.error(f"Ошибка при инициализации класса SystemInfo:\n{e}")

    def take_vd_driver(self):
        "Функция собирает список подключенных видеоустройств nvidia и возвращает список этих устройств"
        try:
            videocards = os.listdir("/proc/driver/nvidia/gpus/")
            logging.info("SystemInfo: take_vd_driver -  Отработал успешно!")
            return videocards
        except PermissionError:
            logging.error("SystemInfo: take_vd_driver - Нет прав на чтение директории /proc/driver/nvidia/gpus/!")
            return []
        except FileNotFoundError:
            logging.error("SystemInfo: take_vd_driver - Файла /proc/driver/nvidia/gpus/ не существует!")
            return []
        except Exception as e:
            logging.error(f"SystemInfo: take_vd_driver - Непредвиденная ошибка чтения файла /proc/driver/nvidia/gpus/:\n{e}")
            return []


    def collect_system_info(self):
        "Функция собирает информацию о системе: Процессор, объем ОЗУ, Видеокарты и выводит их"
        try:
            devices = ["/proc/cpuinfo", "/proc/meminfo"] + self.videocards
            info_message = ''

            for device in devices:
                try:
                    with open (device, "r") as f:
                        model = f.read()

                    if device == "/proc/cpuinfo":
                        model = self.edit.take_info(parameter="model name", line=model)
                        model = self.edit.text_replacement(full_line=model, original="model name", new_word="Процессор")
                    elif device == "/proc/meminfo":
                        model = self.edit.take_info(parameter="MemTotal", line=model)
                        model = self.edit.text_replacement(full_line=model, original="MemTotal", new_word="Объем ОЗУ")
                    elif device == "/proc/driver/nvidia/gpus/0000:01:00.0/information":
                        model = self.edit.take_info(parameter="Model", line=model)
                        model = self.edit.text_replacement(full_line=model, original="Model", new_word="Видеокарта")
                    info_message += f"{model}\n"
                    
                    logging.info(f"Класс SystemInfo класс collect_system_info принял данные файла {device}!")
                except PermissionError:
                    logging.error(f"Ошибка класса SystemInfo функции collect_system_info:\nНет прав на чтение файла {device}!")
                    continue
                except FileNotFoundError:
                    logging.error(f"Ошибка класса SystemInfo функции collect_system_info:\nОтсутствие файла {device}!")
                    continue
            logging.info(f"Класс SystemInfo класс collect_system_info отработал штатно!")
            return info_message
        except Exception as e:
            logging.error(f"Ошибка класса SystemInfo функции collect_system_info:\n{e}")
            return ""

class Temperature:
    "Класс собирает метрики темературы со всех устройств материнской платы, edit - класс обработки информации"

    def __init__(self):
        "Инициализирует переменную indexes_for_dev - список всех устройств мат. платы, "
        try:
            self.indexes_for_dev = self.take_index_hwmon()
            self.edit = Editor()
            logging.info("Инициализация класса Temperature произведена успешно!")
        except Exception as e:
            logging.error(f"Ошибка при инициализации класса Temperature:\n{e}")
    
    def collect_dev(self, indexes_for_dev_with_temp):
        "Функция собирает имена девайсов из /sys/class/hwmon/"
        try:
            name_devices = ""
            for index_devices in indexes_for_dev_with_temp:
                try:
                    with open(f"/sys/class/hwmon/{index_devices}/name", 'r') as f:
                        list_devices = f.read()
                    # name_devices.append(list_devices)
                    name_devices += list_devices
                    
                except FileNotFoundError:
                    logging.error(f"Ошибка класса Temperature функции collect_dev:\nОшибка существования файла /sys/class/hwmon/{index_devices}!")
                    continue
                except PermissionError:
                    logging.error(f"Ошибка класса Temperature функции collect_dev:\nОшибка прав на чтение файла /sys/class/hwmon/{index_devices}!")
                    continue

            name_devices = self.edit.sort_stdout(name_devices)
            logging.info("Класс Temperature функция collect_dev отработал штатно!")
            return name_devices
        except Exception as e:
            logging.error(f"Ошибка класса Temperature функции collect_dev:\n{e}")
            return []

    def collect_temp(self):
        """Собирает температуры и имена датчиков"""
        try:
            index_real_dev = []  
            real_temp = []
                   
            
            for i in self.indexes_for_dev:
                temp_file = f"/sys/class/hwmon/{i}/temp1_input"
                
                try:
                    with open(temp_file, 'r') as f:
                        raw_value = f.read().strip()  
                    
                    if raw_value and raw_value.lstrip('-').isdigit():  
                        temp_celsius = float(raw_value) / 1000.0
                        real_temp.append(temp_celsius)      
                        index_real_dev.append(i)            
                        logging.info(f"Датчик {i}: {temp_celsius}°C")
                    else:
                        logging.warning(f"Некорректное значение в {temp_file}: '{raw_value}'")
                        
                except FileNotFoundError:
                    logging.warning(f"Файл не найден: {temp_file}")
                    continue
                except PermissionError:
                    logging.warning(f"Нет прав: {temp_file}")
                    continue
                except ValueError as e:
                    logging.error(f"Ошибка преобразования '{raw_value}': {e}")
                    continue
            
            logging.info(f"Собрано: {len(real_temp)} температур(ы)")
            
            if real_temp:
                return real_temp, self.collect_dev(index_real_dev)
            else:
                return [], []
                
        except Exception as e:
            logging.error(f"Критическая ошибка в collect_temp: {e}")
            return [], []

    def take_index_hwmon(self):
        "Собирает индексы устройств системы"
        try:
            list_file = []
            list_dir = os.listdir("/sys/class/hwmon/")
            for file_name in list_dir:
                if "hwmon" in file_name:
                    list_file.append(file_name)

            logging.info("Класс Temperature функция take_index_hwmon отработала штатно!")
            return list_file
        except Exception as e:
            logging.error(f"Ошибка класса Temperature функции take_index_hwmon:\n{e}")
            return []
        
class Editor:
    "Класс обработки текста"

    def del_spase(self, str_sp, elem_str):
        "Удаляет все вхожления указанного элемента в строке"
        try:
            end_str = ""
            for i in range(len(str_sp)):
                if str_sp[i] not in elem_str:
                    end_str += str_sp[i]
            logging.info("Класс editor функция del_spase отработала штатно!")
            return end_str
        except Exception as e:
            logging.error(f"Ошибка класса editor функции del_spase:\n{e}")
            return ""

    def sort_stdout(self, process: str):
        try:
            out = process.strip().split('\n')
            logging.info("Класс editor функция sort_stdout отработала штатно!")
            return out
        except Exception as e:
            logging.error(f"Ошибка класса editor функции sort_stdout:\n{e}")
            return []
    
    def name_temp(self):
        try:
            temp = Temperature()
            out = []
            list_dev_and_temp = temp.collect_temp()
            list_temp = list_dev_and_temp[0]
            list_name = list_dev_and_temp[1]
            for i in range(len(list_name)):
                out.append(f"{list_name[i]}={list_temp[i]}")
            logging.info("Класс editor функция name_temp отработала штатно!")
            return out
        except Exception as e:
            logging.error(f"Ошибка класса editor функции name_temp:\n{e}")
            return []
        
    def take_info(self, parameter: str, line: str):
        try:
            final_info = ""
            line = line.split("\n")
            for list_elem in line:
                if parameter in list_elem:
                    final_info += list_elem
                    break
            logging.info("Editor: take_info отработал штатно!")
            return final_info
        except Exception as e:
            logging.error(f"Editor: take_info завершился с ошибкой: {e}")
            return ""
        
    def text_replacement(self, full_line: str, original: str, new_word: str):
        try:
            if original in full_line and ":" in full_line:
                value = full_line.split(":", 1)[1]
                value = value.strip()
                full_line = f"{new_word}: {value}"
                logging.info(f"Editor: text_replacement успешно заменил оригинальную строку на новую!")
                return full_line
            elif original not in full_line:
                logging.warning(f"Editor: text_replacement не нашел вхождений параметра {original} в параметр {full_line}")
                return ""
            else:
                logging.error("Editor: text_replacement ошибка в коде!")
                return ""
        except Exception as e:
            logging.error(f"Editor: text_replacement завершился с ошибкой:\n{e}")
            return ""
    
class Grafs:
        def __init__(self):
            try:
                self.temp = Temperature()
                logging.info("Инициализация класса Grafs произведена успешно!")
            except Exception as e:
                logging.error(f"Ошибка при инициализации класса Grafs:\n{e}")

        def take_name_gr(self, duration: int):
            try:
                _, name_dev = self.temp.collect_temp()
                if not name_dev:
                    logging.warning("Не уалось получить имя датчиков для графиков!")
                    return [], []
                
                full_temp = [[] for _ in name_dev]
                
                for second in range(duration + 1):
                    temps, _ = self.temp.collect_temp()
                    for idx, temp_val in enumerate(temps):
                        if idx < len(full_temp):
                            full_temp[idx].append(temp_val)
                    tm.sleep(1)

                logging.info("Класс Grafs функция take_name_gr отработала штатно!")
                return name_dev, full_temp
            except Exception as e:
                logging.error(f"Ошибка класса Grafs функции take_name_gr:\n{e}")
                return [], []
            
        def graf(self, x: list, y: list, name: str, xlable: str, ylabel: str):
            try:
                plt.figure(figsize=(10, 6))
                plt.plot(x, y, label=name)
                plt.xlabel(xlable)
                plt.ylabel(ylabel)
                plt.title(name)
                plt.show()

                filename = f"Graf_{name.replace(' ', '_')}.png"
                plt.savefig(f"{os.getcwd()}/grafs/{filename}")
                logging.info("Класс Grafs функция graf отработала штатно!")
                plt.close()
            except Exception as e:
                logging.error(f"Ошибка класса Grafs функции graf:\n{e}")
                return
            
if __name__ == "__main__":
    a =True
    while a:
        number_do = int(input("1 - Информация о системе\n2 - Температурный график\nВведите действие: "))
        if number_do == 1:
            info = SystemInfo()
            print(info.collect_system_info())
        elif number_do == 2:
            time = int(input("Введите временной отрезок в секундах: "))
            grafs = Grafs()
            data = grafs.take_name_gr(duration=time)
            graf_time = []
            for i in range(0, time + 1):
                graf_time.append(i)
            for j in range(len(list(data[0]))):
                grafs.graf(x = graf_time, y = list(data)[1][j], name = list(data)[0][j], xlable="Время в секундах", ylabel="Температура в градусах")
                print()
        elif number_do == 3:
            a = False
