# NUT (Network UPS Tools) 独立容器

# 锁定版本避免意外缓存失效
FROM alpine:3.21

# 系统依赖安装（静态层，应该稳定命中缓存）
RUN apk add --no-cache \
        nut python3 bash curl usbutils dos2unix libusb-dev eudev && \
    # 目录 + 权限 + udev 规则一次搞定 \
    mkdir -p /etc/nut /var/run/nut /var/state/ups && \
    chown -R nut:nut /etc/nut /var/run/nut /var/state/ups && \
    mkdir -p /etc/udev/rules.d && \
    printf '%s\n' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="051d", MODE="0666"' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="0463", MODE="0666"' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="0665", MODE="0666"' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="06da", MODE="0666"' \
        > /etc/udev/rules.d/99-nut-ups.rules

COPY driver_event_bridge.py /driver_event_bridge.py
COPY entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 3493

ENTRYPOINT ["/entrypoint.sh"]