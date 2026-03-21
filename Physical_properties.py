import subprocess as sp
import matplotlib.pyplot as plt
import time
import logging
import os

logging.basicConfig(
    filename="Monitoring.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class SystemInfo:

    def __init__(self):
        try:
            self.edit = Editor()
            logging.info("Инициализация класса SystemInfo произыкдена успешно!")
        except Exception as e:
            logging.error(f"Ошибка при инициализации класса SystemInfo:\n{e}")

    def collect_system_info(self):
        try:
            devices = ["/proc/cpuinfo", "/proc/meminfo"]
            info_massage = ''

            for device in devices:
                with open (device, "r") as f:
                    model = f.read()

                if device == "/proc/cpuinfo":
                    model = self.edit.take_info(parameter="model name", line=model)
                elif device == "/proc/meminfo":
                    model = self.edit.take_info(parameter="MemTotal", line=model)
                info_massage += f"{model}\n"
                
                logging.info("Класс SystemInfo класс collect_system_info отработал штатно!")
            return info_massage
        except PermissionError:
            logging.error("Ошибка класса SystemInfo функции collect_system_info:\nНет прав на чтение файла /proc/cpuinfo!")
        except FileNotFoundError:
            logging.error(f"Ошибка класса SystemInfo функции collect_system_info:\nОтсутствие файла /proc/cpuinfo!")
        except Exception as e:
            logging.error(f"Ошибка класса SystemInfo функции collect_system_info:\n{e}")
            return

class Temperature:

    def __init__(self):
        try:
            self.indexes_for_dev = self.take_index_hwmon()
            self.edit = Editor()
            self.indexes_for_dev = self.take_index_hwmon()
            logging.info("Инициализация класса Temperature произыкдена успешно!")
        except Exception as e:
            logging.error(f"Ошибка при инициализации класса Temperature:\n{e}")
    
    def collect_dev(self, indexes_for_dev_with_temp):
        try:
            name_devices = ''
            for i in indexes_for_dev_with_temp:
                with open(f"/sys/class/hwmon/hwmon{int(i)}/name", 'r') as f:
                    list_devices = f.read()
                name_devices += list_devices
            name_devices = self.edit.sort_stdout(name_devices)
            logging.info("Класс Temperature функция collect_dev отработал штатно!")
            return name_devices
        except Exception as e:
            logging.error(f"Ошибка класса Temperature функции collect_dev:\n{e}")
            return

    def collect_temp(self):
        """Собирает температуры и имена датчиков"""
        try:
            index_real_dev = []  
            real_temp = []       
            
            for i in self.indexes_for_dev:
                temp_file = f"/sys/class/hwmon/hwmon{i}/temp1_input"
                
                try:
                    with open(temp_file, 'r') as f:
                        raw_value = f.read().strip()  
                    
                    if raw_value and raw_value.lstrip('-').isdigit():  
                        temp_celsius = float(raw_value) / 1000.0
                        real_temp.append(temp_celsius)      
                        index_real_dev.append(i)            
                        logging.info(f"Датчик hwmon{i}: {temp_celsius}°C")
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
        try:
            list_file = []
            list_dir = os.listdir("/sys/class/hwmon/")
            for i in list_dir:
                for j in i:
                    if j in 'HhWwMmOoNn':
                        i = i.replace(j, '')
                list_file.append(i)

            logging.info("Класс Temperature функция take_index_hwmon отработала штатно!")
            return list_file
        except Exception as e:
            logging.error(f"Ошибка класса Temperature функции take_index_hwmon:\n{e}")
            return
        
class Editor:

    def del_spase(self, str_sp, elem_str):
        try:
            end_str = ""
            for i in range(len(str_sp) - 2):
                if str_sp[i] not in elem_str:
                    end_str += str_sp[i]
            logging.info("Класс editor функция del_spase отработала штатно!")
            return end_str
        except Exception as e:
            logging.error(f"Ошибка класса editor функции del_spase:\n{e}")
            return

    def sort_stdout(self, process):
        try:
            if str(type(process)) == "<class 'subprocess.CompletedProcess'>":
                out = (str(process.stdout.decode('utf-8'))).strip().split('\n')
            else:
                out = process.strip().split('\n')
            logging.info("Класс editor функция sort_stdout отработала штатно!")
            return out
        except Exception as e:
            logging.error(f"Ошибка класса editor функции sort_stdout:\n{e}")
            return
    
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
            return
        
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
            logging.error(f"Edotor: take_info завершился с ошибкой: {e}")
            return ""
    
class Grafs:
        def __init__(self):
            try:
                self.temp = Temperature()
                logging.info("Инициализация класса Grafs произыкдена успешно!")
            except Exception as e:
                logging.error(f"Ошибка при инициализации класса Grafs:\n{e}")

        def take_name_gr(self, t):
            try:
                list_params = self.temp.collect_temp()
                name_dev = list_params[1]
                full_temp = []
                j = 0
                while j <= t:
                    temp_i_dev = self.temp.collect_temp()[0]
                    if len(full_temp) < len(name_dev):
                        for g in range(len(name_dev)):
                            full_temp.append([])
                    for h in range(len(temp_i_dev)):
                        full_temp[h].append(temp_i_dev[h])
                    j += 1
                    time.sleep(1)
                logging.info("Класс Grafs функция take_name_gr отработала штатно!")
                return name_dev, full_temp
            except Exception as e:
                logging.error(f"Ошибка класса Grafs функции take_name_gr:\n{e}")
                return
            
        def graf(self, x, y, name):
            try:
                plt.plot(x, y, label=name)
                plt.show()
                logging.info("Класс Grafs функция graf отработала штатно!")
            except Exception as e:
                logging.error(f"Ошибка класса Grafs функции graf:\n{e}")
                return
            
if __name__ == "__main__":
    number_do = int(input("1 - Информация о системе\n2 - Температурный график\nВведите дуйствие: "))
    if number_do == 1:
        info = SystemInfo()
        print(info.collect_system_info())
    elif number_do == 2:
        t = 360
        grafs = Grafs()
        data = grafs.take_name_gr(t=t)
        graf_time = []
        for i in range(0, t + 1):
            graf_time.append(i)
        for j in range(len(list(data[0]))):
            grafs.graf(x = graf_time, y = list(data)[1][j], name = list(data)[0][j])
