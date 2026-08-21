# Kora logging — production tuning

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-aspect.md`,
`.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md`

## Contents

- [The cost model](#the-cost-model)
- [Async appender](#async-appender)
- [Controlling volume with levels](#controlling-volume-with-levels)
- [Suppressing large payloads](#suppressing-large-payloads)
- [Batch operations](#batch-operations)
- [Global MDC and pooled threads](#global-mdc-and-pooled-threads)

## The cost model

`@Log` is generated at compile time into a `*Aspect` subclass, so there is no reflection or runtime proxy on the call path. The dominant cost is **not** the aspect wrapper but:

1. Rendering arguments/result to strings (only happens when the logger level is enabled).
2. The log write itself (synchronous I/O blocks the calling thread).

Therefore: keep production loggers at `INFO` (boundary markers, no data rendering) and route everything through an async appender.

## Async appender

Wrap your appender with `ru.tinkoff.kora.logging.logback.KoraAsyncAppender`. Logback's stock `AsyncAppender` does not propagate Kora's MDC or structured arguments, so they would be lost in async output.

```xml
<appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="ru.tinkoff.kora.logging.logback.ConsoleTextRecordEncoder"/>
</appender>

<appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
    <appender-ref ref="STDOUT"/>
</appender>

<root level="INFO">
    <appender-ref ref="ASYNC"/>
</root>
```

For JSON output (Loki / ELK / Datadog), swap the encoder for one provided by the SLF4J/Logback module setup — see `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md`.

## Controlling volume with levels

`@Log` writes its entry/exit records at the annotation's level (`value`, default `INFO`). What is actually emitted is gated by the **logger level** of the class in `logback.xml`:

| Logger level | `@Log` output |
|--------------|---------------|
| `DEBUG` / `TRACE` | boundary markers + argument/result data |
| `INFO` | boundary markers only (`>` and `<`) |
| `WARN`+ | nothing |

```xml
<logger name="com.example.hotpath" level="INFO"/>   <!-- boundaries only -->
<logger name="com.example.service" level="DEBUG"/>  <!-- full data in staging -->
```

## Suppressing large payloads

Argument values are rendered to strings before being logged (when the level is enabled). For large objects, render the whole object only if you must — otherwise suppress it and log a cheap summary key instead:

```java
@Log
public Response upload(
    @Mdc(key = "fileName") String fileName,
    @Log.off byte[] fileData,             // never rendered or logged
    @Mdc(key = "fileSize") long fileSize  // cheap summary in MDC
) {
    // log carries fileName + fileSize, not the bytes
}
```

If a DTO is logged elsewhere, give it a compact `toString()` that emits identifiers and sizes rather than full contents.

## Batch operations

Annotating a per-item method produces one record per item — a log explosion. Log once at the batch boundary and keep the inner method silent:

```java
@Log
public void processBatch(List<Item> items) {
    for (Item item : items) {
        processItemInternal(item);
    }
}

@Log.off                                  // no entry/exit records per item
private void processItemInternal(Item item) { ... }
```

## Global MDC and pooled threads

`@Mdc(global = true)` keeps a key on the thread after the method returns. On HTTP/Kafka worker pools the same thread serves the next request, so an uncleared global key leaks across requests. Prefer method-scoped `@Mdc`. When a global key is unavoidable, remove it when the unit of work ends:

```java
MDC.remove("tenant");
```

There is no `MDC.clear()` in Kora's API — remove keys individually with the static `MDC.remove(key)`.

## See also

- [logging-aspect.md](logging-aspect.md) — `@Log` reference
- [logging-mdc.md](logging-mdc) — `@Mdc` and the imperative API
- Parent [SKILL.md](../SKILL.md)
