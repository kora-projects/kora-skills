# Async Logging Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md`

## Contents

- [KoraAsyncAppender](#koraasyncappender)
- [Parameters](#parameters)
- [How it works](#how-it-works)
- [Sizing guidelines](#sizing-guidelines)
- [Graceful shutdown](#graceful-shutdown)
- [Troubleshooting](#troubleshooting)

## KoraAsyncAppender

`ru.tinkoff.kora.logging.logback.KoraAsyncAppender` wraps another appender and flushes records on
a dedicated thread, so application threads do not block on log I/O. It extends Logback's
`AsyncAppenderBase`, and crucially carries Kora's structured `MDC` (and current span context)
through to the async record — Logback's stock `AsyncAppender` does not. Always use
`KoraAsyncAppender` when relying on Kora `MDC`.

The example apps wrap the inner appender with no parameters, which is sufficient for most
services:

```xml
<appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="ru.tinkoff.kora.logging.logback.ConsoleTextRecordEncoder"/>
</appender>

<appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
    <appender-ref ref="STDOUT"/>
</appender>
```

## Parameters

Because `KoraAsyncAppender` extends `AsyncAppenderBase`, it accepts the standard Logback async
settings. There is no `bufferSize`/`flushThreshold` option — use these:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `queueSize` | 256 | Capacity of the blocking event queue |
| `discardingThreshold` | 20% of `queueSize` | Below this remaining capacity, TRACE/DEBUG/INFO events are dropped; set `0` to never discard |
| `maxFlushTime` | 1000 | Max time (ms) to flush the queue on shutdown |
| `neverBlock` | false | If `true`, drop instead of block when the queue is full |
| `includeCallerData` | false | Capture caller class/method/line (performance cost) |

```xml
<appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
    <appender-ref ref="STDOUT"/>
    <queueSize>8192</queueSize>
    <discardingThreshold>0</discardingThreshold>   <!-- never drop -->
    <maxFlushTime>2000</maxFlushTime>
</appender>
```

## How it works

```
Application threads ──put──▶ blocking queue (queueSize) ──take──▶ worker thread ──▶ inner appender (I/O)
```

1. Application threads enqueue events (non-blocking until the queue is full).
2. A worker thread drains the queue into the wrapped appender.
3. With `discardingThreshold = 0`, no events are dropped; the producer blocks if the queue fills
   (unless `neverBlock = true`).

## Sizing guidelines

| Throughput | `queueSize` | `discardingThreshold` |
|-----------|-------------|------------------------|
| High (> 1000 logs/s) | 16384 | 0 |
| Standard (100–1000 logs/s) | 8192 | 0 |
| Low (< 100 logs/s) | default (256) | 0 |

Memory roughly scales with `queueSize × averageEventSize`. Reduce `queueSize` to cap memory.

## Graceful shutdown

`KoraAsyncAppender` flushes the queue on stop (bounded by `maxFlushTime`). Run the service through
`KoraApplication.run(...)` so Logback stops cleanly on graceful shutdown; otherwise queued events
can be lost.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Events dropped under load | Set `discardingThreshold` to `0` and/or increase `queueSize` |
| Application threads block on logging | Queue is full — increase `queueSize`, speed up the inner appender, or set `neverBlock` (accepting drops) |
| Logs lost on shutdown | Increase `maxFlushTime`; ensure shutdown goes through `KoraApplication.run(...)` |
| Structured MDC missing | Use `KoraAsyncAppender`, not Logback `AsyncAppender`, and Kora `MDC` |
| High memory | Lower `queueSize`; reduce event size |
