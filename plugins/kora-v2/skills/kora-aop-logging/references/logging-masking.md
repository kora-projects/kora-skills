# Masking in Kora 2.0 — the shared model

This is the **canonical masking page** of the package. Transport skills (HTTP server/client, gRPC,
Kafka) document their own config keys and link here for the model.

Packages (artifact `io.koraframework:logging-common`, transitive through `logging-logback`):

- `io.koraframework.logging.common.annotation.Mask`
- `io.koraframework.logging.common.masking` — `MaskingStrategy`, `MaskingFull`, `MaskingKeepFirst`,
  `MaskingKeepLast`, `MaskingPathRules`, `MaskingRules`
- `io.koraframework.logging.common.masking.raw` — `DataMasker`, `JsonDataMasker`, `XmlDataMasker`,
  `FormUrlencodedDataMasker`

To drop a value from a `@Log` record entirely, use `@Log.off` on the parameter instead of masking
it; see [logging-aspect.md](logging-aspect.md).

## Contents

- [Four masking layers](#four-masking-layers)
- [Shared building blocks](#shared-building-blocks)
- [`@Mask` — typed values](#mask--typed-values)
- [Java and Kotlin both generate the rules](#java-and-kotlin-both-generate-the-rules)
- [`DataMasker` — raw payloads](#datamasker--raw-payloads)
- [How a component picks its masker: tagged strategies](#how-a-component-picks-its-masker-tagged-strategies)
- [The JSON encoder's `<maskField>`](#the-json-encoders-maskfield)
- [Pitfalls](#pitfalls)

## Four masking layers

A value can be masked at four points on its way to the log. They are independent: each covers
something the others cannot see.

| Layer | Masks | Applied when | Rules come from | Default |
|---|---|---|---|---|
| **`@Mask` / `MaskingRules<T>`** | fields of a typed object logged as a structured argument (`@Log` arguments/results, `MaskedStructuredArgumentMapper`) | while the object is serialised through its `JsonWriter<T>` | `@Mask` on the type and fields, or a hand-built `MaskingRules<T>` | nothing masked until you annotate |
| **`DataMasker`** | a raw payload — HTTP server/client request and response bodies, Kafka consumer record key/value | before the payload bytes become the logged string | `MaskingPathRules` you build and register as a component tagged for the transport | **none registered** — payloads are logged as-is |
| **Tagged `MaskingStrategy`** | values of the header / query parameter / metadata names listed in the transport's `maskHeaders` (and `maskQueries` for HTTP) | when the transport writes headers/query into its telemetry record | config lists the names; a `MaskingStrategy` component tagged for the transport produces the replacement | `value -> "***"`; `maskHeaders` defaults to `authorization`, `cookie`, `set-cookie` |
| **`JsonRecordEncoder` `<maskField>`** | any JSON field with a given name in the final log line | when the Logback JSON encoder writes the record | `logback.xml` | none; JSON encoder only |

How they relate:

- `@Mask` and `DataMasker` share the **rule syntax** (`MaskingPathRules`) and the
  **`MaskingStrategy`** contract, but not their input. `@Mask` works on a Java object whose type is
  known at compile time; a `DataMasker` works on bytes of unknown shape and validity. `@Mask` never
  touches a transport body, and a `DataMasker` never touches a `@Log` argument.
- The tagged `MaskingStrategy` is the same interface as the `@Mask` strategies, used as a plain
  "value → replacement" function for header, query and metadata values.
- `<maskField>` runs last, on the finished JSON record, by field name only. It cannot see inside a
  string — a body or `headers` string that reached the record unmasked stays unmasked. Mask at the
  source first.

## Shared building blocks

### `MaskingStrategy`

```java
public interface MaskingStrategy {
    String mask(Object value);
}
```

| Built-in | Output for `"secret"` | Constructor |
|---|---|---|
| `MaskingFull` (default) | `***` | `()`, `(String replacement)` |
| `MaskingKeepFirst` | `secr***` | `()`, `(String replacement, int keep)` — defaults `***`, 4 |
| `MaskingKeepLast` | `***cret` | `()`, `(String replacement, int keep)` — defaults `***`, 4 |

`LoggingModule` binds all three as untagged `@DefaultComponent`s (used by `@Mask`). What the
strategy receives depends on the layer: the scalar the `JsonWriter` was about to emit (`@Mask`),
the raw text of the value as a `String` (`DataMasker`, or `null` for an object/array replaced as a
whole), or one header/query value (tagged transport strategy).

### Rule syntax (`MaskingPathRules`)

`MaskingPathRules.builder().mask(fieldOrPath, strategy).build()` — `MaskingRules.builder(T.class)`
is the same builder with the logged type attached.

| Rule | Matches |
|---|---|
| `password` | every field named `password`, at any depth |
| `user.password` | `password` reached through `user`, counted **from the root** of the payload (not under an envelope such as `{"a":{"user":…}}`) |
| `users.*.password` | `*` matches exactly one segment — map values, dynamic keys |

Array and collection elements add no segment: `items.password` matches
`{"items":[{"password":"…"}]}`. Path rules are checked before field-name rules.

## `@Mask` — typed values

This is *partial* redaction of a typed object: it is still logged, some of its JSON fields are
replaced.

### Annotation shape

```java
@Target({TYPE, PARAMETER, FIELD, RECORD_COMPONENT, METHOD, TYPE_USE})
@Retention(RUNTIME)
public @interface Mask {
    Class<? extends MaskingStrategy> value() default MaskingFull.class;
}
```

### The two roles of `@Mask`

`@Mask` does different work depending on where it sits, and a working setup needs both.

**1. On the logged element** — the `@Log` parameter or the `@Log`-annotated method. This switches the
aspect from `StructuredArgumentMapper<T>` to `MaskedStructuredArgumentMapper<T>`, which writes the
value through a `MaskingJsonGenerator`.

**2. On the type and its fields** — this is where the rules come from. The type must be a class or a
record annotated `@Json` (so a `JsonWriter<T>` exists) and `@Mask`; each field or record component
that must be redacted carries its own `@Mask`.

Both are required. `@Mask` on the parameter alone gives you a masked mapper with no rules; `@Mask` on
the type alone changes nothing about how the argument is logged.

### Worked example

```java
@Mask(MaskingKeepFirst.class)          // default strategy for masked fields of this type
@Json
public record Credentials(
    @Mask String secret,               // MaskingKeepFirst, inherited from the type
    @Mask(MaskingKeepLast.class) String token,
    String login                       // not masked
) {}
```

```java
@Mask
@Json
public record User(String name, Credentials credentials) {}
```

```java
@Component
public class AuthService {                       // non-final

    @Log.in
    public void authenticate(@Mask @Json User user) { ... }
}
```

Payload written on entry (verified in `LogAspectTest#testLogArgsWithMaskingMapper`, with
`MaskingKeepFirst("###", 2)` and `MaskingKeepLast("!!!", 3)` bound):

```json
{"arg1":{"name":"user","credentials":{"secret":"se###","token":"!!!ken","login":"login"}}}
```

Kotlin is the same shape:

```kotlin
@Mask(MaskingKeepLast::class)
@Json
data class Credentials(@Mask val secret: String, val login: String)

@Component
open class AuthService {
    @Log.`in`
    open fun authenticate(@Mask @Json user: User) { ... }
}
```

### Strategies

The built-ins are listed under [`MaskingStrategy`](#maskingstrategy). With `@Mask`, `mask` receives
the scalar the JSON writer was about to emit (`String`, `Boolean`, `Number`, `BigInteger`,
`BigDecimal`, `byte[]`), or the source object for an object/array matched as a whole. JSON `null`
is never masked. Map **keys** are never masked as values.

All three are bound by `LoggingModule` as `@DefaultComponent`s built with their no-arg constructors.
Override the settings by declaring your own component of the same concrete type — `@DefaultComponent`
yields to a user-supplied one:

```java
@Module
public interface MaskingTuningModule {
    default MaskingKeepLast maskingKeepLast() { return new MaskingKeepLast("***", 2); }
}
```

A custom strategy is an ordinary component; the generated rules module takes it as a constructor
parameter, so it must be resolvable from the graph:

```java
@Component
public final class LastFourDigits implements MaskingStrategy {
    @Override public String mask(Object value) { return "**** " + value.toString().substring(12); }
}
```

```java
@Mask @Json
public record Card(@Mask(LastFourDigits.class) String pan) {}
```

### Generated rules

For every class or record annotated `@Mask`, the processor emits a `@Module` interface named
`$<Type>_MaskingRulesModule` with a `@DefaultComponent` factory:

```java
@Module
public interface $User_MaskingRulesModule {
    @DefaultComponent
    default MaskingRules<User> userMaskingRules(MaskingKeepFirst strategy0, MaskingKeepLast strategy1) {
        return MaskingRules.builder(User.class)
            .mask("credentials.secret", strategy0)
            .mask("credentials.token", strategy1)
            .build();
    }
}
```

`@Module` interfaces are discovered automatically across the compilation — do **not** add the
generated module to the `@KoraApp` `extends` clause.

How the processor walks the type:

- It descends only into field types that are themselves annotated `@Json`, `@JsonWriter` or `@Mask`.
- `@JsonField("name")` renaming and the type's naming strategy are honoured; `@JsonSkip` fields are
  ignored.
- Collections and arrays contribute **no** path segment; `Map` values contribute a `*` segment.
- Recursive types terminate (a type already on the current branch is not revisited).
- A field's strategy is: the field's own `@Mask(X)`, else the enclosing type's `@Mask(X)`, else
  `MaskingFull`.
- Only concrete classes and records qualify. An interface gives
  `Only classes and records can be annotated with @Mask`; an abstract class gives
  `Abstract classes can't be annotated with @Mask`.

### Rule matching

`MaskingRules<T>` extends `MaskingPathRules`, so the syntax is the shared one from
[Rule syntax](#rule-syntax-maskingpathrules). `strategy(path, fieldName)` checks path rules first,
then field rules, comparing names exactly (case-sensitive) because they are the names the
`JsonWriter` emits:

| Rule string | Matches |
|---|---|
| `password` | any JSON field named `password`, at any depth |
| `user.password` | `password` reached through `user`, counted from the logged root |
| `users.*.password` | one dynamic segment — the value objects of a `Map` |

Build them by hand with the public API:

```java
MaskingRules<User> rules = MaskingRules.builder(User.class)
    .mask("password", new MaskingFull())
    .mask("credentials.token", new MaskingKeepLast())
    .build();
```

or with the map constructor: `new MaskingRules<>(User.class, Map.of("token", strategy))`.

### Structured vs stringified output

`MaskedStructuredArgumentMapper<T>` has a `structured` flag, and the aspect sets it from whether the
logged element also carries `@Json`:

| On the parameter / method | Payload |
|---|---|
| `@Mask @Json` | nested JSON object: `{"arg1":{"name":"user","token":"***"}}` |
| `@Mask` only | the masked JSON as one escaped string: `{"arg1":"{\"name\":\"user\",\"token\":\"***\"}"}` |

Prefer `@Mask @Json` — a nested object is what a log aggregator can index.

### Custom rules with `@Mapping`

Point a single logged element at your own rules by subclassing `MaskingRules<T>` and selecting it
with `@Mapping` (`io.koraframework.common.annotation.Mapping`):

```java
public final class CustomRules extends MaskingRules<User> {
    public CustomRules() {
        super(User.class, Map.of("token", value -> "rules-" + value));
    }
}
```

```java
@Log.in
public void handle(@Mask @Json @Mapping(CustomRules.class) User user) { ... }
```

The aspect then constructs `new MaskedStructuredArgumentMapper<>(jsonWriter, customRules, hasJson)`
directly, so `CustomRules` and a `JsonWriter<User>` must both be resolvable from the graph.

## Java and Kotlin both generate the rules

Verified against the framework source at `2.0.0.RC2`:

- `logging-symbol-processor` registers `MaskingRulesSymbolProcessorProvider` (KSP).
- `logging-annotation-processor` registers `LoggingAnnotationProcessor` in
  `META-INF/services/javax.annotation.processing.Processor` (#921, RC2), and it runs
  `MaskingRulesProcessor`; since #970 it is also declared an **isolating** Gradle incremental
  processor, so incremental compilation stays on. `io.koraframework:annotation-processors` depends on
  it, so the usual `annotationProcessor "io.koraframework:annotation-processors"` line is enough.

So **both languages generate `$<Type>_MaskingRulesModule`**; no hand-written `MaskingRules<T>` is
needed. In 2.0.0.RC1 the Java service entry was missing, the module was never generated and the graph
failed on an unresolved `MaskingRules<User>` — if you meet a hand-written
`MaskingRules.builder(User.class)…` `@Module` from that era, delete it, or it competes with the
generated `@DefaultComponent` (yours, being non-default, wins and silently ignores later `@Mask`
edits). Declaring `MaskingRules<T>` by hand is still legitimate for a type you cannot annotate.

## `DataMasker` — raw payloads

```java
public interface DataMasker {
    Charset DEFAULT_CHARSET = StandardCharsets.UTF_8;
    String format();                                   // "json", "xml", "form-urlencoded"
    default String mask(byte[] content) { … }          // as UTF-8
    String mask(byte[] content, @Nullable Charset charset);
}
```

A `DataMasker` is a **soft parser over bytes**: it walks the payload once, copying it to the output
and replacing matched values, never builds a document and **never throws**. It is stateless and
safe to share.

| Implementation | `format()` | Constructors | What a rule matches |
|---|---|---|---|
| `JsonDataMasker` | `json` | `(MaskingPathRules)`, `(rules, int maxDepth, int maxLength)` — defaults 64, 64 KiB | object field values; an object/array value is replaced as a whole; a masked value is written as a JSON string (`"secret":1` → `"secret":"***"`) |
| `XmlDataMasker` | `xml` | `(MaskingPathRules)`, `(rules, int maxDepth, int maxLength)` — defaults 64, 64 KiB | element text **and** attribute values (`<password>…</password>` and `<user password="…"/>`); namespace prefixes are ignored |
| `FormUrlencodedDataMasker` | `form-urlencoded` | `(MaskingPathRules)`, `(rules, int maxLength)` — default 64 KiB | parameter values by name; names are percent-decoded before matching (`pass%77ord`) |

Behaviour shared by all three:

- **Fail closed.** As soon as the scanner loses track of the structure, everything after that
  point is replaced by a marker instead of being copied: `<masked:unparseable>` (JSON),
  `<!--masked:unparseable-->` (XML). An HTML error page sent as `application/json` becomes just
  `<masked:unparseable>`; an empty JSON payload too. The form masker is flat, so damage stays local:
  an undecodable parameter name gets its value masked and scanning resumes at the next `&`.
- **Length limit.** Output stops at `maxLength` bytes and ends with `<masked:truncated>`
  (`<!--masked:truncated-->` for XML); a huge payload costs the limit, not its own size.
- **Names match case-insensitively** for ASCII letters (`Password` matches rule `password`) —
  unlike `@Mask`, whose names come from your own `JsonWriter`.
- **Charset.** The payload is scanned in the transport's declared charset (UTF-8 when unknown);
  UTF-16-style encodings are re-encoded to UTF-8 first.
- A `MaskingStrategy` that throws, or returns `null`, falls back to `***`. For an object/array
  replaced as a whole the strategy receives `null`, so `MaskingKeepFirst`/`MaskingKeepLast` fall
  back to `***` there.

```java
var masker = new JsonDataMasker(MaskingPathRules.builder()
    .mask("password", new MaskingFull())
    .mask("card.number", new MaskingKeepLast())
    .build());

masker.mask("{\"login\":\"anton\",\"password\":\"secret\"}".getBytes(StandardCharsets.UTF_8));
// {"login":"anton","password":"***"}
```

## How a component picks its masker: tagged strategies

Each transport module declares its masking inputs as graph dependencies **tagged with its telemetry
class**, with a `@DefaultComponent` fallback where one exists:

- `@Tag(<Telemetry>.class) MaskingStrategy` — default `value -> "***"`; replaces the values of the
  names listed in `maskHeaders` / `maskQueries`.
- `@Tag(<Telemetry>.class) All<DataMasker>` — every `DataMasker` component carrying that tag; the
  transport's body converter indexes them by `format()` and picks one per payload. Empty by default.

| Transport | Tag class | Name lists in config | `DataMasker` used for | Masker picked by |
|---|---|---|---|---|
| HTTP server | `io.koraframework.http.server.common.telemetry.HttpServerTelemetry` | `maskHeaders`, `maskQueries` | request and response bodies | `Content-Type`: `application/x-www-form-urlencoded` → `form-urlencoded`, `*/json` and `*+json` → `json`, `*/xml` and `*+xml` → `xml` |
| HTTP client | `io.koraframework.http.client.common.telemetry.HttpClientTelemetry` | `maskHeaders`, `maskQueries` | request and response bodies | same `Content-Type` rule |
| gRPC server | `io.koraframework.grpc.server.telemetry.GrpcServerTelemetry` | `maskHeaders` (metadata) | — | — |
| gRPC client | `io.koraframework.grpc.client.telemetry.GrpcClientTelemetry` | `maskHeaders` (metadata) | — | — |
| Kafka listener | `io.koraframework.kafka.common.consumer.telemetry.KafkaConsumerTelemetry` | `maskHeaders` | record key and value (logged at `TRACE`) | the `json` masker, only when that side's deserializer is Kora's `JsonKafkaDeserializer` |
| Kafka publisher | `io.koraframework.kafka.common.producer.telemetry.KafkaPublisherTelemetry` | `maskHeaders` | — (key and value are never logged) | — |

When no masker matches, the payload is logged as it is. Registering maskers — one per format per
transport tag (a second one with the same `format()` replaces the first, in no defined order):

===! "Java"

    ```java
    import io.koraframework.common.annotation.Module;
    import io.koraframework.common.annotation.Tag;
    import io.koraframework.http.server.common.telemetry.HttpServerTelemetry;
    import io.koraframework.logging.common.masking.MaskingFull;
    import io.koraframework.logging.common.masking.MaskingKeepLast;
    import io.koraframework.logging.common.masking.MaskingPathRules;
    import io.koraframework.logging.common.masking.MaskingStrategy;
    import io.koraframework.logging.common.masking.raw.DataMasker;
    import io.koraframework.logging.common.masking.raw.FormUrlencodedDataMasker;
    import io.koraframework.logging.common.masking.raw.JsonDataMasker;

    @Module
    public interface TelemetryMaskingModule {

        static MaskingPathRules sensitiveFields() {
            return MaskingPathRules.builder()
                .mask("password", new MaskingFull())
                .mask("card.number", new MaskingKeepLast())
                .build();
        }

        @Tag(HttpServerTelemetry.class)
        default DataMasker httpServerJsonMasker() {
            return new JsonDataMasker(sensitiveFields());
        }

        @Tag(HttpServerTelemetry.class)
        default DataMasker httpServerFormMasker() {
            return new FormUrlencodedDataMasker(sensitiveFields());
        }

        @Tag(HttpServerTelemetry.class)
        default MaskingStrategy httpServerHeaderMasking() {
            return new MaskingKeepLast();
        }
    }
    ```

=== "Kotlin"

    ```kotlin
    import io.koraframework.common.annotation.Module
    import io.koraframework.common.annotation.Tag
    import io.koraframework.http.server.common.telemetry.HttpServerTelemetry
    import io.koraframework.logging.common.masking.MaskingFull
    import io.koraframework.logging.common.masking.MaskingKeepLast
    import io.koraframework.logging.common.masking.MaskingPathRules
    import io.koraframework.logging.common.masking.MaskingStrategy
    import io.koraframework.logging.common.masking.raw.DataMasker
    import io.koraframework.logging.common.masking.raw.FormUrlencodedDataMasker
    import io.koraframework.logging.common.masking.raw.JsonDataMasker

    private val sensitiveFields: MaskingPathRules = MaskingPathRules.builder()
        .mask("password", MaskingFull())
        .mask("card.number", MaskingKeepLast())
        .build()

    @Module
    interface TelemetryMaskingModule {

        @Tag(HttpServerTelemetry::class)
        fun httpServerJsonMasker(): DataMasker = JsonDataMasker(sensitiveFields)

        @Tag(HttpServerTelemetry::class)
        fun httpServerFormMasker(): DataMasker = FormUrlencodedDataMasker(sensitiveFields)

        @Tag(HttpServerTelemetry::class)
        fun httpServerHeaderMasking(): MaskingStrategy = MaskingKeepLast()
    }
    ```

Repeat with `HttpClientTelemetry` / `KafkaConsumerTelemetry` for the other transports — a masker
is only seen by the transport whose tag it carries. Keep the shared rule set a plain value (a static
helper, a top-level `val`) rather than an untagged `MaskingPathRules` component: every generated
`MaskingRules<T>` is also a `MaskingPathRules`, so such a dependency can become ambiguous.

For finer selection, the transport's body converter (`DefaultHttpServerBodyConverter`,
`DefaultHttpClientBodyConverter`, `DefaultKafkaConsumerBodyConverter`) is a `@DefaultComponent`
with protected `select…DataMasker(…)` methods that receive the request/response/record; subclass it
and provide your subclass as the component. Transport-specific details — log levels at which bodies
appear, body size limits — live in each transport skill.

## The JSON encoder's `<maskField>`

`io.koraframework.logging.logback.json.JsonRecordEncoder` (artifact
`io.koraframework:logging-logback-json`) accepts `<maskField>name</maskField>` in `logback.xml`
(or a custom `LoggingEventJsonMasker` via `<masker class="…"/>`). Every JSON field with that name —
case-insensitive, at any depth of the record — is written as `"***"`. It only exists in the JSON
encoder and matches field names only. See
[kora-telemetry-logging: json-logging-reference.md](../../kora-telemetry-logging/references/json-logging-reference.md#masking-fields-in-the-json-record).

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Graph build fails on `MaskingRules<Foo>` in a Java service | Kora 2.0.0.RC1, where the Java masking processor was not registered with javac (fixed in RC2, #921), or `annotation-processors` missing from `annotationProcessor` | Upgrade to RC2+ and keep `annotationProcessor "io.koraframework:annotation-processors"` |
| Graph build fails on `JsonWriter<Foo>` | The logged type is not `@Json`, or `JsonModule` is not in the `@KoraApp` | Add `@Json` to the type and `io.koraframework.json.common.JsonModule` to the app |
| The value logs as one escaped JSON string | `@Mask` without `@Json` on the logged element | Add `@Json` next to `@Mask` |
| A nested field is not masked | The nested type is not annotated `@Json`/`@Mask`, so the walker did not descend into it | Annotate the nested type |
| A renamed field is not masked | Rules use the **JSON** name | Match `@JsonField("…")`, not the Java field name |
| `Only classes and records can be annotated with @Mask` | `@Mask` on an interface or enum | Move it to the concrete type |
| `Abstract classes can't be annotated with @Mask` | `@Mask` on an abstract class | Move it to the concrete subtype |
| Custom `MaskingStrategy` not found | It is not a component | Add `@Component` or declare it in a `@Module` |
| Secret must not be logged at all | `@Mask` still emits a redacted placeholder | Use `@Log.off` on the parameter |
| HTTP/Kafka bodies logged in clear text | No `DataMasker` is registered by default | Register one tagged with the transport's telemetry class (above) |
| A `DataMasker` is registered but never applied | Missing or wrong `@Tag` (e.g. server tag on a client), or the `Content-Type` / Kafka deserializer does not select that format | Tag it with the transport's telemetry class; check the selection column above |
| A logged body is only `<masked:unparseable>` | The payload is not valid for the selected format (an HTML error page sent as `application/json`) — fail closed by design | Expected; fix the upstream `Content-Type` if the body should be readable |
| `user.password` masks nothing in a body | Paths are anchored at the payload root; an envelope adds a segment | Use the full path from the root, or the bare field name |
| `mask = "***"` under `telemetry.logging` has no effect | There is no `mask` key | Provide a `MaskingStrategy` tagged with the transport's telemetry class |
| `<maskField>` in `logback.xml` misses a secret inside a body or header string | It matches JSON field names of the record, not text inside string values | Mask at the source with `DataMasker` / the transport's `maskHeaders` |

## See also

- [logging-aspect.md](logging-aspect.md) — `@Log` family and argument mappers
- [logging-mdc.md](logging-mdc.md) — `@Mdc` and the MDC runtime model
- [logging-performance.md](logging-performance.md) — cost model and volume control
- Parent [SKILL.md](../SKILL.md)
