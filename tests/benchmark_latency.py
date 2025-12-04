#!/usr/bin/env python3
"""
Latency Benchmark for QuakeLiveInterface

Measures the round-trip time (RTT) of the action-observation loop.

For a twitch shooter like Quake:
    - < 20ms: Excellent (pro-level responsive)
    - 20-50ms: Good (playable)
    - 50-100ms: Acceptable (casual play)
    - > 100ms: Problematic (agent will be "clumsy")

Measures:
    - Action send time (T0)
    - Redis publish latency
    - State receive time (T4)
    - Full step() latency
    - Frame rate (observations per second)

Usage:
    python tests/benchmark_latency.py [--host localhost] [--samples 1000]
"""

import argparse
import time
import sys
import os
import numpy as np
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from QuakeLiveInterface.env import QuakeLiveEnv


class LatencyBenchmark:
    """Benchmarks environment latency characteristics."""

    def __init__(self, env):
        self.env = env
        self.step_times = []
        self.state_ages = []
        self.frame_intervals = []
        self.last_frame_time = None

    def run_benchmark(self, num_samples=1000, warmup=100):
        """Run the latency benchmark."""
        print(f"\n📊 Running Latency Benchmark ({num_samples} samples)...")
        print("-" * 50)

        # Reset and warmup
        print("  Warming up...")
        self.env.reset()
        for _ in range(warmup):
            action = self.env.action_space.sample()
            self.env.step(action)

        # Benchmark loop
        print("  Benchmarking...")
        self.step_times = []
        self.frame_intervals = []

        for i in range(num_samples):
            action = self.env.action_space.sample()

            # Measure step() latency
            t0 = time.perf_counter()
            obs, reward, terminated, truncated, info = self.env.step(action)
            t1 = time.perf_counter()

            step_latency_ms = (t1 - t0) * 1000
            self.step_times.append(step_latency_ms)

            # Track frame intervals
            if self.last_frame_time is not None:
                interval = (t1 - self.last_frame_time) * 1000
                self.frame_intervals.append(interval)
            self.last_frame_time = t1

            # Progress
            if (i + 1) % 200 == 0:
                print(f"    {i + 1}/{num_samples} samples collected...")

            if terminated or truncated:
                self.env.reset()

        return self._calculate_stats()

    def _calculate_stats(self):
        """Calculate and return statistics."""
        step_arr = np.array(self.step_times)
        frame_arr = np.array(self.frame_intervals) if self.frame_intervals else np.array([0])

        stats = {
            'step_latency': {
                'mean': np.mean(step_arr),
                'std': np.std(step_arr),
                'min': np.min(step_arr),
                'max': np.max(step_arr),
                'p50': np.percentile(step_arr, 50),
                'p95': np.percentile(step_arr, 95),
                'p99': np.percentile(step_arr, 99),
            },
            'frame_rate': {
                'mean_interval': np.mean(frame_arr),
                'fps': 1000 / np.mean(frame_arr) if np.mean(frame_arr) > 0 else 0,
                'jitter': np.std(frame_arr),
            },
            'samples': len(self.step_times)
        }

        return stats

    def print_report(self, stats):
        """Print a formatted benchmark report."""
        print("\n" + "=" * 60)
        print("    LATENCY BENCHMARK REPORT")
        print("=" * 60)

        # Step latency
        sl = stats['step_latency']
        print(f"\n📈 Step Latency (action → observation)")
        print(f"   Mean:   {sl['mean']:.2f} ms")
        print(f"   Std:    {sl['std']:.2f} ms")
        print(f"   Min:    {sl['min']:.2f} ms")
        print(f"   Max:    {sl['max']:.2f} ms")
        print(f"   P50:    {sl['p50']:.2f} ms")
        print(f"   P95:    {sl['p95']:.2f} ms")
        print(f"   P99:    {sl['p99']:.2f} ms")

        # Interpretation
        mean_latency = sl['mean']
        print(f"\n🎮 Interpretation:")
        if mean_latency < 20:
            print(f"   ✅ EXCELLENT ({mean_latency:.1f}ms) - Pro-level responsiveness")
        elif mean_latency < 50:
            print(f"   ✅ GOOD ({mean_latency:.1f}ms) - Fully playable")
        elif mean_latency < 100:
            print(f"   ⚠️  ACCEPTABLE ({mean_latency:.1f}ms) - May affect fast reactions")
        else:
            print(f"   ❌ HIGH ({mean_latency:.1f}ms) - Agent will be sluggish")

        # Frame rate
        fr = stats['frame_rate']
        print(f"\n📊 Frame Rate")
        print(f"   Effective FPS:    {fr['fps']:.1f}")
        print(f"   Frame Interval:   {fr['mean_interval']:.2f} ms")
        print(f"   Jitter (std):     {fr['jitter']:.2f} ms")

        if fr['fps'] >= 60:
            print(f"   ✅ Smooth - matching server tick rate")
        elif fr['fps'] >= 30:
            print(f"   ⚠️  Adequate - may miss some frames")
        else:
            print(f"   ❌ Low - significant frame drops")

        # Recommendations
        print(f"\n💡 Recommendations:")
        if mean_latency > 50:
            print("   - Check network latency to Redis")
            print("   - Consider running Redis locally")
            print("   - Profile step() to find bottlenecks")
        if fr['jitter'] > 10:
            print("   - High jitter detected - check for GC pauses")
            print("   - Consider using a process pool for actions")

        print("\n" + "=" * 60)


def run_redis_ping_test(host, port):
    """Test raw Redis latency."""
    import redis

    print("\n🔌 Redis Connection Test")
    print("-" * 50)

    try:
        r = redis.Redis(host=host, port=port, decode_responses=True)

        # Ping test
        ping_times = []
        for _ in range(100):
            t0 = time.perf_counter()
            r.ping()
            t1 = time.perf_counter()
            ping_times.append((t1 - t0) * 1000)

        ping_arr = np.array(ping_times)
        print(f"   Redis Ping:  {np.mean(ping_arr):.2f} ms (mean), "
              f"{np.percentile(ping_arr, 99):.2f} ms (p99)")

        # Pub/sub roundtrip test
        pubsub = r.pubsub()
        pubsub.subscribe('test_channel')

        rtt_times = []
        for _ in range(100):
            t0 = time.perf_counter()
            r.publish('test_channel', 'ping')
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            t1 = time.perf_counter()
            if msg:
                rtt_times.append((t1 - t0) * 1000)

        if rtt_times:
            rtt_arr = np.array(rtt_times)
            print(f"   Pub/Sub RTT: {np.mean(rtt_arr):.2f} ms (mean), "
                  f"{np.percentile(rtt_arr, 99):.2f} ms (p99)")
        else:
            print("   Pub/Sub RTT: Could not measure (no messages received)")

        pubsub.unsubscribe()
        r.close()

    except Exception as e:
        print(f"   ❌ Redis test failed: {e}")


def run_action_throughput_test(env, duration=5.0):
    """Test maximum action throughput."""
    print(f"\n🚀 Action Throughput Test ({duration}s)")
    print("-" * 50)

    env.reset()

    action_count = 0
    start_time = time.perf_counter()

    while time.perf_counter() - start_time < duration:
        action = env.action_space.sample()
        env.step(action)
        action_count += 1

    elapsed = time.perf_counter() - start_time
    actions_per_sec = action_count / elapsed

    print(f"   Actions executed: {action_count}")
    print(f"   Duration: {elapsed:.2f}s")
    print(f"   Throughput: {actions_per_sec:.1f} actions/sec")

    if actions_per_sec >= 60:
        print(f"   ✅ Can maintain 60Hz action rate")
    elif actions_per_sec >= 30:
        print(f"   ⚠️  Limited to ~{actions_per_sec:.0f}Hz")
    else:
        print(f"   ❌ Throughput too low for real-time control")


def main():
    parser = argparse.ArgumentParser(description='Latency Benchmark')
    parser.add_argument('--host', default='localhost', help='Redis host')
    parser.add_argument('--port', type=int, default=6379, help='Redis port')
    parser.add_argument('--samples', type=int, default=1000, help='Number of samples')
    args = parser.parse_args()

    print("=" * 60)
    print("    LATENCY BENCHMARK SUITE")
    print("=" * 60)

    # Redis ping test
    run_redis_ping_test(args.host, args.port)

    # Main benchmark
    try:
        env = QuakeLiveEnv(
            redis_host=args.host,
            redis_port=args.port,
            max_episode_steps=100000
        )

        benchmark = LatencyBenchmark(env)
        stats = benchmark.run_benchmark(num_samples=args.samples)
        benchmark.print_report(stats)

        # Throughput test
        run_action_throughput_test(env)

        env.close()

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        print("\nMake sure the Quake Live server is running.")


if __name__ == '__main__':
    main()
