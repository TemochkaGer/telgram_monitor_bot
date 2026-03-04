import subprocess as sp
import matplotlib as plt

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

if __name__ == "__main__":
    start = editor()
    print(start.name_temp())
