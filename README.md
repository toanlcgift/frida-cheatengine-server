## device requirement:
- ios jailbroken device
## build ceserver-ios-lite
- option 1: build from macos, using xcode commandline
- option 2: build from jailbroken device, using FridaCodeManager tweak

## install frida server from jailbroken device

- add frida repo via Cydia/Zebra/Sileo/Installer: https://build.frida.re/
- install frida

## run ceserver-ios-lite binary file on jailbroken device

``` shell
$mobile: sudo chmod 777 ceserver
$mobile: ./ceserver
```

## run main.py from PC/mac

``` python
python main.py app_name
```

## open cheat engine from PC/mac, connect target IP in network mode
