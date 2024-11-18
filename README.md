# 树莓派电视信号转 RTMP & 远程遥控器控制

## 服务端

### 电视信号转 RTMP

#### 前置准备

1. 使用 USB 采集卡采集信号
2. 检查视频捕获设备

    ```bash
    pi@rpi4:~ $ v4l2-ctl --list-devices
    bcm2835-codec-decode (platform:bcm2835-codec):
        /dev/video10
        /dev/video11
        /dev/video12
        /dev/video18
        /dev/video31
        /dev/media3

    bcm2835-isp (platform:bcm2835-isp):
        /dev/video13
        /dev/video14
        /dev/video15
        /dev/video16
        /dev/video20
        /dev/video21
        /dev/video22
        /dev/video23
        /dev/media0
        /dev/media2

    rpivid (platform:rpivid):
        /dev/video19
        /dev/media1

    AV TO USB2.0: AV TO USB2.0 (usb-0000:01:00.0-1.1):
        /dev/video0
        /dev/video1
        /dev/media4

    pi@rpi4:~ $ v4l2-ctl -d /dev/video0 --list-formats-ext
    ioctl: VIDIOC_ENUM_FMT
	Type: Video Capture

	[0]: 'MJPG' (Motion-JPEG, compressed)
		Size: Discrete 720x480
			Interval: Discrete 0.040s (25.000 fps)
			Interval: Discrete 0.050s (20.000 fps)
			Interval: Discrete 0.100s (10.000 fps)
			Interval: Discrete 0.200s (5.000 fps)
		Size: Discrete 640x480
			Interval: Discrete 0.040s (25.000 fps)
			Interval: Discrete 0.050s (20.000 fps)
			Interval: Discrete 0.100s (10.000 fps)
			Interval: Discrete 0.200s (5.000 fps)
		Size: Discrete 480x320
			Interval: Discrete 0.040s (25.000 fps)
			Interval: Discrete 0.050s (20.000 fps)
			Interval: Discrete 0.100s (10.000 fps)
			Interval: Discrete 0.200s (5.000 fps)
		Size: Discrete 320x240
			Interval: Discrete 0.040s (25.000 fps)
			Interval: Discrete 0.050s (20.000 fps)
			Interval: Discrete 0.100s (10.000 fps)
			Interval: Discrete 0.200s (5.000 fps)
	[1]: 'YUYV' (YUYV 4:2:2)
		Size: Discrete 480x320
			Interval: Discrete 0.040s (25.000 fps)
			Interval: Discrete 0.050s (20.000 fps)
			Interval: Discrete 0.100s (10.000 fps)
			Interval: Discrete 0.200s (5.000 fps)
		Size: Discrete 320x240
			Interval: Discrete 0.040s (25.000 fps)
			Interval: Discrete 0.050s (20.000 fps)
			Interval: Discrete 0.100s (10.000 fps)
			Interval: Discrete 0.200s (5.000 fps)
    ```

    可以看到 `/dev/video0` 上可以进行视频信号捕获，在`MJPG`格式下，分辨率最大为`720x480`，可以以`25fps`捕获。

3. 检查音频捕获设备

    ```bash
    pi@rpi4:~ $ arecord --list-devices
    **** List of CAPTURE Hardware Devices ****
    card 3: MS210x [MS210x], device 0: USB Audio [USB Audio]
        Subdevices: 0/1
        Subdevice #0: subdevice #0
    ```

    可以看到设备`hw:CARD=MS210x,DEV=0`。
 
4. 使用 Docker 部署 RTMP 服务

    具体见 https://hub.docker.com/r/tiangolo/nginx-rtmp/

    可以安装在 NAS 上。

    nginx 参考配置如下：

    ```conf
    worker_processes auto;
    rtmp_auto_push on;

    events {}

    rtmp {
        server {
            listen 1935;
            listen [::]:1935 ipv6only=on;

            application tv {
                live on;
                record off;

                allow publish 127.0.0.0/16;
                allow publish 192.168.0.0/16;
                allow publish 10.0.0.0/16;
                allow publish 172.16.0.0/16;
                deny publish all;
                
                allow play all;
            }
        }
    }
    ```

#### 启动服务

1. 安装 PM2 进行进程管理并配置开机自启

    ```bash
    sudo apt install -y nodejs npm
    sudo npm install -g pm2
    pm2 install pm2-logrotate
    pm2 startup
    # 以 pm2 startup 提示为准，这里用户为 pi
    sudo env PATH=$PATH:/usr/bin /usr/local/lib/node_modules/pm2/bin/pm2 startup systemd -u pi --hp /home/pi
    ```

2. 保存 ffmpeg 脚本

    任意目录创建`tv-live-stream.sh`，按需调整内容：

    ```bash
    #!/bin/bash

    function run_stream() {
        ffmpeg -hide_banner -loglevel warning -f alsa -ac 2 -thread_queue_size 256 -i 'hw:CARD=MS210x,DEV=0' \
            -f v4l2 -input_format mjpeg -video_size 720x480 -framerate 25 -thread_queue_size 64 -i /dev/video0 \
            -pix_fmt yuv420p -vf "tpad=start_duration=0.5 [delay]; [delay] scale=960:540 [out]" \
            -vcodec h264_v4l2m2m -quality realtime -g 50 -q:v 2 -b:v 5000k \
            -c:a aac -b:a 128k -ar 44100 \
            -f flv rtmp://192.168.1.1:1935/tv
    }

    sleep 5

    echo "Warm up"
    run_stream & sleep 5; pkill ffmpeg

    echo "Start streaming"
    run_stream
    ```

3. 使用 PM2 启动服务

    ```bash
    pm2 start --name tv-live-stream ./tv-live-stream.sh
    pm2 save
    ```

### 红外遥控器模拟

#### 前置准备

1. 在树莓派 GPIO 18 插入接收端，17 插入发送端
2. 配置 `/boot/firmware/config.txt`，在最后加入

    ```bash
    dtoverlay=gpio-ir,gpio_pin=18
    dtoverlay=gpio-ir-tx,gpio_pin=17
    ```

3. 重启生效
4. 安装 `ir-keytable`
5. 执行 `ir-keytable`

    ```bash
    pi@rpi4:~ $ sudo ir-keytable
    Found /sys/class/rc/rc1/ with:
        Name: vc4-hdmi-1
        Driver: cec
        Default keymap: rc-cec
        Input device: /dev/input/event2
        Supported kernel protocols: cec
        Enabled kernel protocols: cec
        bus: 30, vendor/product: 0000:0000, version: 0x0001
        Repeat delay = 0 ms, repeat period = 125 ms
    Found /sys/class/rc/rc2/ with:
        Name: gpio_ir_recv
        Driver: gpio_ir_recv
        Default keymap: rc-rc6-mce
        Input device: /dev/input/event4
        LIRC device: /dev/lirc1
        Attached BPF protocols:
        Supported kernel protocols: lirc rc-5 rc-5-sz jvc sony nec sanyo mce_kbd rc-6 sharp xmp imon
        Enabled kernel protocols: lirc rc-5 rc-5-sz jvc sony nec sanyo mce_kbd rc-6 sharp xmp imon
        bus: 25, vendor/product: 0001:0001, version: 0x0100
        Repeat delay = 500 ms, repeat period = 125 ms
    Found /sys/class/rc/rc0/ with:
        Name: vc4-hdmi-0
        Driver: cec
        Default keymap: rc-cec
        Input device: /dev/input/event0
        Supported kernel protocols: cec
        Enabled kernel protocols: cec
        bus: 30, vendor/product: 0000:0000, version: 0x0001
        Repeat delay = 0 ms, repeat period = 125 ms
    ```

    可以看到`rc2`为接收端。

6. 临时打开所有红外协议接收

    ```bash
    ir-keytable -s rc2 -p all
    ```

7. 使用 evtest 测试并记录各个按键的红外信号，并修改`main.py`

#### 启动进程

1. 使用 pm2 启动进程

    ```bash
    pm2 start --name rpi-tv-controller --interpreter python uvicorn -- main:app --host 0.0.0.0 --port 10001
    ```

2. 去除红外接收端，去除 config.txt 中的 dtoverlay

## 客户端

### 红外配置

    编译`ir-enable-all-protocol`。

    ```bash
    gcc ir-enable-all-protocol.c -o ir-enable-all-protocol
    sudo cp ir-enable-all-protocol /usr/local/bin/ir-enable-all-protocol
    ```

    通过`visudo`修改命令配置。

    ```bash
    EDITOR=vim sudo -E visudo
    ```

    加入：

    ```bash
    pi ALL=NOPASSWD:/usr/local/bin/ir-enable-all-protocol
    ```

    注意这里用户名为`pi`，根据需要进行调整。

### 准备 pip 环境

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

### 设置开机自动启动

    根据需要修改下述脚本并执行：

    ```bash
    cp startup.sh.default startup.sh
    chmod +x startup.sh
    vim startup.sh # 根据需要修改 startup.sh
    mkdir -p ~/.config/autostart
    cat <<EOF > ~/.config/autostart/RPiTvStreamClient.desktop
    [Desktop Entry]
    Type=Application
    Name=RPiTvStreamClient
    Exec=/where_this_project_stores/startup.sh
    EOF
    ```

    重启即可。
