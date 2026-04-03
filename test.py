import psutil
full_info = []
for i in psutil.disk_partitions(all=False):
    i = str(i).split(", ")
    for j in i:
        if "sdiskpart(" in j:
            j = j.replace("sdiskpart(", "")
        elif ")" in j:
            j = j.replace(")", "")
        full_info.append(j)
    full_info.append("")
print("\n".join(full_info))