#!/usr/bin/env python3
import argparse
import json
import math
import random
import signal
import subprocess
import sys
import time

import numpy as np

SAMPLE_RATE = 32000
BLOCK_SIZE = 2048


def list_sinks():
    data = json.loads(subprocess.check_output(['pw-dump'], text=True))
    sinks = []
    for item in data:
        if item.get('type') != 'PipeWire:Interface:Node':
            continue
        properties = item.get('info', {}).get('props', {})
        if properties.get('media.class') != 'Audio/Sink':
            continue
        name = properties.get('node.name', '')
        description = properties.get('node.description', name)
        searchable = ' '.join([
            name,
            description,
            properties.get('device.bus', ''),
            properties.get('alsa.card_name', ''),
        ]).casefold()
        sinks.append({
            'id': item.get('id'),
            'name': name,
            'description': description,
            'usb': 'usb' in searchable,
        })
    return sinks


def choose_sink(sinks, selector):
    if selector:
        needle = selector.casefold()
        return next((
            sink for sink in sinks
            if needle in sink['name'].casefold()
            or needle in sink['description'].casefold()
        ), None)
    return next((sink for sink in sinks if sink['usb']), None)


def stream_connected_to_sink(sink):
    try:
        objects = json.loads(subprocess.check_output(['pw-dump'], text=True))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return False
    stream_ids = set()
    for item in objects:
        if item.get('type') != 'PipeWire:Interface:Node':
            continue
        properties = item.get('info', {}).get('props', {})
        if properties.get('node.name') == 'halloween-soundscape':
            stream_ids.add(item.get('id'))
    if not stream_ids:
        return False
    for item in objects:
        if item.get('type') != 'PipeWire:Interface:Link':
            continue
        info = item.get('info', {})
        if (info.get('output-node-id') in stream_ids
                and info.get('input-node-id') == sink['id']
                and info.get('state') == 'active'):
            return True
    return False


def wait_for_sink(selector):
    waiting = False
    candidate_name = None
    candidate_since = 0
    while True:
        try:
            sink = choose_sink(list_sinks(), selector)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            sink = None
        now = time.monotonic()
        if sink:
            if sink['name'] != candidate_name:
                candidate_name = sink['name']
                candidate_since = now
            elif now - candidate_since >= 3:
                print(f"音频输出：{sink['description']}", flush=True)
                return sink
        else:
            candidate_name = None
            if not waiting:
                if selector:
                    print(f"等待匹配的音频设备：{selector}", flush=True)
                else:
                    print('等待 USB 音箱接入……', flush=True)
                waiting = True
        time.sleep(1)


class Soundscape:
    def __init__(self, sample_rate=SAMPLE_RATE):
        self.rate = sample_rate
        self.random = random.Random()
        self.random_numpy = np.random.default_rng()
        self.position = 0
        self.voices = []
        self.next_effect = 0
        self.effect_index = 0
        self.last_effect = ''
        self.trigger_count = 0
        self.effects = [
            ('owl', 0.18, self.owl),
            ('bell', 0.15, self.bell),
            ('creak', 0.15, self.creak),
            ('ghost', 0.12, self.ghost),
            ('howl', 0.10, self.howl),
            ('flutter', 0.07, self.flutter),
            ('crackle', 0.05, self.crackle),
            ('ghost_laugh', 0.18, self.ghost_laugh),
        ]

    def add_voice(self, signal, gain, pan=None):
        if pan is None:
            pan = self.random.uniform(-0.65, 0.65)
        signal = np.asarray(signal, dtype=np.float64)
        peak = float(np.max(np.abs(signal)))
        if peak > 1:
            signal = signal / peak
        fade_count = min(int(0.025 * self.rate), len(signal) // 2)
        if fade_count:
            fade = np.linspace(0, 1, fade_count, endpoint=False)
            signal[:fade_count] *= fade
            signal[-fade_count:] *= fade[::-1]
        angle = (pan + 1) * math.pi / 4
        stereo = signal[:, None] * np.array([math.cos(angle), math.sin(angle)])
        self.voices.append({'samples': stereo * gain, 'position': 0})

    def envelope(self, duration, attack=0.15, release=0.5):
        times = np.arange(int(duration * self.rate)) / self.rate
        envelope = np.minimum(1, times / attack)
        envelope *= np.minimum(1, (duration - times) / release)
        return np.clip(envelope, 0, 1) ** 1.5

    def owl(self):
        result = np.zeros(int(2.0 * self.rate))
        for start, duration, frequency in [(0.05, 0.48, 345), (0.72, 0.72, 292)]:
            count = int(duration * self.rate)
            times = np.arange(count) / self.rate
            phase = 2 * np.pi * (frequency * times - 13 * times ** 2)
            phase += 0.45 * np.sin(2 * np.pi * 5.2 * times)
            envelope = np.sin(np.linspace(0, np.pi, count)) ** 1.7
            tone = np.sin(phase) + 0.28 * np.sin(2 * phase) + 0.08 * np.sin(3 * phase)
            offset = int(start * self.rate)
            result[offset:offset + count] += tone * envelope * 0.65
        self.add_voice(result, 0.34, self.random.uniform(-0.75, 0.15))

    def bell(self):
        duration = 4.8
        times = np.arange(int(duration * self.rate)) / self.rate
        fundamental = self.random.choice([174.61, 196.0, 220.0])
        result = np.zeros_like(times)
        for ratio, amplitude, decay in [
            (1.0, 1.0, 0.85),
            (2.01, 0.48, 1.15),
            (2.74, 0.28, 1.5),
            (4.12, 0.12, 2.1),
        ]:
            partial = np.sin(2 * np.pi * fundamental * ratio * times)
            result += amplitude * partial * np.exp(-decay * times)
        result *= 1 - np.exp(-times * 75)
        self.add_voice(result * 0.58, 0.38, self.random.uniform(-0.2, 0.45))

    def creak(self):
        duration = self.random.uniform(1.5, 2.3)
        times = np.arange(int(duration * self.rate)) / self.rate
        frequency = 82 + 28 * np.sin(2 * np.pi * 2.2 * times + self.random.random())
        frequency += 13 * np.sin(2 * np.pi * 7.1 * times)
        phase = np.cumsum(2 * np.pi * frequency / self.rate)
        noise = self.random_numpy.standard_normal(len(times))
        noise = np.convolve(noise, np.ones(9) / 9, mode='same')
        result = 0.55 * np.sin(phase) + 0.24 * np.sin(2.03 * phase) + 0.32 * noise
        result *= self.envelope(duration, 0.25, 0.65)
        self.add_voice(result, 0.25)

    def ghost(self):
        duration = 3.8
        times = np.arange(int(duration * self.rate)) / self.rate
        noise = self.random_numpy.standard_normal(len(times))
        near = np.convolve(noise, np.ones(18) / 18, mode='same')
        far = np.convolve(noise, np.ones(90) / 90, mode='same')
        breath = near - far
        phase = 2 * np.pi * (410 * times - 20 * times ** 2)
        phase += 0.6 * np.sin(2 * np.pi * 4.3 * times)
        tone = np.sin(phase) + 0.22 * np.sin(2.01 * phase)
        envelope = np.sin(np.pi * times / duration) ** 2
        result = (0.72 * breath + 0.12 * tone) * envelope
        self.add_voice(result, 0.42)

    def howl(self):
        duration = 3.5
        times = np.arange(int(duration * self.rate)) / self.rate
        progress = np.clip(times / duration, 0, 1)
        frequency = 195 + 165 * np.sin(np.pi * progress) ** 1.2 - 42 * progress
        frequency += 3.5 * np.sin(2 * np.pi * 4.8 * times)
        phase = np.cumsum(2 * np.pi * frequency / self.rate)
        result = np.sin(phase) + 0.31 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
        result *= np.sin(np.pi * progress) ** 0.9 * 0.65
        self.add_voice(result, 0.28, self.random.uniform(-0.8, 0.8))

    def flutter(self):
        duration = 1.35
        times = np.arange(int(duration * self.rate)) / self.rate
        noise = self.random_numpy.standard_normal(len(times))
        low = np.convolve(noise, np.ones(18) / 18, mode='same')
        wings = np.maximum(0, np.sin(2 * np.pi * 11 * times)) ** 4
        chirp_phase = 2 * np.pi * (1450 * times + 290 * times ** 2)
        envelope = self.envelope(duration, 0.12, 0.35)
        result = (0.35 * (noise - low) * wings + 0.07 * np.sin(chirp_phase)) * envelope
        self.add_voice(result, 0.18)

    def crackle(self):
        duration = 0.85
        result = np.zeros(int(duration * self.rate))
        for _ in range(self.random.randint(4, 8)):
            start = self.random.randint(0, len(result) - int(0.08 * self.rate))
            count = int(self.random.uniform(0.018, 0.065) * self.rate)
            times = np.arange(count) / self.rate
            pulse = self.random_numpy.standard_normal(count) * np.exp(-times * self.random.uniform(55, 95))
            result[start:start + count] += pulse * self.random.uniform(0.25, 0.6)
        self.add_voice(result, 0.15, self.random.uniform(-0.55, 0.55))

    def ghost_laugh(self):
        duration = 4.8
        result = np.zeros(int(duration * self.rate))
        cursor = int(0.12 * self.rate)
        syllables = [
            (0.34, 0.10),
            (0.31, 0.09),
            (0.36, 0.12),
            (0.42, 0.14),
            (0.50, 0.16),
            (0.68, 0.0),
        ]
        for index, (length, gap) in enumerate(syllables):
            count = int(length * self.rate)
            times = np.arange(count) / self.rate
            start_frequency = 148 - index * 9
            end_frequency = start_frequency * 0.72
            frequency = start_frequency * (end_frequency / start_frequency) ** (times / length)
            frequency += 2.5 * np.sin(2 * np.pi * (5.1 + index * 0.17) * times)
            phase = np.cumsum(2 * np.pi * frequency / self.rate)
            voice = np.zeros(count)
            for harmonic in range(1, 25):
                harmonic_frequency = harmonic * start_frequency
                formants = 1 + 2.4 * np.exp(-((harmonic_frequency - 720) / 300) ** 2)
                formants += 1.5 * np.exp(-((harmonic_frequency - 1180) / 430) ** 2)
                formants += 0.7 * np.exp(-((harmonic_frequency - 2400) / 600) ** 2)
                voice += (formants / harmonic) * np.sin(harmonic * phase)
            envelope = self.envelope(length, 0.055, 0.13)
            voice *= envelope * (0.8 + 0.2 * np.sin(2 * np.pi * 6.2 * times) ** 2)
            result[cursor:cursor + count] += voice
            cursor += count + int(gap * self.rate)
        dry = result.copy()
        for delay, gain in [(0.19, 0.24), (0.37, 0.13), (0.61, 0.07)]:
            offset = int(delay * self.rate)
            result[offset:] += dry[:-offset] * gain
        self.add_voice(result * 0.28, 0.36, self.random.uniform(-0.2, 0.2))

    def trigger_effect(self):
        if self.effect_index == 0:
            name, action = 'bell', self.bell
        elif self.effect_index == 1:
            name, action = 'ghost_laugh', self.ghost_laugh
        else:
            choices = [effect for effect in self.effects if effect[0] != self.last_effect]
            name, _, action = self.random.choices(
                choices,
                weights=[effect[1] for effect in choices],
                k=1,
            )[0]
        action()
        self.last_effect = name
        self.effect_index += 1
        self.trigger_count += 1

    def create_effect(self, name=None):
        if name is None:
            self.trigger_effect()
        else:
            getattr(self, name)()
        return self.voices.pop(0)['samples']

    def synthesize(self, frames):
        times = (self.position + np.arange(frames)) / self.rate
        output = np.zeros((frames, 2))
        if not self.voices and times[0] >= self.next_effect:
            self.trigger_effect()
            duration = len(self.voices[0]['samples']) / self.rate
            self.next_effect = times[0] + duration + self.random.uniform(1, 3)

        active_voices = []
        for voice in self.voices:
            start = voice['position']
            available = len(voice['samples']) - start
            if available <= 0:
                continue
            count = min(frames, available)
            output[:count] += voice['samples'][start:start + count]
            voice['position'] += count
            if voice['position'] < len(voice['samples']):
                active_voices.append(voice)
        self.voices = active_voices
        self.position += frames
        return np.tanh(output * 1.1)

    def render(self, frames=BLOCK_SIZE):
        output = np.clip(self.synthesize(frames), -0.98, 0.98)
        return (output * 32767).astype('<i2').tobytes()


def play(sink, volume, soundscape, duration=None):
    command = [
        'pw-cat',
        '--playback',
        '--raw',
        '--format', 's16',
        '--rate', str(SAMPLE_RATE),
        '--channels', '2',
        '--channel-map', 'stereo',
        '--target', sink['name'],
        '--volume', str(volume),
        '--latency', '150ms',
        '--properties', 'node.name=halloween-soundscape node.dont-move=true',
        '-',
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, bufsize=0)
    try:
        started = time.monotonic()
        next_health_check = started + 1
        next_block = started
        while True:
            now = time.monotonic()
            if duration is not None and now - started >= duration:
                try:
                    process.stdin.close()
                    process.wait(timeout=3)
                except (BrokenPipeError, subprocess.TimeoutExpired):
                    pass
                return
            if now >= next_health_check:
                if not stream_connected_to_sink(sink):
                    raise BrokenPipeError('音频流已离开目标输出设备')
                next_health_check = now + 0.5
            process.stdin.write(soundscape.render())
            next_block += BLOCK_SIZE / SAMPLE_RATE
            delay = next_block - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_block = time.monotonic()
    finally:
        try:
            if not process.stdin.closed:
                process.stdin.close()
        except BrokenPipeError:
            pass
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            process.wait()


def main():
    parser = argparse.ArgumentParser(description='随机万圣节环境音景')
    parser.add_argument('--volume', type=float, default=0.40, help='音景流音量，0 到 1，默认 0.40')
    parser.add_argument('--device', help='按名称选择输出设备，默认自动寻找 USB 音箱')
    parser.add_argument('--duration', type=float, help='播放指定秒数后停止')
    parser.add_argument('--list-devices', action='store_true', help='列出可用音频输出')
    args = parser.parse_args()
    if not 0 <= args.volume <= 1:
        parser.error('--volume 必须在 0 到 1 之间')
    if args.duration is not None and args.duration <= 0:
        parser.error('--duration 必须大于 0')
    if args.list_devices:
        for sink in list_sinks():
            kind = 'USB' if sink['usb'] else '其他'
            print(f"[{kind}] {sink['description']}\n  {sink['name']}")
        return

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    soundscape = Soundscape()
    while True:
        sink = wait_for_sink(args.device)
        try:
            play(sink, args.volume, soundscape, args.duration)
            return
        except (BrokenPipeError, OSError):
            print('音频连接已断开，等待 USB 音箱重新接入……', flush=True)
            time.sleep(2)


if __name__ == '__main__':
    main()
