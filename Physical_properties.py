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
            cpu_model = sp.run('lscpu | grep "Имя модели"', shell=True, capture_output=True, timeout=2)
            cpu_model = self.edit.del_spase((str(cpu_model.stdout)).split(":")[1], '/?|\\, ')
            logging.info("Класс SystemInfo класс collect_system_info отработал штатно!")
            return cpu_model
        except Exception as e:
            logging.error(f"Ошибка класса SystemInfo функции collect_system_info:\n{e}")

class Temperature:

    def __init__(self):
        try:
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

    def collect_temp(self):
        try:
            index_real_dev = []
            real_temp = []
            full_temp = ""
            for i in self.indexes_for_dev:
                with open(f"/sys/class/hwmon/hwmon{int(i)}/temp1_input", 'r') as f:
                    temp = f.read()
                
                if temp not in '':
                    index_real_dev.append(i)
                    logging.info(f"Класс Temperature функция collect_temp смогла получить температуру одного из девайсов:\n{temp.stdout.decode('utf-8')}")
                else:
                    logging.error(f"Ошибка класса Temperature функции collect_temp:\n{temp.stderr}")
                
                full_temp += temp.stdout.decode('utf-8')
            full_temp = self.edit.sort_stdout(full_temp)
            
            for i in full_temp:
                i = int(i)/1000
                real_temp.append(i)
            logging.info("Класс Temperature функция collect_temp отработала штатно!")
            return real_temp, self.collect_dev(index_real_dev)
        except Exception as e:
            logging.error(f"Ошибка класса Temperature функции collect_temp:\n{e}")

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
    
class Grafs:
        def __init__(self):
            try:
                self.temp = Temperature()
                logging.info("Инициализация класса Grafs произыкдена успешно!")
            except Exception as e:
                logging.error(f"Ошибка при инициализации класса Grafs:\n{e}")

        def take_name_gr(self):
            try:
                list_params = self.temp.collect_temp()
                name_dev = list_params[1]
                full_temp = []
                j = 0
                while j <= 60:
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
            
        
        def graf(self, x, y, name):
            try:
                plt.plot(x, y, label=name)
                plt.show()
                logging.info("Класс Grafs функция graf отработала штатно!")
            except Exception as e:
                logging.error(f"Ошибка класса Grafs функции graf:\n{e}")
            
if __name__ == "__main__":
    grafs = Grafs()
    data = grafs.take_name_gr()
    graf_time = []
    for i in range(0, 61):
        graf_time.append(i)
    for j in range(len(list(data[0]))):
        grafs.graf(x = graf_time, y = list(data)[1][j], name = list(data)[0][j])
