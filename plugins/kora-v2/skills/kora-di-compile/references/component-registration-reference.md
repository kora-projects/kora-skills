# Component Registration Reference

**Applies to:** Kora 2.x (`io.koraframework`)

## Contents

- [Overview](#overview)
- [The 2.0 Annotation Set](#the-20-annotation-set)
- [1. @Component — Constructor Injection](#1-component--constructor-injection)
- [2. @Module Factory Methods](#2-module-factory-methods)
- [3. Providers on the @KoraApp Interface](#3-providers-on-the-koraapp-interface)
- [4. @DefaultComponent — Overridable Providers](#4-defaultcomponent--overridable-providers)
- [5. Generic Providers (Templates)](#5-generic-providers-templates)
- [6. Extension-Generated Components](#6-extension-generated-components)
- [How the Processor Resolves One Dependency](#how-the-processor-resolves-one-dependency)
- [Method Comparison](#method-comparison)
- [Common Mistakes](#common-mistakes)
- [Related References](#related-references)

## Overview

There is no classpath scanning. A type is in the graph only if one of the mechanisms below put it
there, and only if something reachable from a `@Root` asks for it. Every component is a singleton.

## The 2.0 Annotation Set

All DI annotations live in **`io.koraframework.common.annotation`** — including `@Root`, which was
already in `…common.annotation` under 1.x and only changed group. The table below is the complete
package contents, verified against the published `common-2.0.0.RC2.jar`.

| Annotation | Target | Purpose |
|---|---|---|
| `@KoraApp` | interface | the container configuration; generates `<Name>Graph` |
| `@KoraSubmodule` | interface | exports a Gradle subproject's components as `<Name>SubmoduleImpl` |
| `@Module` | interface | a group of provider methods, auto-discovered in the same compilation |
| `@Component` | class | register this class, constructed by its single public constructor |
| `@DefaultComponent` | method, type | a fallback that any non-default provider of the same type+tag beats |
| `@FactoryModule` | method | the returned object is itself a module; see [Component Factories](component-factories-reference.md) |
| `@Conditional` | type, method | gate on a `GraphCondition`; see [Conditional Components](conditional-components-reference.md) |
| `@Root` | type, method | force the component into the graph even if nothing depends on it |
| `@Tag` | method, parameter, field, type, type-use | disambiguate; nested `Tag.Any` and `Tag.Factory` |
| `@Mapping` | field, method, parameter, record component | pick a converter implementation for another Kora module; `@Repeatable` via nested `Mapping.Mappings`, and the value must implement nested `Mapping.MappingFunction` |
| `@NamingStrategy` | type | pick a `NameConverter` (JSON, database entities) |
| `@Generated` | type | marks Kora-generated source |
| `@AopAnnotation`, `@AopPropagate`, `@AopProxy` | annotation type / type | infrastructure for aspect annotations |

## 1. `@Component` — Constructor Injection

### Java

```java
package com.example.service;

import io.koraframework.common.annotation.Component;

@Component
public final class UserService {
    private final UserRepository repository;

    public UserService(UserRepository repository) {
        this.repository = repository;
    }
}
```

### Kotlin

```kotlin
package com.example.service

import io.koraframework.common.annotation.Component

@Component
class UserService(private val repository: UserRepository)
```

### Requirements

| Requirement | Enforcement |
|---|---|
| **Class**, not an interface or annotation | non-classes are ignored |
| **Not abstract** | abstract classes are silently skipped |
| **Exactly one public constructor** | compile error: `@Component class must have exactly one public constructor:` (Kotlin: the primary constructor must be public) |
| **No raw types** | a raw component type produces `Components with raw types can break dependency resolution in unpredictable way` |

`final` is **not** a requirement — it is a convention, and one that flips when aspects are involved:
a class carrying an AOP annotation (`@Log`, `@Retry`, `@Cacheable`, …) must be non-final in Java and
`open` in Kotlin, because the aspect processor subclasses it:

```
AOP aspect cannot be applied to class 'com.example.UserService' because the class is final.
```

## 2. `@Module` Factory Methods

```java
package com.example.storage;

import io.koraframework.common.annotation.Module;

@Module
public interface StorageModule {

    default Storage storage(StorageConfig config) {
        return new TempFileStorage(config);
    }

    default StorageMetrics storageMetrics(Storage storage) {
        return new StorageMetrics(storage);
    }
}
```

```kotlin
@Module
interface StorageModule {

    fun storage(config: StorageConfig): Storage = TempFileStorage(config)
}
```

Rules the processor enforces:

- `@Module` is accepted on **interfaces only** — `@Module can only be applied to interfaces.`
- providers are `default` methods in Java, bodied interface functions in Kotlin; `private` and
  `static` members are ignored
- the return type must be a **reference type** — a provider returning `int`/`long` is rejected with
  `Module method returns a non-reference type, so it cannot be used as a graph component.`
- return types must not be raw: `Component provider returns a raw type:`
- a provider must not return `null` unless every consumer declares the parameter `@Nullable`

A `@Module` compiled in the same Gradle module as `@KoraApp` is discovered automatically. See
[Module Auto-Discovery Reference](module-auto-discovery-reference.md).

## 3. Providers on the `@KoraApp` Interface

The `@KoraApp` interface is itself a module, so its own `default` methods are providers. Use it for
one-offs and for overriding something an extended module supplies:

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {

    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }

    default Clock clock() {
        return Clock.systemUTC();
    }
}
```

## 4. `@DefaultComponent` — Overridable Providers

`@DefaultComponent` targets both **methods and types**, so a `@Component` class can be a default too:

```java
@Module
public interface SmsCellularModule {

    @DefaultComponent
    default SmsCellularProvider smsCellularProvider() {
        return () -> "1";
    }
}
```

When several providers match one claim, the processor drops every `@DefaultComponent` candidate; if
exactly one non-default remains, it wins. Full precedence rules and the override patterns are in
[@DefaultComponent Reference](default-component-reference.md).

## 5. Generic Providers (Templates)

A provider with a type parameter is a **template**: the processor instantiates it on demand for each
concrete type argument that some consumer asks for.

```java
@Module
public interface StorageModule {

    default Function<Integer, byte[]> intMapper()  { return i -> new byte[] {i.byteValue()}; }
    default Function<String, byte[]> stringMapper() { return s -> s.getBytes(UTF_8); }

    default <T> Storage<T> typedStorage(Function<T, byte[]> mapper) {
        return new TempFileStorage<>(mapper);
    }
}
```

A consumer asking for `Storage<String>` gets `typedStorage(stringMapper())`; one asking for
`Storage<Integer>` gets `typedStorage(intMapper())`. Templates are considered only after concrete
declarations fail, and when several templates match the processor tries each in isolation — exactly
one must resolve, or you get `Multiple components match dependency`.

## 6. Extension-Generated Components

When nothing in the graph provides a type, the processor asks its **extensions** to generate one.
This is how declarative Kora features enter the graph with no `@Component` of their own:

Extensions register through `META-INF/services`, so they are active as soon as the corresponding
processor artifact is on the processor path. The ones shipped with Kora 2.0:

| Requested type | Processor artifact | Extension |
|---|---|---|
| a `@Repository` interface | `database-annotation-processor` / `database-symbol-processor` | `RepositoryLinkerExtensionFactory`, plus JDBC and Cassandra column/row mapper factories |
| `JsonReader<T>` / `JsonWriter<T>` | `json-annotation-processor` / `json-symbol-processor` | `JsonLinkerExtensionFactory` |
| a `@HttpClient` interface | `http-client-annotation-processor` / `http-client-symbol-processor` | `HttpClientLinkerExtensionFactory` |
| `HttpServerRequestMapper<T>` | `http-server-annotation-processor` / `http-server-symbol-processor` | `HttpServerRequestMapperKoraExtensionFactory` |
| a config interface / `@ConfigMapper` type | `config-annotation-processor` / `config-symbol-processor` | `ConfigLinkerExtensionFactory` |
| `Validator<T>` for a `@Valid` type | `validation-annotation-processor` / `validation-symbol-processor` | `ValidKoraExtensionFactory` |
| a generated gRPC stub | `grpc-client-annotation-processor` / `grpc-client-symbol-processor` | `GrpcClientExtensionFactory` |
| a MapStruct `@Mapper` (Java) / Konvert `@Konverter` (Kotlin) | `mapstruct-java-extension` / `konvert-ksp-extension` | mapper implementations |

Aspect proxies are **not** extensions: the AOP processor generates a `…_AopProxy` subclass, and the
`@KoraApp` processor registers that instead of the annotated class. The proxy is an implementation
detail: declare and inject the component by its **original** type. A module provider whose return
type is the generated `$Foo__AopProxy` class is rejected with `Component provider returns a
generated AOP proxy type:` (Java and KSP alike), and the fix it prints is to return the proxied type.

An extension that fails reports through the owning processor, so read the *earlier* errors in the
build log before the `No component found` at the end. If the extension artifact is missing from the
processor path there is no diagnostic at all — only `No component found for dependency`.

## How the Processor Resolves One Dependency

For each constructor parameter or provider parameter, in order:

1. **Concrete declarations** matching type **and** tag.
   - exactly one → use it
   - more than one → drop the `@DefaultComponent` candidates; if exactly one non-default remains,
     use it
   - still ambiguous → unless *all* remaining candidates are `@Conditional`, fail with
     `Multiple components match dependency`
2. **Templates** (generic providers) — see above.
3. `@Nullable` parameter → inject `null`.
4. `java.util.Optional<T>` parameter → resolve `T` as nullable and wrap it.
5. **Extension** generation.
6. Otherwise → `No component found for dependency`, with the resolution path, any
   same-type-different-tag candidates, and module hints.

## Method Comparison

| Mechanism | Use when | Notes |
|---|---|---|
| `@Component` | your own service classes | least ceremony; one public constructor |
| `@Module` provider | third-party types, non-trivial construction | full control over the instance |
| `@KoraApp` provider | a one-off, or an override | keeps trivia out of a module |
| `@DefaultComponent` | a library default the app may replace | works on methods and on `@Component` classes |
| Generic provider | one construction rule, many type arguments | resolved lazily per requested type |
| `@FactoryModule` | the *same* module wired twice with different config/tags | see [Component Factories](component-factories-reference.md) |
| Extension | `@Repository`, `@Json`, `@HttpClient`, … | nothing to register by hand |

## Common Mistakes

### Importing DI annotations from `io.koraframework.common`

```java
// BAD — this package holds Configurer, Either, Principal, PromisedProxy; not the annotations
import io.koraframework.common.Component;
import io.koraframework.common.KoraApp;

// GOOD
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.KoraApp;
```

This is the single most common 1.x → 2.0 slip: in 1.x these lived in `ru.tinkoff.kora.common`, and a
plain `ru.tinkoff.kora` → `io.koraframework` replace lands them in the wrong package.

### Two public constructors

```java
// BAD — "@Component class must have exactly one public constructor:"
@Component
public final class UserService {
    public UserService() { }
    public UserService(UserRepository repo) { }
}

// GOOD — keep one public, demote the rest
@Component
public final class UserService {
    public UserService(UserRepository repo) { }
    private UserService() { throw new UnsupportedOperationException(); }
}
```

### `@Module` on a class

```java
// BAD — "@Module can only be applied to interfaces."
@Module
public class DatabaseModule { }

// GOOD
@Module
public interface DatabaseModule { }
```

### A Kora `Context` parameter

```java
// BAD — Context does not exist in Kora 2.0; nothing can provide it
@Component
public final class AuditService {
    public AuditService(Context context) { }
}

// GOOD — pass what you actually need
@Component
public final class AuditService {
    public AuditService(Clock clock) { }
}
```

### Asynchronous component contracts

```java
// BAD — Kora 2.0 contracts are synchronous, on virtual threads
@Component
public final class UserService {
    public CompletionStage<User> find(String id) { … }
}

// GOOD
@Component
public final class UserService {
    public User find(String id) { … }
}
```

Kotlin: no `suspend` on component methods that Kora itself calls, and no Reactor `Mono`/`Flux`
anywhere in a Kora contract.

## Related References

- [@KoraApp Reference](kora-app-component-reference.md) — bootstrap and the generated graph
- [Component Factories Reference](component-factories-reference.md) — providers, generics, `@FactoryModule`
- [@DefaultComponent Reference](default-component-reference.md) — precedence and overrides
- [Module Auto-Discovery Reference](module-auto-discovery-reference.md) — when `extends` is required
- [Tags & Collections Reference](tags-collections-reference.md) — `@Tag`, `All<T>`, `ValueOf<T>`
