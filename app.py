from PyQt6.QtGui import QIcon

from ui import backgroud
from ui import main_window
import api_requests
import utils
import base64

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot, QTimer
from pyzkfp import ZKFP2

import sys


class MainWindow(QMainWindow):
    request_compare = pyqtSignal()
    
    def __init__(self):
        super().__init__()

        self.notificate_ui = main_window.Ui_MainWindow()
        self.notificate_ui.setupUi(self)
        self.setFixedSize(450, 320)
        self.setWindowIcon(QIcon('src/fingerprint.png'))
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        self.worker = Worker()
        self.worker_thread = QThread()
        self.worker.compare_completed.connect(self.compare_completed_slot)
        self.worker.statement_signal.connect(self.statement_update)
        self.request_compare.connect(self.worker.identify_finger)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        self.request_compare.emit()

    def compare_completed_slot(self, is_ok: bool, user_id: str):
        try:
            if is_ok:
                self.notificate_ui.message_text.setText('ОТПЕЧАТОК РАСПОЗНАН')
                self.show()
                API.put_userid_compid(user_id)
                with open('finger_comparing.txt', 'w', encoding='utf-8') as f:
                    f.write(f'finger recognized = {is_ok}')
                app.exit()
            else:
                with open('finger_comparing.txt', 'w', encoding='utf-8') as f:
                    f.write(f'finger recognized = {is_ok}')
                self.notificate_ui.message_text.setText('КЛИЕНТ С ТАКИМ ОТПЕЧАТКОМ НЕ ОБНАРУЖЕН')
                QTimer.singleShot(2000, self.restart)
        except Exception as e:
            utils.write_error_log(e)
            app.exit()

    def restart(self):
        try:
            self.hide()
            self.notificate_ui.message_text.setText('ПОДОЖДИТЕ...')
            self.request_compare.emit()
        except Exception as e:
            utils.write_error_log(e)
            app.exit()

    def statement_update(self):
        try:
            self.show()
        except Exception as e:
            utils.write_error_log(e)
            app.exit()


class Worker(QObject):
    compare_completed = pyqtSignal(bool, str)
    statement_signal = pyqtSignal()

    try:
        zkfp2 = ZKFP2()
        zkfp2.Init()
        zkfp2.OpenDevice(0)
    except Exception as e:
        utils.write_error_log(e)
        exit()

    @pyqtSlot()
    def identify_finger(self):
        try:
            while True:
                capture = Worker.zkfp2.AcquireFingerprint()
                if capture:
                    self.statement_signal.emit()
                    tmp, img = capture
                    break
            finger_print = bytes(tmp)
            all_ids = API.get_all_ids()
            for user_id in all_ids:
                base64_tmp_from_db = API.get_finger_tmp_by_userid(user_id)
                finger_from_db = base64.b64decode(base64_tmp_from_db.encode('utf-8'))
                res = Worker.zkfp2.DBMatch(finger_print, finger_from_db)
                if res > SCORE_LIMIT:
                    Worker.zkfp2.Light('green')
                    self.compare_completed.emit(True, user_id)
                    return
            Worker.zkfp2.Light('red')
            self.compare_completed.emit(False, 'no_user')
        except Exception as e:
            utils.write_error_log(e)
            app.exit()


if __name__ == '__main__':
    try:
        SETTINGS = utils.load_settings_app()
        SCORE_LIMIT = int(SETTINGS['score_limit'])
        IP = f'{SETTINGS["ip"]}:{SETTINGS["port"]}'
        AUTH_DATA = (SETTINGS['login_api'], SETTINGS['password_api'])
        API = api_requests.CompClubRequests(IP, limit_balance=float(SETTINGS["limit_balance"]), product_ids=SETTINGS['product_ids'], auth_data=AUTH_DATA)
    except Exception as e:
        utils.write_error_log(e)
        utils.execute_error_msg()

    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.hide()
    sys.exit(app.exec())
