import os
import platform
import re
import sys
import threading
import time

import frida
import toml

import ceserver as ce
from automation import ADBAutomation, SSHAutomation
from define import MODE, OS

hostos = platform.system()
if hostos == "Windows":
    import ceserver_memprocfs as cememprocfs

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/memoryview")
from hexview import memory_view_mode

with open("config.toml") as f:
    config = toml.loads(f.read())


def parse_int(s):
    if re.match(r"^0x[0-9a-fA-F]+$", s):
        return int(s, 16)
    else:
        return int(s)


def get_device():
    mgr = frida.get_device_manager()
    changed = threading.Event()

    def on_changed():
        changed.set()

    mgr.on("changed", on_changed)

    device = None
    while device is None:
        device = frida.get_device_manager().add_remote_device("192.168.137.101:6543")

    mgr.off("changed", on_changed)
    return device


def main(package, pid=None, run_mode=None, memory_address=None):
    target_os = config["general"]["target_os"]
    mode = config["general"]["mode"]
    frida_server_ip = config["general"]["frida_server_ip"]
    binary_path = config["general"]["binary_path"]

    adb_auto = config["adb_auto"]
    if run_mode != "memoryview":
        if adb_auto["enable"] and target_os == OS.ANDROID.value:
            adbauto = ADBAutomation(adb_auto)
            if adb_auto["ceserver_path"] != "":
                t1 = threading.Thread(target=adbauto.exec_ceserver)
                t1.start()
            if adb_auto["frida_server_path"] != "":
                t2 = threading.Thread(target=adbauto.exec_frida_server)
                t2.start()
            if adb_auto["gdbserver_path"] != "":
                t3 = threading.Thread(target=adbauto.exec_gdbserver)
                t3.start()
            time.sleep(1)

        ssh_auto = config["ssh_auto"]
        if ssh_auto["enable"] and target_os == OS.IOS.value:
            sshauto = SSHAutomation(ssh_auto)
            if ssh_auto["ceserver_path"] != "":
                t1 = threading.Thread(target=sshauto.exec_ceserver)
                t1.start()
            if ssh_auto["debugserver_path"] != "":
                t2 = threading.Thread(target=sshauto.exec_debugserver)
                t2.start()
            time.sleep(1)

    if target_os in [OS.ANDROID.value, OS.IOS.value]:
        if frida_server_ip != "":
            device = frida.get_device_manager().add_remote_device(frida_server_ip)
        else:
            device = get_device()
        if pid is None:
            apps = device.enumerate_applications()
            target = package
            for app in apps:
                if target == app.identifier or target == app.name:
                    app_identifier = app.identifier
                    app_name = app.name
                    break
            if mode == MODE.SPAWN.value:
                process_id = device.spawn([app_identifier])
                session = device.attach(process_id)
                device.resume(process_id)
                time.sleep(1)
            elif mode == MODE.ATTACH.value:
                session = device.attach(app_name)
            else:
                pass
        else:
            session = device.attach(pid)
    else:
        if frida_server_ip != "":
            device = frida.get_device_manager().add_remote_device(frida_server_ip)
        else:
            device = frida.get_remote_device()
        if pid is None:
            processes = device.enumerate_processes()
            target = package
            for process in processes:
                if target == str(process.pid) or target == process.name:
                    # process_name = process.name
                    process_id = process.pid
                    break
            if mode == MODE.SPAWN.value:
                process_id = device.spawn([binary_path])
                session = device.attach(process_id)
                device.resume(process_id)
                time.sleep(1)
            elif mode == MODE.ATTACH.value:
                session = device.attach(process_id)
            else:
                pass
        else:
            session = device.attach(pid)

    def on_message(message, data):
        print(message)

    if mode != MODE.ENUM.value or run_mode == "memoryview":
        if target_os == OS.WINDOWS.value:
            with open("javascript/core_win.js", "r") as f:
                jscode = f.read()
        else:
            with open("javascript/core.js", "r") as f:
                jscode = f.read()
            with open("javascript/symbol.js", "r") as f:
                jscode2 = f.read()
        script = session.create_script(jscode)
        script.on("message", on_message)
        script.load()
        api = script.exports_sync
        api.SetConfig(config)
        symbol_api = 0

        if run_mode == "memoryview":
            memory_view_mode(api, memory_address)
            return

        if target_os != OS.WINDOWS.value:
            script2 = session.create_script(jscode2)
            script2.on("message", on_message)
            script2.load()
            symbol_api = script2.exports_sync
        if mode == MODE.ATTACH.value:
            info = api.GetInfo()
            process_id = info["pid"]
    else:
        process_id = None
        api = None
        symbol_api = None
        session = None
    ce.ceserver(process_id, api, symbol_api, config, session, device)


def memprocfs_main(config):
    cememprocfs.ceserver(config)


if __name__ == "__main__":
    args = sys.argv
    if config["base"]["engine"] == "memprocfs":
        memprocfs_main(config["memprocfs"])
    else:
        config = config["frida"]
        target = config["general"]["target"]
        target_os = config["general"]["target_os"]
        binary_path = config["general"]["binary_path"]
        mode = config["general"]["mode"]
        if "--memoryview" in args:
            memory_address = int(args[args.index("--memoryview") + 1], 16)
            run_mode = "memoryview"
            pid = int(args[2])
            main(None, pid, run_mode, memory_address)
        else:
            if target_os in [OS.ANDROID.value, OS.IOS.value]:
                if target == "":
                    if mode != MODE.ENUM.value:
                        if args[1] == "-p" or args[1] == "--pid":
                            pid = parse_int(args[2])
                            main(None, pid)
                        else:
                            main(args[1])
                    else:
                        main("")
                else:
                    main(target)
            else:
                if target == "":
                    if binary_path == "":
                        if mode != MODE.ENUM.value:
                            if args[1] == "-p" or args[1] == "--pid":
                                pid = parse_int(args[2])
                                main(None, pid)
                            else:
                                main(args[1])
                        else:
                            main("")
                    else:
                        main("")
                else:
                    main(target)
