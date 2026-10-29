# rpi5_halloween
## 项目说明
* 使用DeskPi RackMate 7.84英尺的1280x400像素的HDMI接口触摸屏作为显示。SKU: DP-0059： 显示万圣节恐怖古堡效果
* USB音箱： 随机播放恐怖音效
* WS2812灯带：实现诡异背光环境

## 代码直接通过start.sh开机自动调用

* HDMI接口接：HDMI-A-1接口，就是靠近USB-C口。
* 5V-TOUCH接口： 通过USB-C线接树莓派usb口。
* USB音箱：接USB音箱。
* GPIO10（物理接口19）下面是pinout信息：
```bash
Description        : Raspberry Pi 5B rev 1.0
Revision           : d04170
SoC                : BCM2712
RAM                : 8GB
Storage            : MicroSD
USB ports          : 4 (of which 2 USB3)
Ethernet ports     : 1 (1000Mbps max. speed)
Wi-fi              : True
Bluetooth          : True
Camera ports (CSI) : 2
Display ports (DSI): 2

,--------------------------------.
| oooooooooooooooooooo J8   : +====
| 1ooooooooooooooooooo      : |USB2
|  Wi  Pi Model 5B  V1.0  fan +====
|  Fi     +---+      +---+       |
|         |RAM|      |RP1|    +====
||p       +---+      +---+    |USB3
||c      -------              +====
||i        SoC      |c|c J14     |
(        -------  J7|s|s 12 +======
|  J2 bat   uart   1|i|i oo |   Net
| pwr\..|hd|...|hd|o|1|0    +======
`-| |-1o|m0|---|m1|--------------'

J8:
   3V3  (1) (2)  5V
 GPIO2  (3) (4)  5V
 GPIO3  (5) (6)  GND
 GPIO4  (7) (8)  GPIO14
   GND  (9) (10) GPIO15
GPIO17 (11) (12) GPIO18
GPIO27 (13) (14) GND
GPIO22 (15) (16) GPIO23
   3V3 (17) (18) GPIO24
GPIO10 (19) (20) GND
 GPIO9 (21) (22) GPIO25
GPIO11 (23) (24) GPIO8
   GND (25) (26) GPIO7
 GPIO0 (27) (28) GPIO1
 GPIO5 (29) (30) GND
 GPIO6 (31) (32) GPIO12
GPIO13 (33) (34) GND
GPIO19 (35) (36) GPIO16
GPIO26 (37) (38) GPIO20
   GND (39) (40) GPIO21

J2:
RUN (1)
GND (2)

J7:
COMPOSITE (1)
      GND (2)

J14:
TR01 TAP (1) (2) TR00 TAP
TR03 TAP (3) (4) TR02 TAP

For further information, please refer to https://pinout.xyz/
``` 
* 5V 接5v引脚
* GND接GND引脚
* 默认灯带灯珠数量54

## 图案效果

![screenEffect](./Gemini_Generated_Image_1mok6v1mok6v1mok.jfif)
