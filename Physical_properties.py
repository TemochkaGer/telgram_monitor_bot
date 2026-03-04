import subprocess as sp
import matplotlib.pyplot as plt
import time

class SystemInfo:

    def collect_system_info(self):
        cpu_model = sp.run('lscpu | grep "Имя модели"', shell=True, capture_output=True, timeout=2)
        cpu_model = self.edit.del_spase((str(cpu_model.stdout)).split(":")[1], '/?|\\, ')
        print(cpu_model)
        return

class Temperature:

    def __init__(self):
        self.edit = editor()
        self.indexes_for_dev = self.take_index_hwmon()
    
    def collect_dev(self, indexes_for_dev_with_temp):
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
        return name_devices

    def collect_temp(self):
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

        return real_temp, self.collect_dev(index_real_dev)

    def take_index_hwmon(self):
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
        return index_list
        
class editor:

    def del_spase(self, str_sp, elem_str):
        end_str = ""
        for i in range(len(str_sp) - 2):
            if str_sp[i] not in elem_str:
                end_str += str_sp[i]

        return end_str
    
    def sort_stdout(self, process):
        if str(type(process)) == "<class 'subprocess.CompletedProcess'>":
            out = (str(process.stdout.decode('utf-8'))).strip().split('\n')
        else:
            out = process.strip().split('\n')
        return out
    
    def name_temp(self):
        temp = Temperature()
        out = []
        list_dev_and_temp = temp.collect_temp()
        list_temp = list_dev_and_temp[0]
        list_name = list_dev_and_temp[1]
        for i in range(len(list_name)):
            out.append(f"{list_name[i]}={list_temp[i]}")
        return out
    
class Grafs:
        def __init__(self):
            self.temp = Temperature()

        def take_name_gr(self):
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
            return name_dev, full_temp
        
        def graf(self, x, y, name):
            plt.plot(x, y, label=f"{name}")
            plt.show()

            
if __name__ == "__main__":
    grafs = Grafs()
    data = grafs.take_name_gr()
    graf_time = []
    for i in range(0, 61):
        graf_time.append(i)
    for j in range(len(list(data[0]))):
        grafs.graf(x = graf_time, y = list(data)[1][j], name = list(data)[0][j])
