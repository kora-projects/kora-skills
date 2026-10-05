# `@Log` reference — Kora 2.0

Package: **`io.koraframework.logging.common.annotation`**
(`Log`, with nested `Log.in`, `Log.out`, `Log.result`, `Log.off`).
Runtime: `io.koraframework:logging-common`. Aspect generator: `logging-annotation-processor` (javac,
inside `annotation-processors`) or `logging-symbol-processor` (KSP, inside `symbol-processors`).

## Contents

- [Annotation shapes](#annotation-shapes)
- [Which annotations trigger the aspect](#which-annotations-trigger-the-aspect)
- [Level resolution](#level-resolution)
- [Record shape](#record-shape)
- [Rendering arguments and results](#rendering-arguments-and-results)
- [Java vs Kotlin](#java-vs-kotlin)
- [Return types the aspect rejects](#return-types-the-aspect-rejects)
- [Logger names and `logging.levels`](#logger-names-and-logginglevels)
- [Non-final / open, and what bypasses the aspect](#non-final--open-and-what-bypasses-the-aspect)

## Annotation shapes

Verbatim from `logging/logging-common/.../annotation/Log.java`:

```java
@AopAnnotation
@Target({METHOD, PARAMETER})
@Retention(RUNTIME)
public @interface Log {
    Level value() default Level.INFO;                       // org.slf4j.event.Level

    @AopAnnotation @Target(METHOD) @interface in     { Level value() default Level.INFO;  }
    @AopAnnotation @Target(METHOD) @interface out    { Level value() default Level.INFO;  }
    @AopPropagate  @Target(METHOD) @interface result { Level value() default Level.DEBUG; }
    @AopPropagate  @Target({PARAMETER, METHOD}) @interface off {}
}
```

Consequences that are easy to get wrong:

- The level attribute is **`value`**, so `@Log(Level.DEBUG)` — `@Log(level = …)` does not compile.
- `org.slf4j.event.Level` has only `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`. **There is no
  `Level.OFF`.**
- `@Log` has no `TYPE` target: it cannot be applied to a class to cover all its methods.
- `@Log.result` and `@Log.off` take **no** attributes other than `value` on `result`; `off` is a
  marker.

## Which annotations trigger the aspect

`LogAspect.getSupportedAnnotationClassNames()` returns exactly `{ @Log, @Log.in, @Log.out }` — and
those three are the ones marked `@AopAnnotation`. `@Log.result` and `@Log.off` are `@AopPropagate`:
they only modify a weave that something else started.

| Written on the method | Entry record | Exit record |
|---|---|---|
| `@Log` | yes | yes |
| `@Log.in` | yes | no |
| `@Log.out` | no | yes |
| `@Log.result` only | **no** | **no** — nothing is woven |
| `@Log.off` only | **no** | **no** — nothing is woven |
| `@Log.out` + `@Log.off` | no | yes, but with **no `out` payload** |

`@Log.off` on a *method* is therefore not an off switch for the method. It suppresses the result
payload only (`LogAspectUtils.logResultLevel` returns `null` when `@Log.off` is present). To stop a
method from being logged, delete its `@Log*` annotations.

## Level resolution

`LEVELS = [ERROR, WARN, INFO, DEBUG, TRACE]` — later entries are more verbose.

**Entry / exit level.** From `@Log.in` / `@Log.out` if present, otherwise from `@Log`, otherwise
`INFO`. Absent all three → that record is not produced at all.

**Argument level.** Each parameter is logged at `max(verbosity)` of:
- its own `@Log(<Level>)` if present, otherwise `DEBUG`, and
- the entry level.

So with a plain `@Log` (entry `INFO`) the arguments land at `DEBUG`: at `INFO` you see a bare `>`,
at `DEBUG` you see `> {"data":{…}}`. `@Log(Level.INFO)` on a single parameter raises just that one to
`INFO`. `@Log.off` on a parameter removes it from the payload entirely; if every parameter is
`@Log.off` (or there are none) the entry record has no marker at all.

**Result level.** `@Log.result(<Level>)` if present, otherwise `DEBUG`, clamped so it is never less
verbose than the exit level. `@Log.off` on the method sets it to "none".

The generated code guards each block with `logger.isXxxEnabled()` before building the marker, so a
disabled level costs a boolean check and renders nothing.

## Record shape

Two SLF4J messages: `>` on entry, `<` on exit, each optionally carrying an SLF4J `Marker` built by
`StructuredArgument.marker("data", …)`. Rendered by a Kora encoder (see
[kora-telemetry-logging](../../kora-telemetry-logging/SKILL.md)) the payload is JSON:

```
> {"data":{"id":"42","limit":"10"}}
< {"data":{"out":"OK"}}
```

Arguments are keyed by parameter name; the result is always keyed `out`. A `void` / `Unit` method
never gets an `out` payload. With the JSON encoder (`io.koraframework:logging-logback-json`) the
marker becomes the record's top-level `data` field and the message is `>` / `<`:
`{"…","message":">","data":{"id":"42","limit":"10"}}`.

**Exceptions.** The aspect wraps the call in `try/catch (Throwable)`. If `WARN` is enabled it logs
at **WARN** with `<` and a payload of `errorType` (canonical class name) and `errorMessage`; the
`Throwable` itself is passed to the logger only when `DEBUG` is also enabled. The exception is then
rethrown unchanged. The error record is emitted at WARN regardless of the annotation's level.

## Rendering arguments and results

For each logged parameter and for the result the aspect asks the graph for an **optional**
`StructuredArgumentMapper<T>` constructor parameter (declared `@Nullable`). When no mapper is bound,
the generated code falls back to `gen.writeStringProperty(name, String.valueOf(value))` — the value's
`toString()`, as a JSON string. That is why `@Log` works with no JSON setup at all.

Three ways to change what is written:

| Written on the parameter / method | Mapper used | Payload |
|---|---|---|
| nothing | none, or a `StructuredArgumentMapper<T>` bound in the graph | `"name":"<toString()>"` |
| `@Json` | `LoggingModule.jsonStructuredArgumentMapper` (`@Json`-tagged) over the type's `JsonWriter<T>` | nested JSON object |
| `@Mapping(MyMapper.class)` | your `StructuredArgumentMapper<T>` implementation | whatever it writes |
| `@Mask` (± `@Json`) | `MaskedStructuredArgumentMapper<T>` | see [logging-masking.md](logging-masking.md) |

Only `@Mask` / `MaskingRules<T>` masks `@Log` payloads. The transport `DataMasker`s and tagged
`MaskingStrategy`s from [logging-masking.md](logging-masking.md#four-masking-layers) never see them.

`@Json` is `io.koraframework.json.common.annotation.Json` and is itself a `@Tag`, so it selects the
JSON-flavoured mapper. Using it requires `JsonModule` (`io.koraframework.json.common.JsonModule`) in
the `@KoraApp` and `@Json` on the logged type so a `JsonWriter<T>` exists.

A custom mapper is an ordinary component:

```java
public final class TokenLogMapper implements StructuredArgumentMapper<String> {
    @Override
    public void write(JsonGenerator gen, String value) {
        gen.writeString(value.substring(0, 4) + "…");
    }
}
```

```java
@Log.in
public void refresh(@Mapping(TokenLogMapper.class) String token) { ... }
```

`StructuredArgumentMapper` lives in `io.koraframework.logging.common.arg` and writes into a Jackson 3
`tools.jackson.core.JsonGenerator` — not `com.fasterxml.jackson.core`.

## Java vs Kotlin

Kotlin syntax notes:

- `in` is a Kotlin keyword: write ``@Log.`in` ``. `@Log.out`, `@Log.result`, `@Log.off` need no
  backticks.
- The class **and** the function must be `open`.
- Levels: `import org.slf4j.event.Level` then `@Log(Level.DEBUG)`.

```kotlin
import io.koraframework.logging.common.annotation.Log
import org.slf4j.event.Level

@Component
open class UserService(private val repository: UserRepository) {

    @Log
    open fun getUser(id: String): User = repository.findById(id)

    @Log.`in`(Level.DEBUG)
    open fun refresh(@Log.off token: String) { ... }
}
```

Two verified behavioural divergences between the two processors — avoid them by putting the level on
exactly one annotation:

| Case | Java (`LogAspectUtils`) | Kotlin (`LogKoraAspect`) |
|---|---|---|
| `@Log(A)` **and** `@Log.in(B)` on the same method | entry level `B` (the specific annotation wins) | entry level `A` (`@Log` wins) |
| `@Log.in` + `@Log.result(L)` | no exit record | an exit record **is** produced, at level `L` |

Kotlin `Flow` returns take a separate path in the Kotlin aspect: the stream is wrapped with
`onStart` (entry), `onEach` (per element) and `onCompletion` (exit/error) instead of the record being
tied to the function call. Kora 2.0 has no `Flow` contracts, so this only concerns your own code and
requires `org.jetbrains.kotlinx:kotlinx-coroutines-core`.

## Return types the aspect rejects

The Java aspect fails the build for a method returning a Reactive Streams `Publisher`
(Reactor `Mono`/`Flux`) or a `Future`:

```
@Log can't be applied for type org.reactivestreams.Publisher
```

`@Mdc` additionally rejects `CompletionStage`. The Java `@Log` aspect still contains a
`CompletionStage` branch, but **Kora 2.0 has no asynchronous contracts** — repositories, controllers
and HTTP clients are synchronous on virtual threads — so annotate synchronous methods.

## Logger names and `logging.levels`

The logger is named `<fully-qualified enclosing class>.<methodName>`:

```java
package com.example;
public class UserService {
    @Log public User getUser(String id) { ... }   // logger "com.example.UserService.getUser"
}
```

Because Logback's hierarchy is dot-separated, a level set on `com.example.UserService` (or
`com.example`) is inherited by every method logger under it.

Levels are configured under the `logging.levels` map read by
`io.koraframework.logging.common.LoggingConfig`:

```java
@ConfigMapper
public interface LoggingConfig {
    default Map<String, String> levels() { return Map.of(); }
}
```

```hocon
logging {
  levels {
    "ROOT": "WARN"
    "io.koraframework": "INFO"
    "com.example.UserService": "DEBUG"
    "com.example.UserService.getUser": "TRACE"
  }
}
```

Three things to remember:

1. The key is `levels` (plural). `logging.level` is an unknown key, ignored without a warning.
2. Dotted logger names must be **quoted** in HOCON, or they nest into objects and match nothing.
3. `LoggingLevelRefresher` is a `@Root` `Lifecycle`. Its `init()` calls
   `LoggingLevelApplier.reset()` — which sets `ROOT` to `INFO` and clears every other logger's level
   — and only then applies `logging.levels`. **Per-logger levels written in `logback.xml` do not
   survive graph initialisation.** Configure them in `logging.levels`.

`LoggingLevelApplier` is supplied by `LogbackModule` only. A `@KoraApp` that extends bare
`LoggingModule` without a Logback backend fails to build the graph for want of that component.

## Non-final / open, and what bypasses the aspect

The generated `$<Class>__AopProxy` extends your class and calls `super`, so:

- Java: neither the class nor the annotated method may be `final`; the class needs a public,
  protected or package-private constructor. Errors are explicit, e.g.
  `AOP aspect cannot be applied to class '…' because the class is final.`
- Kotlin: the class and the function must be `open`, and the class must not be abstract. KSP reports
  `AOP aspect cannot be applied to class '…' because the class is not open.` — the aspect is never
  silently skipped in 2.0.
- Top-level Kotlin functions cannot be woven at all.

Bypasses, both inherent to subclass proxying:

- **Self-invocation.** `this.annotatedMethod()` inside the same object runs the `super`
  implementation; the aspect only wraps calls made through the proxy instance.
- **Manual construction.** `new UserService(...)` produces an unproxied object. Let the DI graph
  build the component.

## See also

- [logging-mdc.md](logging-mdc.md) — `@Mdc` and the MDC runtime model
- [logging-masking.md](logging-masking.md) — `@Mask`, strategies and rules
- [logging-performance.md](logging-performance.md) — cost model and volume control
- Parent [SKILL.md](../SKILL.md)
