# Kora Java Build Troubleshooting

Kora is a compile-time framework: the `annotation-processors` processor runs
during `compileJava` and generates `ApplicationGraph`, controllers, JSON
readers/writers, and aspects into
`build/generated/sources/annotationProcessor/`. Most setup failures trace back
to the processor not running or the BOM not reaching the right classpath.

## Contents

- [Annotation processor did not run](#annotation-processor-did-not-run)
- [ApplicationGraph not found](#applicationgraph-not-found)
- [Dependency was not found](#dependency-was-not-found)
- [Wrong imports](#wrong-imports)
- [Tests find no components](#tests-find-no-components)
- [Daemon and cache issues](#daemon-and-cache-issues)
- [Inspecting generated code](#inspecting-generated-code)

## Annotation processor did not run

**Symptom:** no files under `build/generated/sources/annotationProcessor/`;
`ApplicationGraph` is unresolved; the application class compiles to an empty
graph.

**Cause:** `annotationProcessor "ru.tinkoff.kora:annotation-processors"` is
missing, or it is declared but does not get a version.

**Fix:** ensure both the dependency and the configuration wiring exist:

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
}
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
}
```

Confirm it is on the processor path:

```bash
./gradlew dependencies --configuration annotationProcessor
```

## ApplicationGraph not found

**Symptom:** `cannot find symbol: variable ApplicationGraph` in
`KoraApplication.run(ApplicationGraph::graph)`.

**Cause:** `ApplicationGraph` is generated from the `@KoraApp` interface. It
does not exist until the processor runs once.

**Fix:** run the compile step so the processor generates it:

```bash
./gradlew classes
```

If it still does not appear, the processor is not wired — see the section above.
The generated class lives in the same package as the `@KoraApp` interface.

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

## Wrong imports

The most common copy-paste error. Correct packages:

| Symbol | Import |
|--------|--------|
| `@KoraApp` | `ru.tinkoff.kora.common.KoraApp` |
| `KoraApplication` | `ru.tinkoff.kora.application.graph.KoraApplication` |
| `@Component` | `ru.tinkoff.kora.common.Component` |
| `@HttpController` | `ru.tinkoff.kora.http.server.common.annotation.HttpController` |
| `@HttpRoute` | `ru.tinkoff.kora.http.common.annotation.HttpRoute` |

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
    testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"
    testImplementation "ru.tinkoff.kora:test-junit5"
}
```

Also confirm `useJUnitPlatform()` is set in the `test` task.

## Daemon and cache issues

| Symptom | Fix |
|---------|-----|
| Build hangs or fails right after `clean` | `./gradlew --stop`, then rebuild |
| Generated classes broken after a refactor | delete `build/generated/`, rebuild |
| IDE shows errors but `./gradlew classes` passes | IDE has not indexed `build/generated/`; re-run `classes`, refresh/invalidate caches |

## Inspecting generated code

When the wiring is unclear, read what the processor produced:

```
build/generated/sources/annotationProcessor/java/main/
```

Look for `ApplicationGraph.java` (the wired graph), `*Controller` HTTP routers,
and `*JsonReader` / `*JsonWriter`. Reading these is the fastest way to verify
that a module's factories and your `@Component`s actually joined the graph.
