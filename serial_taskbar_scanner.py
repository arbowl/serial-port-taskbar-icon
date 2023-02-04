import serial
import serial.tools.list_ports
import json
from time import sleep
from PyQt5.QtCore import QMutex, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QApplication, QMenu, QSystemTrayIcon


class UsbDevice:
    def __init__(self, name: str, send: str, receive: str, baudrate: str):
        self.name = name
        self.send = send
        self.receive = receive
        self.baudrate = baudrate
        self.connection = None
        
    def create_connection(self, com_port: str) -> bool:
        try:
            connection = serial.Serial(port=com_port, baudrate=self.baudrate, timeout=0.1)
            sleep(1)
            # Reads output from the device until it outputs three blank lines in a row
            counter = [None for _ in range(3)]
            while counter != ['' for _ in range(3)]:
                counter = [None for _ in range(3)]
                for count in range(3):
                    check = connection.readline().decode().strip()
                    if check == '':
                        counter[count] = ''
                    else:
                        break

            # Identifies the serial object
            connection.write((self.send + '\r\n').encode())
            sleep(1)
            receive = connection.readline().decode().strip()
            if self.receive in receive:
                self.connection = connection
                return True
        except Exception:
            self.connection = None
            return False


class UsbScanner(QObject):
    send_update = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._running = True
        self._mutex = QMutex()
        self.send_update.connect(update_tooltip)
    
    def stop(self) -> None:
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()
        
    def is_running(self) -> bool:
        try:
            self._mutex.lock()
            return self._running
        finally:
            self._mutex.unlock()
    
    def run(self) -> None:
        all_devices = dict()
        devices_to_scan_for = settings['Devices to Scan For']
        for device in devices_to_scan_for:
            all_devices[device] = UsbDevice(
                    device,
                    device['Send'],
                    device['Receive'],
                    device['Baudrate']
            )
        accounted_for_devices = []
        while self.is_running():
            unaccounted_for_devices = [device for device in all_devices if not device.connection]
            com_list = [comport.device for comport in serial.tools.list_ports.comports()]
            for com_port in com_list:
                port = com_port[3:]
                for device in unaccounted_for_devices:
                    if device.create_connection(port):
                        accounted_for_devices.append(device)
            formatted_devices = [device.name + ': COM' + device.port for device in accounted_for_devices]
            tooltip = ',\n '.join(formatted_devices)
            self.send_update.emit(tooltip)
            sleep(1)
        self.finished.emit()
            
            
def update_tooltip(update: str) -> None:
    tray_icon.setToolTip(update)
    if update:
        tray_icon.setIcon(icons + 'usb_connection.png')
    else:
        tray_icon.setIcon(icons + 'usb_no_connection.png')


if __name__ == '__main__':
    icons = '/Icons/'
    settings = json.load(open('Settings/settings.json'))
    
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    tray_icon = QSystemTrayIcon()
    tray_icon.setIcon(icons + 'usb.png')
    tray_icon.setVisible(True)
    
    scanning_thread = QThread()
    scanner = UsbScanner()
    scanner.moveToThread(scanning_thread)
    scanning_thread.started.connect(scanner.run)
    scanner.finished.connect(scanning_thread.quit)
    scanner.finished.connect(scanning_thread.wait)
    scanner.finished.connect(scanning_thread.deleteLater)
    scanning_thread.start()
    
    right_click_menu = QMenu()
    quit_app = QAction('Quit')
    quit_app.triggered.connect(scanner.stop)
    quit_app.triggered.connect(app.quit)
    right_click_menu.addAction(quit)
    tray_icon.setContextMenu(right_click_menu)
    
    app.exec()