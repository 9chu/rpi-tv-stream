# -*- coding: utf-8 -*-
import os
import sys
import time
import pathlib
import logging
import threading
import subprocess
import evdev
import requests
from selectors import DefaultSelector, EVENT_READ


class MaxLevelFilter(logging.Filter):
    def __init__(self, level):
        super(MaxLevelFilter, self).__init__()
        self.level = level

    def filter(self, record):
        return record.levelno < self.level


def setup_console_logger(log_format = "[%(asctime)s][%(levelname)s][%(module)s:%(funcName)s:%(lineno)d] %(message)s"):
    if os.getenv("DEBUG") == "1":
        verbose = True
    else:
        verbose = False

    logger = logging.getLogger()
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # 当且仅当默认 logger 中没有其他 handler 时，才添加 handler
    # 用于防止在 multiprocessing 中重复添加 handler
    if len(logger.handlers) > 0:
        return

    formatter = logging.Formatter(log_format)

    # 使用 stdout 输出 ERROR 以下级别日志
    logger_stdout = logging.StreamHandler(sys.stdout)
    logger_stdout.addFilter(MaxLevelFilter(logging.ERROR))
    logger_stdout.setLevel(logging.DEBUG)
    logger_stdout.setFormatter(formatter)
    logger.addHandler(logger_stdout)

    # 使用 stderr 输出 ERROR 及以上级别日志
    logger_stderr = logging.StreamHandler(sys.stderr)
    logger_stderr.setLevel(logging.ERROR)
    logger_stderr.setFormatter(formatter)
    logger.addHandler(logger_stderr)


class FFPlayThread(threading.Thread):
    def __init__(self, url):
        threading.Thread.__init__(self)
        self.stop = False
        self.url = url

    def run(self):
        while not self.stop:
            logging.info(f"Start ffplay, url={self.url}")
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            proc = subprocess.Popen(["ffplay", "-flags", "low_delay", "-framedrop", "-strict", "experimental", "-fs",
                                     "-hide_banner", "-loglevel", "error", self.url], stdin=subprocess.PIPE,
                                     stdout=sys.stdout, stderr=sys.stderr, env=env)
            proc.stdin.close()
            
            # 等待进程退出
            while proc.poll() is None:
                time.sleep(1)
                if self.stop:
                    logging.info("Receive abort signal, quit ffplay")
                    proc.send_signal(2)  # SIGINT
                    for i in range(0, 3):  # Wait 3 seconds
                        time.sleep(1)
                        if proc.poll() is not None:
                            break
                    if proc.poll() is None:
                        proc.kill()
            
            # 如果没有结束，那么等待一段时间后重启
            if not self.stop:
                logging.error(f"ffplay abnormal exit, code={proc.returncode}")
                time.sleep(3)  # Wait 3 seconds


class IRKeyProcess:
    def __init__(self):
        self.keydown_timer = {}
        self.on_keydown = None
        self.on_keyup = None

    @staticmethod
    def _translate_button(keycode):
        # for OrangePi controller, customize by yourself
        if keycode == 0x444:
            return "up"
        if keycode == 0x41c:
            return "left"
        if keycode == 0x448:
            return "right"
        if keycode == 0x41d:
            return "down"
        if keycode == 0x45d:
            return "menu"
        if keycode == 0x40a:
            return "back"
        if keycode == 0x45c:
            return "ok"
        if keycode == 0x41f:
            return "home"
        if keycode == 0x413:
            return "1"
        if keycode == 0x410:
            return "2"
        if keycode == 0x411:
            return "3"
        if keycode == 0x40f:
            return "4"
        if keycode == 0x40c:
            return "5"
        if keycode == 0x40d:
            return "6"
        if keycode == 0x40b:
            return "7"
        if keycode == 0x408:
            return "8"
        if keycode == 0x409:
            return "9"
        if keycode == 0x447:
            return "0"
        if keycode == 0x41a:
            return "power"
        return None

    def handle_input(self, event):
        key = IRKeyProcess._translate_button(event.value)
        if key is None:
            return
        now = time.perf_counter()
        if key not in self.keydown_timer:
            if self.on_keydown is not None:
                self.on_keydown(key)
        self.keydown_timer[key] = now
            
    def update(self):
        now = time.perf_counter()
        # 更新所有按键的状态
        up_keys = []
        for k in self.keydown_timer:
            trigger_at = self.keydown_timer[k]
            if now - trigger_at > 0.5:  # 500ms
                up_keys.append(k)
        for k in up_keys:
            del self.keydown_timer[k]
            if self.on_keyup is not None:
                self.on_keyup(k)


def handle_ir_button(key, control_url):
    try:
        logging.info(f"Key {key} down")
        if key == "power":
            resp = requests.post(f"{control_url}/restart")
        elif key in ["left", "right", "up", "down", "back", "ok", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]:
            resp = requests.post(f"{control_url}/key", json={"key": key})
        elif key == "menu":
            resp = requests.post(f"{control_url}/key", json={"key": "browse"})
        else:
            return
        resp.raise_for_status()
    except Exception as ex:
        logging.exception("Send message to backend fail")


def main():
    rc_port = os.environ.get("RC_PORT", "rc0")
    rtmp_url = os.environ.get("RTMP_URL", "rtmp://localhost")
    control_url = os.environ.get("CONTROL_URL", "http://localhost:10001")

    setup_console_logger()

    # 初始化 IR 协议
    ir_proc_ret = subprocess.run(["sudo", "/usr/local/bin/ir-enable-all-protocol", rc_port], stdin=subprocess.PIPE,
                                 stdout=sys.stdout, stderr=sys.stderr)
    if ir_proc_ret.returncode != 0:
        logging.warning("Open IR protocol fail")
    
    # 启动 ffplay 并保持运行
    thread = FFPlayThread(rtmp_url)
    thread.start()

    try:
        # 等待红外输入
        input_device = next(pathlib.Path(f"/sys/class/rc/{rc_port}/").glob("input*/event*/"), None)
        if input_device is None:
            logging.error("No IR input detected")
        else:
            device = evdev.InputDevice(f"/dev/input/{input_device.name}")

            process = IRKeyProcess()
            #process.on_keyup = lambda k: logging.info(f"Key {k} up")
            process.on_keydown = lambda k: handle_ir_button(k, control_url)
            
            selector = DefaultSelector()
            selector.register(device, EVENT_READ)

            while True:
                for key, mask in selector.select(timeout=0.1):
                    device = key.fileobj
                    for event in device.read():
                        process.handle_input(event)
                process.update()
    except KeyboardInterrupt as e:
        pass
    
    # 关闭线程
    thread.stop = True
    thread.join()


if __name__ == "__main__":
    main()
