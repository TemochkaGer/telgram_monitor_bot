"""Мониторинг системы:
1. Мониторинг служб из MONITOR_SERVICE и их запуск, в противном случае - отправка сообщения об ошибке;
2. Мониторинг физических характерисик сервера: температура, загруженность ОЗУ, Диска и сравнеие с значениями и списка ALERT_THRESHOLDS;
3. Проверка монтированныйх дисков из MONITIRED_MOUNTS, в противном случае их подключение;
4. Мониторинг активных подключений по SSH через метод last, авотматический вывод по таймеру новых доключений на стервер, игнорирование подтвержденных адресов из IGNORE_IPS;
5. Вывод полной информации одним сообщением через функцию Дашборда;
6. Проверка системной службы Docker и проверка запущенных контейнеров, обязательная проверка контейнеров из глобального списка DOCKER_CONT;
7. Выполнение по команде полной очистки системы методом subprocess, а именно выполнение команд: sudo apt clean, sudo rm -rf /tmp/* && sudo rm -rf /var/tmp/*, sudo journalctl --vacuum-time=7d;
8. Проверка работы серверов кластера методом ping -c 10 {i} | tail -n 2."""

import subprocess
import psutil
#import socket
from dotenv import load_dotenv
#import gpustat
import os
#import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
import GPUtil
from tabulate import tabulate
from typing import List, Tuple
import secrets
import string

load_dotenv('/home/ger/test_telegram_bot/.env')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
USER_CHAT_ID = os.getenv('USER_CHAT_ID')
SUDO_PASS = os.getenv('SUDO_PASS')

MONITOR_SERVICES = ['nginx', 'ssh', 'cron', 'docker']    #Список служб для провреки
MONITIRED_MOUNTS = ["/mnt/adata_ssd"]   #Спикок дисков, которые надо проверить на монтированность
ALERT_THRESHOLDS = {
    'cpu_usage': 90,
    'cpu_temp': 85,
    'ram_usage': 90,
    'disk_free': 10
}   #Список критических значений физических характеристик сервера  

DOCKER_CONT = ['flask-app'] #Список проверяемых контейнеров
NETWORK_CHECK_INTERVAL = 3600   #Интервал проверки сетевых подключений
IGNORE_IPS = ['127.0.0.1', '::1', '0.0.0.0', "109.184.12.59", "192.168.0.80", "192.168.0.1", "188.232.14.138", "100.82.22.133"]  #Список доверенных IP адресов
PING_IP = ['192.168.0.99', '192.168.0.157'] #IP адреса точек кластера для проверки работоспособности
GET_NAME, GET_KEY, GET_SUDO_CONFIRMATION = range(3)

class ServerMonitorBot:
    """Класс осуществляет полную проверку системы через Telegram бота с использованием словесных команд"""

    def __init__(self):
        """Функция инициализации бота на сервере, связывает команды бота с функциями и добавляет интерактивную клавиатуру для упрощенного управления
        Запускает автоматическую проверку некоторых аспектов системы"""
        
        self.updater = Updater(TOKEN, use_context=True)
        self.dispatcher = self.updater.dispatcher

        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("status", self.status))
        self.dispatcher.add_handler(CommandHandler("system", self.system_status))
        self.dispatcher.add_handler(CommandHandler("service", self.services_status))
        self.dispatcher.add_handler(CommandHandler("connections", self.connections_check))
        self.dispatcher.add_handler(CommandHandler("dashboard", self.dash_board))
        self.dispatcher.add_handler(CommandHandler("my_id", self.you_id))
        self.dispatcher.add_handler(CommandHandler("clean", self.clear_disk))
        self.dispatcher.add_handler(CommandHandler('docker', self.docker))
        self.dispatcher.add_handler(CommandHandler('ping_server', self.ping_server))
        self.dispatcher.add_handler(CommandHandler("check_gpu", self.gpu_info))
        self.dispatcher.add_handler(CommandHandler("add_user", self.add_user_start))

        self.dispatcher.add_handler(MessageHandler(Filters.text(["Критические события"]), self.status))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Статус системы"]), self.system_status))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Статус сервисов"]), self.services_status))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Активные подключения"]), self.connections_check))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Дашборд"]), self.dash_board))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Очистка системы"]), self.clear_disk))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Проверка Docker контейнера"]), self.docker))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Пинг машин кластера"]), self.ping_server))
        self.dispatcher.add_handler(MessageHandler(Filters.text(["Статус видеокарты"]), self.gpu_info))

        conv_handler = ConversationHandler(
        entry_points = [MessageHandler(Filters.text('Добавить пользователя'), self.add_user_start)],
        states = {
            GET_NAME: [MessageHandler(Filters.text & ~Filters.command, self.get_name)],
            GET_SUDO_CONFIRMATION: [CallbackQueryHandler(self.get_sudo_confirmation, pattern = '^sudo_')],
            GET_KEY: [MessageHandler(Filters.text & ~Filters.command, self.get_key)]
        },
        fallbacks = [CommandHandler('cancel', self.cancel_add_user)]
        )

        self.dispatcher.add_handler(conv_handler)

        self.last_connections = set()
        self.setup_monitoring()
        self._setup_alert_job()
        self._setup_network_monitoring()
        self._setup_servers_ip_chek()
        self._setup_active_connections()

    def you_id(self, update: Update, context: CallbackContext):
        """Скрытая команда бота для вывода пользователя его ID чата для добавляния в группу доверенных лиц администратором"""
        update.message.reply_text(f"{update.message.chat_id}")
        return

    def verification(self, update: Update):
        """Осуществелиние проверки пользователя, обращающегося к мониторинговой системе, на наличие прав пользования
        Возвращает True в случае вхождения в группу доверенных лиц, иначе False"""

        user_id = update.message.chat_id
        if str(user_id) == str(ADMIN_CHAT_ID) or str(user_id) == str(USER_CHAT_ID):
            return True
        else:
            return False

    def run(self):
        """Запуск бота с выводом состояния в журнал сервиса на сервере"""

        print("🤖 Серверный мониторинг запускается...")
        print(f"📊 Мониторинг сервисов: {MONITOR_SERVICES}")
        print(f"💾 Мониторинг дисков: {MONITIRED_MOUNTS}")
        print("⏰ Периодические проверки настроены")

        try:
            self.updater.start_polling()
            print("✅ Бот успешно запущен!")
            self.updater.idle()
        except Exception as e:
            print(f"❌ Ошибка запуска бота: {e}")
            raise

    def start(self, update: Update, context: CallbackContext):

        keyboard = [
            ['Критические события', 'Статус системы'],
            ['Статус сервисов', 'Активные подключения'],
            ['Дашборд', 'Очистка системы'],
            ["Проверка Docker контейнера", "Пинг машин кластера"],
            ["Статус видеокарты", "Добавить пользователя"]
        ]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard = True)

        message_text = """
            Серверный мониторинг запущен!\n\n
            Доступные команды:\n
            Критические события - Общий статус сервера;\n
            Статус системы - Системное инфо;\n
            Статус сервисовs - Статус сервисов;\n
            Активные подключения - Вывод ip адресов пользователей, подключенных к серверу;\n
            Дашборд - Дашборд состояния системы.\n
            Очистка системы - очистка временных файлов сервера\n
            Проверка Docker контейнера - проверка состояния службы Docker и контейнеров на работу\n
            Пинг машин кластера - проверка сетевого подключения к машинам кластера с выводом информации
            """

        update.message.reply_text(text = message_text, reply_markup = reply_markup)

    def status(self, update: Update, context: CallbackContext):
        """Проверка автооризации пользователя через функцию verification, в случае True осуществляет вывод сообщения о критических состояниях сервера,
        иначе выводит сообщение об ограничениях прав пользователя"""

        ver = self.verification(update)
        if ver:
            alert = []

            cpu_usage = psutil.cpu_percent(interval=1)
            if cpu_usage > ALERT_THRESHOLDS['cpu_usage']:
                alert.append(f"🖥️ CPU: {cpu_usage}%")

            mem = psutil.virtual_memory()
            if mem.percent > ALERT_THRESHOLDS['ram_usage']:
                alert.append(f"💾 ОЗУ: {mem}%")

            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    free_percent = 100 - usage.percent
                    if free_percent < ALERT_THRESHOLDS['disk_free'] and 'snap' not in part.mountpoint:
                        alert.append(f"📀 Свободного места на диске {part.mountpoint} осталось: {free_percent}!")
                except OSError as e:
                    if part.mountpoint == '/mnt/data':
                        alert.append("❌ Диск /mnt/data недоступен!")
                        continue
                except Exception as e:
                    continue

            for service in MONITOR_SERVICES:
                status = self.check_service(service)
                if "Не работает" in status:
                    alert.append(f"❌ Сервис {service} не работает!")

            current_mounts = [part.mountpoint for part in psutil.disk_partitions()]
            for mount in MONITIRED_MOUNTS:
                if mount not in current_mounts:
                    alert.append(f"❌ Диск {mount} не смонтирован!")

            if not alert:
                update.message.reply_text("✅ Все системы работают номально!")
            else:
                update.message.reply_text("\n".join(alert))
        else:
            return "Нет прав доступа!"

    def _setup_network_monitoring(self):
        """Запуск периодической проверки активных сетевых подключений"""
        
        self.updater.job_queue.run_repeating(
            self._check_new_connections,
            interval=NETWORK_CHECK_INTERVAL,
            first=5
        )
        
    def _setup_active_connections(self):
        """Запуск проверки активыных подключиний к серверу с выводом IP адреса"""
        
        self.updater.job_queue.run_repeating(
            lambda context: self._get_active_connections(context),
            interval = 10800.0,
            first = 10.0
        )

    def _setup_alert_job(self):
        """Запуск периодической проверки системы на критические события"""

        self.updater.job_queue.run_repeating(
            self._check_alerts,
            interval=43200.0,
            first=10.0
        )

    def _setup_servers_ip_chek(self):
        """Запуск проверки сетевого подключения к точкам кластера"""
        
        self.updater.job_queue.run_repeating(
            lambda context: self.ping_server_job(context),
            interval = NETWORK_CHECK_INTERVAL,
            first = 10.0
        )

    def ping_server_job(self, context: CallbackContext):
        """Метод для периодической проверки серверов"""
        result = []
        for i in PING_IP:
            rez = subprocess.run(
                [f'ping -c 10 {i} | tail -n 2'],
                shell = True,
                capture_output = True,
                text = True
            )

            count = rez.stdout
            count = count.split(", ")
            count_time = count[-1].split("\n")
            count_time = count_time[0]

            if rez.returncode == 0:
                continue
            else:
                result.append(f'Подключение {i} - неактивно!')

        if result:
            result = str("\n".join(result))
            self.send_alert(f'Статусы подключений:' + '\n' + f'{result}')
        else:
            return

    def services_status(self, update: Update, context: CallbackContext):
        """Проверка состояния сервисов и автоматический перезапуск при необходимости"""

        ver = self.verification(update)
        if ver:
            message = "📊 Статус сервисов: \n\n"

            for service in MONITOR_SERVICES:
                status = self.check_service(service)
                message += f"{service}: {status}\n"

                if "Не работает" in status:
                    restart_result = self.restart_service(service)
                    message += f"🔧 Попытка перезапуска:\n {restart_result}\n"

            update.message.reply_text(message)
        else:
            return "Нет прав доступа!"

    def check_service(self, service_name):
        """Проверяет, работает ли сервис через systemctl"""
        
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return "✅ Работает"
            else:
                return "❌ Не работает"

        except Exception as e:
            return f"❌ Ошибка проверки: {str(e)}"

    def restart_service(self, service_name):
        """Пытаемся перезапустить сервис и возвращает результат"""
        
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', service_name],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return "✅ Успешно перезапущен"
            else:
                error = result.stderr.strip()
                self.send_alert(
                    f"❌ Не удалость перезапустить {service_name}:\n{error}")
                return f"❌ Ошибка запуска: {error}"

        except Exception as e:
            return f"❌ Ошибка при перезапуске: {str(e)}"

    def send_alert(self, message):
        """Отправляет уведомления"""
        
        try:
            if not ADMIN_CHAT_ID:
                print("ADMIN_CHAT_ID не установлен!")
                return

            self.updater.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
            )
            print(f"Уведомление отправлено: {message[:50]}")

        except Exception as e:
            print(f"❌ Ошибка отправки алерта мониторинга {e}")

    def setup_monitoring(self):
        """Настройка периодических задач"""
        
        self.updater.job_queue.run_repeating(
            self._check_service_auto,
            interval=300.0,
            first=10
        )

    def _check_service_auto(self, context: CallbackContext):
        """Автоматическая проверка сервисов"""
        
        for service in MONITOR_SERVICES:
            status = self.check_service(service)
            if "Не работает" in status:
                restart_result = self.restart_service(service)
                self.send_alert(
                    f"❌ Сервис {service} не работал."
                    f"⚙️ Перезапуск: {restart_result}"
                )

    def system_status(self, update: Update, context: CallbackContext):
        """Cбор данных о состоянии сервера"""

        ver = self.verification(update)
        if ver:
            cpu_usage = psutil.cpu_percent(interval=1)
            cpu_temp = self._get_cpu_temp()
            memory = psutil.virtual_memory()
            disk_info = self._get_disk_info()
            mounts_status = self._get_mounts_status()
            message = (
                "🖥 Состояние системы\n\n"
                f"ПРоцессор: {cpu_usage}% (Температура: {cpu_temp}°C)\n"
                f"Память: {memory.percent}% использовано, ({memory.available / (1024**3):.1f} GB свободно)\n\n"f"Диски:{disk_info}\n\n"f"Монтирование:\n{mounts_status}")

            update.message.reply_text(message)
        else:
            return "Нет прав доступа!"

    def _get_cpu_temp(self):
        """Получение температуры процессора"""

        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read()) / 1000
                return float(f'{temp:.1f}')
        except BaseException:
            return 0.0

    def _check_alerts(self, context: CallbackContext):
        """Проверка критических показателей"""
        
        alerts = []

        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > ALERT_THRESHOLDS['cpu_usage']:
            alerts.append(f"Ресурсов процесора использовано {cpu_usage}% при пороге в {ALERT_THRESHOLDS['cpu_usage']}%")

        try:
            cpu_temp = float(self._get_cpu_temp())
            if cpu_temp > ALERT_THRESHOLDS['cpu_temp']:
                alerts.append(f"Температыра процессора {cpu_temp}С при пороговом значении в {ALERT_THRESHOLDS['cpu_temp']}С")

        except BaseException:
            pass

        mem = psutil.virtual_memory()
        if mem.percent > ALERT_THRESHOLDS['ram_usage']:
            alerts.append(f"Значение использованного объема опеативной памяти: {mem}%, превышает заданное значение: {ALERT_THRESHOLDS['ram_usage']}%")

        for part in psutil.disk_partitions():
            if part.mountpoint:
                usage = psutil.disk_usage(part.mountpoint)
                free_persent = 100 - usage.percent
                if free_persent < ALERT_THRESHOLDS['disk_free'] and "snap" not in part.mountpoint:
                    alerts.append(f"Дискового пространства {part.mountpoint} осталось свободно {free_persent}% при минимальном свободном значении - {ALERT_THRESHOLDS['disk_free']}%")

        current_mounts = [part.mountpoint for part in psutil.disk_partitions()]
        for mount in MONITIRED_MOUNTS:
            if mount not in current_mounts:
                alerts.append(f"Диск {mount} не смонтирован!")

        if alerts:
            self.send_alert(f"Критические события: \n\n" + "\n".join(alerts))

    def clear_disk(self, update: Update, context:CallbackContext):
        """Выполнение полной очистки системы методом subprocess, а именно выполнение команд: sudo apt clean, sudo rm -rf /tmp/* && sudo rm -rf /var/tmp/*, sudo journalctl --vacuum-time=7d"""
        
        ver = self.verification(update)
        
        if ver:
            update.message.reply_text("Начало очистки системы...")
            try:
                clear1 = subprocess.run(
                    ['sudo apt clean'],
                    shell = True,
                    capture_output = True,
                    text = True
                )
                clear2 = subprocess.run(
                    ["sudo rm -rf /tmp/* && sudo rm -rf /var/tmp/*"],
                    shell = True,
                    capture_output = True,
                    text = True
                )
                clear3 = subprocess.run(
                    ['sudo journalctl --vacuum-time=7d'],
                    shell = True,
                    capture_output = True,
                    text = True
                )

                if clear1.returncode != 0:
                    update.message.reply_text(f"Не удалось почистить пакет apt!")
                if clear2.returncode != 0:
                    update.message.reply_text(f"Не удалось почистить временные файлы!")
                if clear3.returncode != 0:
                    update.message.reply_text("Не удалось почистить логи!")

                if clear1.returncode == 0 and clear2.returncode == 0 and clear3.returncode == 0:
                    update.message.reply_text("Чистка пакета apt, временных файлов и логов выполнена успешно!")

                update.message.reply_text("Чистка системы завершена!")

            except Exception as e:
                update.message.reply_text(f"Возникла непердвиденная ошибка:\n{e}")

            return
        
        else:
            update.message.reply_text("Нет прав доступа!")
            return


    def _get_disk_info(self):
        """Анализ установленных системных дисков"""

        error_disk = []
        crit_disk = []
        norm_disk = []
        easy_disk = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                if 'snap' in part.mountpoint and usage.percent >= 90:
                    norm_disk.append(f"{part.device} ({part.mountpoint}): "f"{usage.percent}% заполнено.\nНо ничего страшного!⚠️")
                elif "snap" not in part.mountpoint and usage.percent >= 90:
                    crit_disk.append(f"{part.device} ({part.mountpoint}): {usage.percent}% заполнено.\nПора чистить!❗️")
                else:
                    easy_disk.append(f"{part.device} ({part.mountpoint}): {usage.percent}% заполнено.\nВсе хорошо!✅")
            except OSError as e:
                if part.mountpoint == "/mnt/data":
                    error_disk.append(f"Диск {part.device} ({part.mountpoint}): Ошибка доступа!‼️")
                else:
                    error_disk.append(f"Диск {part.device} ({part.mountpoint}): Ошибка доступа!‼️")
            except Exception as e:
                error_disk.append(f"{part.device} ({part.mountpoint}): Неизвестная ошибка!‼️")

        return "\n".join(error_disk)+"\n"+"\n".join(crit_disk)+"\n"+"\n".join(norm_disk)+"\n"+"\n".join(easy_disk)

    def _get_mounts_status(self):
        """Проверка состояния смонтированных дисков"""

        status = []
        current_mounts = [part.mountpoint for part in psutil.disk_partitions()]

        try:
            for mount in MONITIRED_MOUNTS:
                if mount in current_mounts:
                    status.append(f"Диск {mount} смонтирован!")
                else:
                    status.append(f"Диск {mount} не смонтирован!")

                return "\n".join(status)
        except:
            return "Неизвестная ошибка! ‼️"

    def _get_active_connections(self, context: CallbackContext):
        """Получение списка активнвных TCP подключений"""
        
        connections = []

        try:
            result=subprocess.run(
                ["last | awk '{print $3 \" \" $9}' | head"],
                shell = True,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                self.send_alert(f"Ошибка выполнения last: {result.stderr}")
                return connections

            for line in result.stdout.splitlines():
                line = line.strip()
                if line and "logged" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        time = parts[1]
                        connections.append(f"Активное сетевое подключение: {ip}")

        except subprocess.TimeoutExpired:
            self.send_alert("Таймаут при проверке сетевых подключений!")
        except Exception as e:
            self.send_alert(f"Ошибка проверки подключений: {str(e)}")

        return "\n".join(connections)

    def _check_new_connections(self,context: CallbackContext):
        """Обнаружение новых подключений"""

        new_conn = []

        try:
            result=subprocess.run(
                ["last | awk '{print $1 \" \" $3 \" \" $9}' | head"],
                shell = True,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                self.send_alert(f"Ошибка выполнения last: {result.stderr}")
                return new_conn

            for line in result.stdout.splitlines():
                line = line.strip()
                if line and "logged" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[1]
                        name = parts[0]
                        if ip not in IGNORE_IPS:
                            new_conn.append(f"Новое сетевое подключение: {name} {ip}" + "\n" + f"Информация о новом сетевом подключении:\n{self._get_ip_info(ip)}")
                        else:
                            print(f"Новых подключений нет!✅")

        except subprocess.TimeoutExpired:
            self.send_alert("Таймаут при проверке сетевых подключений!")
        except Exception as e:
            self.send_alert(f"Ошибка проверки подключений: {str(e)}")

        if new_conn:
            self.send_alert("🔍 Новые подключения:\n" + "\n".join(new_conn))
        return

    def _get_ip_info(self, ip):
        """Получаем информацию об ip"""

        try:
            import requests
            responce=requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
            data=responce.json()

            if data['status'] == 'success':
                return f"{data['country']} - {data['isp']}"
            return "Информация недоступна!"
        except BaseException:
            return "Неудалось получить информацию!"

    def connections_check(self, update: Update, context: CallbackContext):
        """Показываем текущие подключения"""

        ver = self.verification(update)
        if ver:
            new_conn = []

            try:
                result=subprocess.run(
                    ["last | awk '{print $1 \" \" $3 \" \" $9}' | head"],
                    shell = True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    self.send_alert(f"Ошибка выполнения last: {result.stderr}")
                    return new_conn

                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and "logged" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            ip = parts[1]
                            name = parts[0]
                            new_conn.append(f"Активные подключиения: {name} {ip}")

            except subprocess.TimeoutExpired:
                self.send_alert("Таймаут при проверке сетевых подключений!")
            except Exception as e:
                self.send_alert(f"Ошибка проверки подключений: {str(e)}")

            if not new_conn:
                new_conn.append("✅ Нет активных подключений")

            update.message.reply_text("\n".join(new_conn))
            return
        else:
            update.message.reply_text("Нет прав доступа!")
            return

    def dash_board(self, update: Update, context: CallbackContext):
        """Дашборд всей системы для краткости"""

        ver = self.verification(update)
        if ver:
            full_status = []

            cpu_temp = self._get_cpu_temp()
            if cpu_temp >= ALERT_THRESHOLDS['cpu_temp']:
                full_status.append(f"Центральный процессор - температура: ❌")
            elif cpu_temp >= 60 and cpu_temp <ALERT_THRESHOLDS['cpu_temp']:
                full_status.append(f"Центральный процессор - температура: ⚠️")
            else:
                full_status.append(f"Центральный процессор - температура: ✅")

            cpu_usage = psutil.cpu_percent(interval=1)
            if cpu_usage >= ALERT_THRESHOLDS['cpu_usage']:
                full_status.append(f"Центральный процессор - нагрузка: ❌")
            elif cpu_usage >=60 and cpu_usage < ALERT_THRESHOLDS['cpu_usage']:
                full_status.append(f"Центральный процессор - нагрузка: ⚠️")
            else:
                full_status.append(f"Центральный процессор - нагрузка: ✅")

            ram_usage = psutil.virtual_memory()
            ram_usage = ram_usage.percent
            if ram_usage >= ALERT_THRESHOLDS['ram_usage']:
                full_status.append(f"Оперативная память - нагрузка: ❌")
            elif ram_usage >=70 and ALERT_THRESHOLDS['ram_usage']:
                full_status.append(f"Оперативная память - нагрузка: ⚠️")
            else:
                full_status.append(f"Оперативная память - нагрузка: ✅")

            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    free_percent = 100 - usage.percent
                    if free_percent <= 30 and free_percent > ALERT_THRESHOLDS['disk_free'] and 'snap' not in part.mountpoint:
                        full_status.append(f"Диске {part.mountpoint}    Состояние: ⚠️")
                    elif free_percent <= ALERT_THRESHOLDS['disk_free'] and 'snap' not in part.mountpoint:
                        full_status.append(f"Диск: {part.mountpoint}    Состояние: ❌")
                    else:
                        full_status.append(f"Диск: {part.mountpoint}    Состояние: ✅")
                except Exception as e:
                    full_status.append(f"Диск: {part.mountpoint}    Состояние: ‼️")
                    continue

            for service in MONITOR_SERVICES:
                status = self.check_service(service)
                if "Не работает" in status:
                    full_status.append(f"Сервис {service}   Состояние: ❌")
                else:
                    full_status.append(f"Сервис {service}   Состояние: ✅")

            update.message.reply_text("Дашборд состояния серверва:\nУсловные обозначения:\n✅ - отлично;\n⚠️ - нормально, но стоит обратить внимание;\n❌ - критическое состояние;\n‼️ - вышло из строя;\n" + "\n".join(full_status))
            return
        else:
            update.message.reply_text("Нет прав доступа!")
            return
        
    def docker(self, update: Update, context: CallbackContext):
        """ Проверка системной службы Docker и проверка запущенных контейнеров, обязательная проверка контейнеров из глобального списка DOCKER_CONT"""

        ver = self.verification(update)
        if ver:
            status = subprocess.run(
                ['systemctl', 'is-active', 'docker'],
                capture_output = True,
                text = True
                )
            
            if status.returncode != 0:
                status = subprocess.run(
                    ['sudo systemctl restart docker'],
                    capture_output = True,
                    text = True
                )
            if status.returncode == 0:
                update.message.reply_text(f'Docker запущен\nНачинаем проверку контейнеров...')
                dock_str = subprocess.run(
                    ["docker ps | awk '{print $12}' | tail -n 2"],
                    shell = True,
                    capture_output = True,
                    text = True
                )
                dock_str = dock_str.stdout
                dock_list = dock_str.split("\n")
                update.message.reply_text('Список запущенных контенеров:\n'+f'{"\n".join(dock_list)}')

                count = []
                for i in dock_list:
                    if i in DOCKER_CONT:
                        update.message.reply_text(f'Нужный контейнер {i} запущен!')
                        count.append[i]
                if len(count) < len(DOCKER_CONT):
                    for j in DOCKER_CONT:
                        if j in count:
                            continue
                        else:
                            update.message.reply_text(f"Начинаем перезапуск контейнера {j}")
                            res = subprocess.run(
                                ["docker", "start", j],
                                capture_output = True,
                                text = True
                            )
                            if res.returncode == 0:
                                update.message.reply_text(f"Контейнер {j} успешно перезапущен!")
                            else:
                                update.message.reply_text(f"Контейнер {j} не был перезапущен!")

                update.message.reply_text('Проверка закончена!')
                return
            else:
                update.message.reply_text('Нет прав доступа!')
                return
        
    def ping_server(self, update: Update, context: CallbackContext):
        """Проверка работы серверов кластера методом ping -c 10 {i} | tail -n 2"""
        
        ver = self.verification(update)
        if ver:
            result = []
            for i in PING_IP:
                rez = subprocess.run(
                    [f'ping -c 10 {i} | tail -n 2'],
                    shell = True,
                    capture_output = True,
                    text = True
                )

                count = rez.stdout
                count = count.split(", ")
                count_time = count[-1].split("\n")
                count_time = count_time[0]

                if rez.returncode == 0:
                    result.append(f'Подключение {i} - активно!\nОшbбок в отправке пакетов зафиксировано: {count[1]}!\nОбщее время проверки: {count_time}')
                else:
                    result.append(f'Подключение {i} - неактивно!')

            result = str("\n".join(result))
            self.send_alert(f'Статусы подключений:' + '\n' + f'{result}')
            return
        else:
            update.message.reply_text('Нет прав доступа!')
            return

    def gpu_info(self, update: Update, context: CallbackContext):
        """
        Получает информацию о доступных GPU: загрузка, температура, объём памяти.
        Возвращает отформатированную таблицу.
        """

        try:
            gpus = GPUtil.getGPUs()
            gpu_info_lines = []

            for gpu in gpus:
                gpu_info = (
                    f"  GPU {gpu.id}: {gpu.name}\n"
                    f"  Загрузка: {gpu.load * 100:.1f}%\n"
                    f"  Память: {gpu.memoryUsed}MB / {gpu.memoryTotal}MB (Свободно: {gpu.memoryFree}MB)\n"
                    f"  Температура: {gpu.temperature}°C\n"
                )
                gpu_info_lines.append(gpu_info)

            if gpu_info_lines:
                message = "Информация о видеокартах:\n\n" + "\n".join(gpu_info_lines)
                
            else:
                message = "Видеокарты не обнаружены"
                

            update.message.reply_text(message)

        except Exception as e:
            update.message.reply_text(f"Ошибка получения информации о видеокарте: {str(e)}")
            
        return

    def add_user_start(self, update: Update, context: CallbackContext):
        """Начало процесса добавления пользователя"""
        if not self.verification(update):
            update.message.reply_text("Нет прав доступа!")
            return ConversationHandler.END

        update.message.reply_text('Введите имя пользователя:')
        return GET_NAME

    def generate_password(self):
        """Генерация надежного пароля"""

        length = 16
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        punctuation = string.punctuation

        password = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(digits), 
            secrets.choice(punctuation)
        ]

        all_chars = uppercase + lowercase + digits + punctuation
        password += [secrets.choice(all_chars) for i in range(length - 4)]
        secrets.SystemRandom().shuffle(password)
        password = ''.join(password)

        return password

    def get_name(self, update: Update, context: CallbackContext):
        """Получение имени пользователя и генерация пароля"""
        name = update.message.text.strip().replace(" ", "_")
        context.user_data['name'] = name

        if not self.check_user(update, context, name):
            update.message.reply_text(f'Пользователь {name} уже существует!')
            return ConversationHandler.END

        password = self.generate_password()
        context.user_data['password'] = password

        with open(f'/tmp/{name}_pass.txt', 'w') as f:
            f.write(password)
        with open(f'/tmp/{name}_pass.txt', 'rb') as f:
            update.message.reply_document(f, filename='pass.txt')

        keyboard = [
            [InlineKeyboardButton("Да", callback_data='sudo_yes'),
             InlineKeyboardButton("Нет", callback_data='sudo_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            'Выдать права суперпользователя (sudo)?',
            reply_markup=reply_markup
        )
        return GET_SUDO_CONFIRMATION

    def get_sudo_confirmation(self, update: Update, context: CallbackContext):
        """Обработка подтверждения прав суперпользователя"""
        query = update.callback_query
        query.answer()
        
        if query.data == 'sudo_yes':
            context.user_data['sudo'] = True
            query.edit_message_text(text="Права суперпользователя будут выданы.")
        else:
            context.user_data['sudo'] = False
            query.edit_message_text(text="Права суперпользователя не будут выданы.")
        
        query.message.reply_text('Теперь отправьте SSH публичный ключ!')
        return GET_KEY

    def get_key(self, update: Update, context: CallbackContext):
        """Получение SSH ключа и создание пользователя"""

        key = update.message.text.strip()
        name = context.user_data['name']
        password = context.user_data['password']
        sudo_rights = context.user_data.get('sudo', False)

        success = self.create_user_with_ssh(update, context, name, password, key, sudo_rights)

        if success:
            update.message.reply_text(f'Пользователь {name} создан успешно!')
        else:
            update.message.reply_text(f'Ошибка создания пользователя {name}!')

        if 'name' in context.user_data:
            del context.user_data['name']
        if 'password' in context.user_data:
            del context.user_data['password']
        if 'sudo' in context.user_data:
            del context.user_data['sudo']

        return ConversationHandler.END

    def check_user(self, update: Update, context: CallbackContext, name):
        """Проверка существования пользователя"""

        try:
            check = subprocess.run(
                ['getent', 'passwd', name],
                capture_output=True,
                text=True,
                timeout=30
            )
            return check.returncode != 0
        except Exception as e:
            update.message.reply_text(f'Ошибка проверки пользователя: {e}')
            return False

    def create_user_with_ssh(self, update: Update, context: CallbackContext, name, password, key, sudo_rights=False):
        """Создание пользователя с SSH ключом и опциональными правами sudo"""

        try:
            user_add = subprocess.run(
                ['sudo', '-S','adduser', '--disabled-password', '--gecos', '', '-shell', '/bin/bash', name],
                input = str(SUDO_PASS),
                capture_output=True,
                text=True,
                timeout=30
            )

            if user_add.returncode != 0:
                update.message.reply_text(f'Ошибка создания пользователя: {user_add.stderr}')
                return False

            add_pass = subprocess.run(
                ['sudo', 'chpasswd'],
                input=f'{name}:{password}',
                capture_output=True,
                text=True,
                timeout=30
            )

            if add_pass.returncode != 0:
                update.message.reply_text(f'Ошибка установки пароля: {add_pass.stderr}')
                self.del_user(name)
                return False

            mk_dir = subprocess.run(
                ['sudo', 'mkdir', '-p', f'/home/{name}/.ssh/'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if mk_dir.returncode != 0:
                update.message.reply_text(f'Ошибка создания директории: {mk_dir.stderr}')
                self.del_user(name)
                return False

            mk_key = subprocess.run(
                ['sudo', 'tee', f'/home/{name}/.ssh/authorized_keys'],
                input=key,
                capture_output=True,
                text=True,
                timeout=30
            )

            if mk_key.returncode != 0:
                update.message.reply_text(f'Ошибка записи SSH ключа: {mk_key.stderr}')
                self.del_user(name)
                return False

            chmod_commands = [
                ['sudo', 'chmod', '700', f'/home/{name}/.ssh'],
                ['sudo', 'chmod', '600', f'/home/{name}/.ssh/authorized_keys'],
                ['sudo', 'chown', '-R', f'{name}:{name}', f'/home/{name}/.ssh']
            ]

            for cmd in chmod_commands:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    update.message.reply_text(f'Ошибка установки прав: {result.stderr}')
                    self.del_user(name)
                    return False

            if sudo_rights:
                sudo_groups = ['sudo']
                for group in sudo_groups:
                    sudo_add = subprocess.run(
                        ['sudo', 'usermod', '-aG', group, name],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if sudo_add.returncode != 0:
                        update.message.reply_text(f'Ошибка добавления в группу {group}: {sudo_add.stderr}')

            update.message.reply_text(f'Пользователь {name} создан успешно!' + 
                                    (' С правами суперпользователя.' if sudo_rights else ''))
            return True

        except Exception as e:
            update.message.reply_text(f'Непредвиденная ошибка при создании пользователя {name}:\n{e}')
            self.del_user(name)
            return False

    def del_user(self, name):
        """Удаление пользователя"""

        try:
            sudo_groups = ['sudo', 'wheel']
            for group in sudo_groups:
                subprocess.run(
                    ['sudo', 'gpasswd', '-d', name, group],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

            del_user = subprocess.run(
                ['sudo', 'userdel', '-r', '-f', name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if del_user.returncode == 0:
                return f"Удаление пользователя {name} произведено успешно!"
            else:
                return f"Ошибка при удалении пользователя {name}!\n{del_user.stderr}"
                
        except Exception as e:
            return f"Непредвиденная ошибка при удалении: {e}"

    def cancel_add_user(self, update: Update, context: CallbackContext):
        """Отмена процесса добавления пользователя"""

        update.message.reply_text('Добавление пользователя отменено.')
        context.user_data.clear()
        return ConversationHandler.END

if __name__ == '__main__':
    bot=ServerMonitorBot()
    bot.run()
