import subprocess as sp
import matplotlib.pyplot as plt
import datetime
import time

class SystemInfo:

    def __init__(self):
        try:
            self.log = Logging()
            self.edit = editor()
            self.log.write_log(proc="--INFO--Инициализация класса SystemInfo произыкдена успешно!")
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка при инициализации класса SystemInfo:\n{e}")

    def collect_system_info(self):
        try:
            cpu_model = sp.run('lscpu | grep "Имя модели"', shell=True, capture_output=True, timeout=2)
            cpu_model = self.edit.del_spase((str(cpu_model.stdout)).split(":")[1], '/?|\\, ')
            self.log.write_log(proc="--INFO--Класс SystemInfo класс collect_system_info отработал штатно!")
            return cpu_model
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка класса SystemInfo функции collect_system_info:\n{e}")

class Logging:

    def write_log(self, proc):
        with open("Physical_properties.log", "a") as f:
            f.write(f"{datetime.datetime.today()}{proc}\n")
        return            

class Temperature:

    def __init__(self):
        try:
            self.edit = editor()
            self.log = Logging()
            self.indexes_for_dev = self.take_index_hwmon()
            self.log.write_log(proc="--INFO--Инициализация класса Temperature произыкдена успешно!")
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка при инициализации класса Temperature:\n{e}")
    
    def collect_dev(self, indexes_for_dev_with_temp):
        try:
            name_devices = ''
            for i in indexes_for_dev_with_temp:
                list_devices = sp.run(
                    f"cat /sys/class/hwmon/hwmon{int(i)}/name",
                    shell=True,
                    capture_output=True,
                    timeout=5
                )
                name_devices += list_devices.stdout.decode('utf-8')
            name_devices = self.edit.sort_stdout(name_devices)
            self.log.write_log(proc="--INFO--Класс Temperature класс collect_dev отработал штатно!")
            return name_devices
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка класса Temperature функции collect_dev:\n{e}")

    def collect_temp(self):
        try:
            index_real_dev = []
            real_temp = []
            full_temp = ""
            for i in self.indexes_for_dev:
                temp = sp.run(
                    f"cat /sys/class/hwmon/hwmon{int(i)}/temp1_input",
                    shell=True,
                    capture_output=True,
                    timeout=5
                )
                
                if temp.stdout.decode('utf-8') not in '':
                    index_real_dev.append(i)
                
                full_temp += temp.stdout.decode('utf-8')
            full_temp = self.edit.sort_stdout(full_temp)
            
            for i in full_temp:
                i = int(i)/1000
                real_temp.append(i)
            self.log.write_log(proc="--INFO--Класс Temperature класс collect_temp отработал штатно!")
            return real_temp, self.collect_dev(index_real_dev)
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка класса Temperature функции collect_temp:\n{e}")

    def take_index_hwmon(self):
        try:
            list_hwmon = self.edit.sort_stdout(
                sp.run("ls /sys/class/hwmon/ | grep hwmon", 
                    shell=True, capture_output=True, 
                    timeout=3
                    )
                    )
            index_list = []
            for i in list_hwmon:
                for j in i:
                    if j in 'HhWwMmOoNn':
                        i = i.replace(j, '')
                index_list.append(i)
            self.log.write_log(proc="--INFO--Класс Temperature класс take_index_hwmon отработал штатно!")
            return index_list
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка класса Temperature функции take_index_hwmon:\n{e}")
        
class editor:

    def __init__(self):
        self.log = Logging()

    def del_spase(self, str_sp, elem_str):
        try:
            end_str = ""
            for i in range(len(str_sp) - 2):
                if str_sp[i] not in elem_str:
                    end_str += str_sp[i]
            self.log.write_log(proc="--INFO--Класс editor класс del_spase отработал штатно!")
            return end_str
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка класса editor функции del_spase:\n{e}")

    def sort_stdout(self, process):
        try:
            if str(type(process)) == "<class 'subprocess.CompletedProcess'>":
                out = (str(process.stdout.decode('utf-8'))).strip().split('\n')
            else:
                out = process.strip().split('\n')
            self.log.write_log(proc="--INFO--Класс editor класс sort_stdout отработал штатно!")
            return out
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка класса editor функции sort_stdout:\n{e}")
    
    def name_temp(self):
        try:
            temp = Temperature()
            out = []
            list_dev_and_temp = temp.collect_temp()
            list_temp = list_dev_and_temp[0]
            list_name = list_dev_and_temp[1]
            for i in range(len(list_name)):
                out.append(f"{list_name[i]}={list_temp[i]}")
            self.log.write_log(proc="--INFO--Класс editor класс name_temp отработал штатно!")
            return out
        except Exception as e:
            self.log.write_log(proc=f"--ERROR--Ошибка класса editor функции name_temp:\n{e}")
    
class Grafs:
        def __init__(self):
            try:
                self.temp = Temperature()
                self.log = Logging()
                self.log.write_log(proc="--INFO--Инициализация класса Grafs произыкдена успешно!")
            except Exception as e:
                self.log.write_log(proc=f"--ERROR--Ошибка при инициализации класса Grafs:\n{e}")

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
                self.log.write_log(proc="--INFO--Класс Grafs класс take_name_gr отработал штатно!")
                return name_dev, full_temp
            except Exception as e:
                self.log.write_log(proc=f"--ERROR--Ошибка класса Grafs функции take_name_gr:\n{e}")
            
        
        def graf(self, x, y, name):
            try:
                plt.plot(x, y, label=name)
                plt.show()
                self.log.write_log(proc="--INFO--Класс Grafs класс graf отработал штатно!")
            except Exception as e:
                self.log.write_log(proc=f"--ERROR--Ошибка класса Grafs функции graf:\n{e}")
            
if __name__ == "__main__":
    grafs = Grafs()
    data = grafs.take_name_gr()
    graf_time = []
    for i in range(0, 61):
        graf_time.append(i)
    for j in range(len(list(data[0]))):
        grafs.graf(x = graf_time, y = list(data)[1][j], name = list(data)[0][j])
