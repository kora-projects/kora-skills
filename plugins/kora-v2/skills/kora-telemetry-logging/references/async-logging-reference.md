# KoraAsyncAppender Reference

## Contents

- [What it is and why it is not optional](#what-it-is-and-why-it-is-not-optional)
- [What append() actually does](#what-append-actually-does)
- [Configuration](#configuration)
- [discardingThreshold drops TRACE/DEBUG/INFO near a full queue](#discardingthreshold-drops-tracedebuginfo-near-a-full-queue)
- [Caller data is unavailable](#caller-data-is-unavailable)
- [Serialisation happens on the appender thread](#serialisation-happens-on-the-appender-thread)
- [Shutdown](#shutdown)
- [Troubleshooting](#troubleshooting)

## What it is and why it is not optional

```java
public final class KoraAsyncAppender extends AsyncAppenderBase<ILoggingEvent> { … }
```

`io.koraframework.logging.logback.KoraAsyncAppender` wraps another appender and hands events to a
worker thread, so application threads do not block on log I/O. That is the ordinary
`AsyncAppenderBase` job. What makes it **required rather than an optimisation** is that it is the
only thing that produces a `KoraLoggingEvent`:

- the Kora `MDC` snapshot (`koraMdc()`), and
- the current OpenTelemetry span context (`span()`)

exist **only** on `KoraLoggingEvent`. Without `KoraAsyncAppender` in the chain,
`ConsoleTextRecordEncoder` receives a plain `ILoggingEvent`, and `traceId`, `spanId` and every Kora
MDC value are absent from the line. Logback's stock `ch.qos.logback.classic.AsyncAppender` does not
substitute for it — it produces no `KoraLoggingEvent` either.

Every migrated example app wraps its console appender with it, in `logback.xml` and
`logback-test.xml` alike.

## What `append()` actually does

```java
@Override
protected void append(ILoggingEvent eventObject) {
    var koraLoggingEvent = new KoraLoggingEvent(
        eventObject.getThreadName(), eventObject.getLoggerName(), …,
        eventObject.getKeyValuePairs(),
        MDC.VALUE.isBound() ? Map.copyOf(MDC.get().values()) : Map.of(),
        Span.current().getSpanContext()
    );
    super.append(koraLoggingEvent);
}
```

Two things to take from this:

1. The MDC and span are captured **eagerly, on the logging thread**, before the event is queued.
   That is what makes them survive the hop to the appender thread.
2. The `MDC.VALUE.isBound()` guard matters: an event logged outside any request/message/job scope
   has no MDC bound, and reading an unbound `ScopedValue` would throw inside the appender and
   silently drop the event. Copy the guard into your own appender/encoder code.

## Configuration

`KoraAsyncAppender` accepts the elements `ch.qos.logback.core.AsyncAppenderBase` declares, but its
constructor replaces Logback's defaults with its own, each also settable through a system property
or an environment variable (`KoraLogbackProperties`: system property first, then the variable). A
value set in `logback.xml` overrides both.

| Element | Kora default | System property / environment variable | Effect |
|---|---|---|---|
| `queueSize` | `512` | `kora.logging.config.queue-size` / `KORA_LOGGING_CONFIG_QUEUE_SIZE` | Capacity of the `ArrayBlockingQueue` between the logging threads and the worker |
| `neverBlock` | **`true`** | `kora.logging.config.never-block` / `KORA_LOGGING_CONFIG_NEVER_BLOCK` | `true` → an event that does not fit is **dropped** (`offer`); `false` → the logging thread blocks until there is room |
| `maxFlushTime` | `1000` ms | `kora.logging.config.max-flush-time` / `KORA_LOGGING_CONFIG_MAX_FLUSH_TIME` (`1s`, `500ms`, `PT1S`; a bare number is ms) | Time budget for draining the queue on `stop()` |
| `discardingThreshold` | `queueSize / 5` | `kora.logging.config.discarding-threshold` / `KORA_LOGGING_CONFIG_DISCARDING_THRESHOLD` | Once fewer than this many slots remain, `TRACE`/`DEBUG`/`INFO` events are dropped; `WARN`/`ERROR` still queue. `0` never drops by level — see below |

An invalid value (`queue-size=0`, `max-flush-time=soon`, `never-block=yes`) falls back to the
default and is reported as a Logback warning when the appender starts.

```xml
<appender name="ASYNC" class="io.koraframework.logging.logback.KoraAsyncAppender">
    <appender-ref ref="STDOUT"/>
    <queueSize>8192</queueSize>
    <neverBlock>false</neverBlock>
</appender>
```

The defaults favour the application over the log: under a burst larger than the queue, records are
lost rather than request threads stalled. If every record must be kept, set `discardingThreshold`
to `0`, `neverBlock` to `false` and size `queueSize` for the burst; memory is roughly `queueSize × average event size`.

The same appender, with the same defaults, is what `KoraLogbackConfigurator` installs (named
`KORA_ASYNC`) when there is no `logback.xml`.

## `discardingThreshold` drops TRACE/DEBUG/INFO near a full queue

`AsyncAppenderBase.append` is

```java
protected void append(E eventObject) {
    if (isQueueBelowDiscardingThreshold() && isDiscardable(eventObject)) return;
    preprocess(eventObject);
    put(eventObject);
}
```

Since 2.0.0.RC2 (#958) `KoraAsyncAppender` overrides `isDiscardable` the way
`ch.qos.logback.classic.AsyncAppender` does:

```java
@Override
protected boolean isDiscardable(ILoggingEvent event) {
    return event.getLevel().toInt() <= Level.INFO_INT;
}
```

So when the remaining capacity drops below `discardingThreshold` (default `queueSize / 5`, i.e. ~102
of 512), `TRACE`, `DEBUG` and `INFO` events are silently skipped while `WARN` and `ERROR` still
queue. Set `<discardingThreshold>0</discardingThreshold>` (or the property / variable) to never drop
by level. (In RC1 the base `isDiscardable` returned `false`, so the threshold had no effect.) Once
the queue is completely full, `neverBlock` decides between dropping and blocking for every level.

## Caller data is unavailable

`KoraLoggingEvent` is a record whose caller-data accessors are hard-coded:

```java
@Override public StackTraceElement[] getCallerData() { return null; }
@Override public boolean hasCallerData()            { return false; }
```

Consequently `%class`, `%method`, `%line`, `%file` and `%caller` cannot be rendered for any event
that passed through `KoraAsyncAppender`, and `AsyncAppenderBase` declares no `includeCallerData`
property to turn it on. If you need caller data for a specific diagnostic, log through an appender
chain that bypasses `KoraAsyncAppender` — and accept that such records lose `traceId`/`spanId` and
Kora MDC.

## Serialisation happens on the appender thread

The event captures *references*: `getArgumentArray()`, `getMarkerList()`, `getKeyValuePairs()` and
the `koraMdc` writers are all invoked later, by the encoder, on the worker thread. The rendered
message string (`getFormattedMessage()`) is captured eagerly, but a `StructuredArgumentWriter`
lambda is not.

Pass immutable snapshots into structured arguments. A lambda that closes over a mutable builder or
an entity that the request goes on to modify will serialise whatever the object looks like when the
appender thread gets to it, not when the log call was made.

## Shutdown

`AsyncAppenderBase.stop()` drains the queue within `maxFlushTime` (Kora default one second; `0`
waits as long as the output takes). Run the service through `KoraApplication.run(...)` so the graph
shuts down cleanly and Logback stops; a hard kill loses whatever is still queued. If tail-end
records are missing from a container's logs, raise `maxFlushTime` before suspecting the appender.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `traceId` / `spanId` / Kora MDC missing | The appender chain does not include `KoraAsyncAppender`, or the encoder ignores `KoraLoggingEvent` |
| Records of every level missing under load | `neverBlock` is `true` by default, so a full queue drops events — raise `queueSize`, or set `neverBlock` to `false` to block instead |
| Logging threads block under load | `neverBlock` was set to `false` and the queue is full — raise `queueSize` or make the inner appender faster |
| `INFO` records missing under load while `WARN`/`ERROR` survive | Level-based discarding below `discardingThreshold` (default `queueSize / 5`) — set it to `0`, or raise `queueSize` |
| `%class` / `%method` / `%line` render as `?` | Caller data is disabled at the event level, by design |
| Records lost at shutdown | Raise `maxFlushTime`; shut down through `KoraApplication.run(...)` |
| A logged object shows post-mutation state | The writer lambda ran on the appender thread — pass an immutable snapshot |
| High memory attributable to logging | Lower `queueSize`, or reduce event size (fewer/smaller structured fields) |
