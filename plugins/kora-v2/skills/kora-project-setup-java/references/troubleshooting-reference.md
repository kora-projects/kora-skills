# Kora 2.0 Java Build Troubleshooting

Kora is a compile-time framework: the `io.koraframework:annotation-processors`
processor runs during `compileJava` and generates `ApplicationGraph`,
controllers, JSON readers/writers, and aspects into
`build/generated/sources/annotationProcessor/`. Most setup failures trace back
to the processor not running, the BOM not reaching the right classpath, or the
JVM being too old.

## Contents

- [Annotation processor did not run](#annotation-processor-did-not-run)
- [ApplicationGraph not found](#applicationgraph-not-found)
- [Dependency requires at least JVM runtime version 25](#dependency-requires-at-least-jvm-runtime-version-25)
- [Dependency was not found](#dependency-was-not-found)
- [Wrong imports](#wrong-imports)
- [Type annotation is not expected here](#type-annotation-is-not-expected-here)
- [Tests find no components](#tests-find-no-components)
- [The service answers on the wrong port](#the-service-answers-on-the-wrong-port)
- [Daemon and cache issues](#daemon-and-cache-issues)
- [Inspecting generated code](#inspecting-generated-code)
- [Moving an existing older build onto 2.0](#moving-an-existing-older-build-onto-20)

## Annotation processor did not run

**Symptom:** no files under `build/generated/sources/annotationProcessor/`;
`ApplicationGraph` is unresolved; the application class compiles to an empty
graph.

**Cause:** `annotationProcessor "io.koraframework:annotation-processors"` is
missing, or it is declared but does not get a version.

**Fix:** ensure both the dependency and the configuration wiring exist:

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
}
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"
}
```

Confirm it is on the processor path:

```bash
./gradlew dependencies --configuration annotationProcessor
```

## ApplicationGraph not found

**Symptom:** `cannot find symbol: variable ApplicationGraph` in
`KoraApplication.run(ApplicationGraph::graph)`.

**Cause:** the graph class is generated from the `@KoraApp` interface and does
not exist until the processor has run once. Its name is the interface's simple
name plus `Graph`, in the same package — `Application` → `ApplicationGraph`,
`MyService` → `MyServiceGraph`.

**Fix:** run the compile step so the processor generates it:

```bash
./gradlew classes
```

If it still does not appear, the processor is not wired — see the section above.

## Dependency requires at least JVM runtime version 25

**Symptom, at configuration time, before anything compiles:**

```
Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.
> Run this build using a Java 25 or newer JVM.
```

**Cause:** a Kora artifact (typically `io.koraframework:openapi-generator`) is on
the `buildscript` classpath. That classpath is resolved by the JVM running
Gradle, which the `java { toolchain { … } }` block does not control. Kora 2.0
artifacts are compiled for JVM 25.

**Fix:** run Gradle itself on JDK 25 or newer.

```bash
JAVA_HOME=/path/to/jdk25-or-newer ./gradlew projects
```

Use the latest GA feature release available when you set the project up. Do not
commit `org.gradle.java.home` — it hard-codes a machine-specific path.

## Dependency was not found

**Symptom:** graph build fails with `Required dependency was not found: <Type>`.

**Cause:** a `@Component` (or a module factory) needs `<Type>`, but no component
in the graph provides it.

**Fix:**
- Annotate the providing class with `@Component`, or add a `*Module` to the
  `@KoraApp extends` list that contributes it.
- If a module is on the build path but its factories are missing, the `*Module`
  interface is not in `extends` — add it.
- Inspect what the graph resolved in
  `build/generated/sources/annotationProcessor/.../ApplicationGraph.java`.

The mirror-image failure is `Multiple components match`: the generated modules
**construct** dependency-free mappers themselves and only **inject** mappers that
have constructor dependencies. So a dependency-free mapper marked `@Component`
is ambiguous, and a mapper with dependencies that is *not* a `@Component` is
missing. Decide per mapper, by its constructor.

## Wrong imports

The most common copy-paste error — in Kora 2.0 the DI annotations sit one
package deeper, in `.annotation`:

| Symbol | Import |
|--------|--------|
| `@KoraApp` | `io.koraframework.common.annotation.KoraApp` |
| `@Component` | `io.koraframework.common.annotation.Component` |
| `@Module`, `@Tag`, `@Root`, `@Mapping` | `io.koraframework.common.annotation.*` |
| `KoraApplication` | `io.koraframework.application.graph.KoraApplication` |
| `@HttpController` | `io.koraframework.http.server.common.annotation.HttpController` |
| `HttpServerResponse` | `io.koraframework.http.server.common.response.HttpServerResponse` |
| `@HttpRoute`, `@Path`, `@Query`, `@Header` | `io.koraframework.http.common.annotation.*` |
| `HttpBody` | `io.koraframework.http.common.body.HttpBody` |
| `JsonModule`, `@Json` | `io.koraframework.json.common.JsonModule`, `io.koraframework.json.common.annotation.Json` |
| `@KoraAppTest`, `@TestComponent` | `io.koraframework.test.extension.junit5.*` |

## Type annotation is not expected here

**Symptom:**

```
error: type annotation @org.jspecify.annotations.Nullable is not expected here
```

**Cause:** Kora 2.0 uses JSpecify, whose annotations are **type-use**. They bind
to the type, not to the declaration, so on a qualified nested type they go
immediately before the simple name. Some Kora annotations behave the same way
(`@Column` has been observed to).

**Fix:**

```java
Outer.@Nullable Inner value;   // not: @Nullable Outer.Inner value;
List<@Nullable String> items;
String @Nullable [] array;     // nullable array; @Nullable String[] = array of nullable strings
```

## Tests find no components

**Symptom:** `@KoraAppTest` runs but `@TestComponent` fields are null, or the
test graph fails to build.

**Cause:** the test source set has no annotation processor, so the test graph is
not generated.

**Fix:**

```groovy
configurations {
    testAnnotationProcessor.extendsFrom(koraBom)
}
dependencies {
    testAnnotationProcessor "io.koraframework:annotation-processors"
    testImplementation "io.koraframework:test-junit5"
}
```

Also confirm `useJUnitPlatform()` is set in the `test` task.

If a test's own `@KoraApp` extends the production application, the production
module must additionally be compiled with
`-Akora.app.submodule.enabled=true`, otherwise the processor warns
`Expected @KoraApp as SubModule, but Submodule implementation not found`.

## The service answers on the wrong port

**Symptom:** the configured ports are ignored; the public API is on 8080 and the
system API on 8085 regardless of `application.conf`.

**Cause:** the port keys are not the ones `HttpServerConfig` reads. An
unrecognised HOCON key is ignored without a warning, so each server falls back to
**its own** default. In Kora 2.0 the keys and defaults are:

```hocon
httpServer {
  port = 8080          // public API, default 8080
  system.port = 8085   // system API, default 8085

  system.readinessPath = "/system/readiness"
  system.livenessPath = "/system/liveness"
  system.metricsPath = "/metrics"
}
```

**This failure is silent, not loud.** `SystemHttpServerConfig extends
HttpServerConfig` but **overrides** `port()` to `8085`, so a stale key does not
collapse both servers onto one port. Startup succeeds, the app looks healthy, and
it is simply listening somewhere nobody is looking — probes, scrapers and load
balancers hit nothing. Expect no `Address already in use`: that only happens in
the narrower case where stale keys really do point two servers at the same port.
Do not go looking for a bind error to confirm the diagnosis; compare the actual
listening ports instead.

**Related silent default:** on the public server, telemetry `logging` and
`metrics` are both `false` by default and `tracing` is `true`. Under
`httpServer.system` that last one flips: `SystemHttpServerConfig` overrides
tracing `enabled()` to `false`, so probe and `/metrics` traffic is not traced
unless you turn it on. If you expect `http_server_*` metrics or request logs,
enable them explicitly:

```hocon
httpServer.telemetry.logging.enabled = true
httpServer.telemetry.metrics.enabled = true
```

Metrics additionally need a `MeterRegistry` in the graph
(`implementation "io.koraframework:micrometer-module"`); without one the flag is
accepted and nothing is recorded.

## Daemon and cache issues

| Symptom | Fix |
|---------|-----|
| Build hangs or fails right after `clean` | `./gradlew --stop`, then rebuild |
| Generated classes broken after a refactor | delete `build/generated/`, rebuild |
| A processor reports a parameter named `arg0` / an impossible mismatch | incremental compilation read a class file; `./gradlew <module>:clean` or `--rerun-tasks` |
| IDE shows errors but `./gradlew classes` passes | IDE has not indexed `build/generated/`; re-run `classes`, refresh/invalidate caches |

## Inspecting generated code

When the wiring is unclear, read what the processor produced:

```
build/generated/sources/annotationProcessor/java/main/
```

Look for `ApplicationGraph.java` (the wired graph), `*Controller` HTTP routers,
and `*JsonReader` / `*JsonWriter`. Reading these is the fastest way to verify
that a module's factories and your `@Component`s actually joined the graph. Never
edit them — they are regenerated on every compile.

---

## Moving an existing older build onto 2.0

> **Migration input only.** Everything below describes symptoms seen when a
> project written against Kora 1.x is moved to 2.0. None of the old coordinates
> or packages exist in 2.0 — do not copy them into a new project.

**Build coordinates.**

| Old | Kora 2.0 |
|---|---|
| groupId `ru.tinkoff.kora` | `io.koraframework` |
| BOM `ru.tinkoff.kora:kora-parent` | `io.koraframework:kora-bom` |
| `ru.tinkoff.kora:annotation-processors` | `io.koraframework:annotation-processors` |
| `json-module` | `json-common` |
| `cache-redis` | `cache-redis-lettuce` |
| `http-client-async`, `database-r2dbc`, `database-vertx`, `s3-client-minio` | removed, no drop-in replacement |

**Renaming the group is not enough — the BOM artifact changed name too.**
`io.koraframework:kora-parent` still exists in the Maven Central directory
listing, but only at `2.0.0.alpha5` / `2.0.0.alpha6`; it is an alpha-era leftover
and is not part of the 2.0 releases. A mechanical group rename therefore
either fails outright (`io.koraframework:kora-parent:2.0.0.RC2` does not exist)
or, worse, resolves against an obsolete alpha if someone reaches for the version
Central offers. The 2.0 BOM is `io.koraframework:kora-bom:2.0.0.RC2`. The same
applies to `io.koraframework:cache-redis` and the other alpha leftovers in that
listing: presence in the directory is not membership in the release.

**Packages.** `ru.tinkoff.kora.*` → `io.koraframework.*`, and the DI annotations
moved one level deeper into `io.koraframework.common.annotation`.

**The first build after the rename must be `clean` + `--no-build-cache`.**

**Symptom:** hundreds of `package ru.tinkoff.kora.… does not exist` errors in
files that are not in your sources — every path leads into `build/generated/`.

**Cause:** generator tasks (OpenAPI, protobuf, `wsdl2java`) do not delete their
previous output, and the build-cache key does not account for a changed
`apiPackage` / `modelPackage`. One source set then holds both the old files in
the old package and the new ones.

**Fix:**

```bash
./gradlew clean --continue
./gradlew classes testClasses --continue --no-build-cache
```

Editing the generated files is never the fix.

**Other build-level changes to expect:** JDK moves to 25+ for both the toolchain
and the Gradle process; `jakarta.annotation.Nullable` is replaced by
type-use `org.jspecify.annotations.Nullable`; reactive and `CompletionStage`
contracts are gone (Kora 2.0 contracts are synchronous, executed on virtual
threads); HTTP server port keys and the JDBC config section were renamed.
