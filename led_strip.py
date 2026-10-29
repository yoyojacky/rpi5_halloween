#!/usr/bin/env python3
import argparse
import math
import os
import signal
import sys
import time

import numpy as np
import spidev

LED_COUNT = 54
SPI_SPEED = 2_400_000


def encode_byte(value):
    encoded = 0
    for bit in range(8):
        encoded = (encoded << 3) | (0b110 if value & (0x80 >> bit) else 0b100)
    return encoded


ENCODING = tuple(encode_byte(value) for value in range(256))


def encode_pixels(pixels):
    output = bytearray()
    for red, green, blue in pixels:
        for value in (green, red, blue):
            encoded = ENCODING[int(value)]
            output.extend(encoded.to_bytes(3, 'big'))
    output.extend(bytes(16))
    return bytes(output)


def scale_pixels(colors, brightness):
    corrected = np.power(np.clip(colors, 0, 1), 1.35)
    return np.clip(corrected * brightness * 255, 0, 255).astype(np.uint8)


class HalloweenEffect:
    def __init__(self, count):
        self.count = count
        self.index = np.arange(count, dtype=np.float64)
        self.phases = self.index * 2.399 + 0.7
        self.rates = 0.55 + (self.index % 7) * 0.13
        self.palette = np.array([
            [0.18, 0.025, 0.34],
            [0.36, 0.045, 0.62],
            [0.68, 0.07, 0.56],
            [0.28, 0.04, 0.48],
            [0.08, 0.02, 0.22],
        ])

    def render(self, time_seconds):
        phase = (self.index / self.count + time_seconds * 0.032) % 1
        scaled = phase * len(self.palette)
        left = np.floor(scaled).astype(int) % len(self.palette)
        fraction = scaled - np.floor(scaled)
        fraction = fraction * fraction * (3 - 2 * fraction)
        right = (left + 1) % len(self.palette)
        colors = self.palette[left] * (1 - fraction[:, None])
        colors += self.palette[right] * fraction[:, None]
        breathing = 0.78 + 0.12 * np.sin(time_seconds * 0.55 + self.index / self.count * math.tau)
        colors *= breathing[:, None]

        center = (time_seconds * 3.6) % (self.count + 16) - 8
        glow = np.exp(-((self.index - center) / 3.0) ** 2) * 0.72
        orange = np.array([1.0, 0.29, 0.035])
        colors = colors * (1 - glow[:, None] * 0.72) + orange * glow[:, None] * 0.72

        moon_distance = (self.index - self.count * 0.58) / (self.count * 0.11)
        moon_glow = np.exp(-(moon_distance ** 2))
        moon_glow *= 0.08 + 0.05 * (math.sin(time_seconds * 0.7) + 1)
        moon = np.array([1.0, 0.52, 0.12])
        colors = colors * (1 - moon_glow[:, None]) + moon * moon_glow[:, None]

        sparkle = np.maximum(0, np.sin(self.phases + time_seconds * self.rates)) ** 22
        colors += sparkle[:, None] * np.array([0.12, 0.024, 0.003])
        return np.clip(colors, 0, 1)


class SpiStrip:
    def __init__(self, count, bus, device):
        self.count = count
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = SPI_SPEED
        self.spi.mode = 0
        self.spi.bits_per_word = 8
        self.clear()

    def show(self, pixels):
        if len(pixels) != self.count:
            raise ValueError(f'需要 {self.count} 颗灯珠的 RGB 数据')
        self.spi.xfer2(list(encode_pixels(pixels)))

    def clear(self):
        self.show(np.zeros((self.count, 3), dtype=np.uint8))

    def close(self):
        try:
            self.clear()
        finally:
            self.spi.close()


class TerminalStrip:
    def __init__(self, count):
        self.count = count

    def show(self, pixels):
        cells = ''.join(f'\033[48;2;{red};{green};{blue}m ' for red, green, blue in pixels)
        print('\r' + cells + '\033[0m', end='', flush=True)

    def clear(self):
        pass

    def close(self):
        print()


def run_test(strip, count, brightness):
    for index in range(count):
        pixels = np.zeros((count, 3), dtype=np.uint8)
        pixels[index] = np.array([255, 80, 10]) * brightness
        strip.show(pixels)
        time.sleep(0.08)


def main():
    parser = argparse.ArgumentParser(description='54 颗 WS2812 万圣节流动灯效')
    parser.add_argument('--count', type=int, default=LED_COUNT, help='灯珠数量，默认 54')
    parser.add_argument('--brightness', type=float, default=0.40, help='亮度 0 到 1，默认 0.40')
    parser.add_argument('--speed', type=float, default=1.0, help='流动速度，默认 1.0')
    parser.add_argument('--fps', type=int, default=30, help='刷新率，默认 30')
    parser.add_argument('--duration', type=float, help='运行指定秒数后停止')
    parser.add_argument('--bus', type=int, default=0, help='SPI 总线，默认 0')
    parser.add_argument('--device', type=int, default=0, help='SPI 设备，默认 0')
    parser.add_argument('--dry-run', action='store_true', help='在终端模拟，不访问硬件')
    parser.add_argument('--test', action='store_true', help='逐颗点亮橙色灯珠，用于检查接线')
    args = parser.parse_args()
    if not 1 <= args.count <= 1000:
        parser.error('--count 必须在 1 到 1000 之间')
    if not 0 <= args.brightness <= 1:
        parser.error('--brightness 必须在 0 到 1 之间')
    if not 0.05 <= args.speed <= 5:
        parser.error('--speed 必须在 0.05 到 5 之间')
    if not 1 <= args.fps <= 60:
        parser.error('--fps 必须在 1 到 60 之间')
    if args.duration is not None and args.duration <= 0:
        parser.error('--duration 必须大于 0')

    device_path = f'/dev/spidev{args.bus}.{args.device}'
    if not args.dry_run and not os.path.exists(device_path):
        print(
            f'未找到 {device_path}。请先用 sudo raspi-config 启用 SPI 并重启，'
            '或使用 --dry-run 进行模拟。',
            file=sys.stderr,
        )
        return 2

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    strip = TerminalStrip(args.count) if args.dry_run else SpiStrip(args.count, args.bus, args.device)
    try:
        if args.test:
            run_test(strip, args.count, args.brightness)
            return 0

        effect = HalloweenEffect(args.count)
        started = time.monotonic()
        frame = 0
        while running:
            elapsed = time.monotonic() - started
            if args.duration is not None and elapsed >= args.duration:
                break
            colors = effect.render(elapsed * args.speed)
            strip.show(scale_pixels(colors, args.brightness))
            frame += 1
            delay = started + frame / args.fps - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        return 0
    finally:
        strip.close()


if __name__ == '__main__':
    sys.exit(main())
