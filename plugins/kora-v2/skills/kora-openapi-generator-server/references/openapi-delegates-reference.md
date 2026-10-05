# OpenAPI Delegates Reference — Kora 2.x

The `*ApiDelegate` interface is the **only** implementation point of a generated Kora HTTP
server. Everything in this document was read out of the generated output of
`io.koraframework:openapi-generator` for `2.0.0.RC2`.

## Contents

- [1. Shape of the generated interface](#1-shape-of-the-generated-interface)
- [2. Implementing it](#2-implementing-it)
- [3. Signature mapping rules](#3-signature-mapping-rules)
- [4. Parameter order](#4-parameter-order)
- [5. `requestInDelegateParams`](#5-requestindelegateparams)
- [6. `delegateMethodBodyMode`](#6-delegatemethodbodymode)
- [7. Form and multipart operations](#7-form-and-multipart-operations)
- [8. Raw and binary bodies](#8-raw-and-binary-bodies)
- [9. Signature-mismatch troubleshooting](#9-signature-mismatch-troubleshooting)
- [10. Related](#10-related)

---

## 1. Shape of the generated interface

One `public interface` per OpenAPI tag, named `<Tag as classname>Delegate`. For tag `pets` the
generator produces `PetsApiDelegate`:

```java
@Generated("io.koraframework.openapi.generator.javagen.ServerApiDelegateGenerator")
public interface PetsApiDelegate {

  @HttpRoute(method = "GET", path = "/pets")
  PetsApiResponses.ListPetsApiResponse listPets(
      @Header("firstHeader") String firstHeader,
      @Query("requiredLimit") int requiredLimit,
      @Query("limit") @Nullable Integer limit) throws Exception;

  @HttpRoute(method = "GET", path = "/pets/{petId}")
  PetsApiResponses.ShowPetByIdApiResponse showPetById(@Path("petId") String petId) throws Exception;
}
```

```kotlin
@Generated("io.koraframework.openapi.generator.kotlingen.ServerApiDelegateGenerator")
public interface PetsApiDelegate {

  @HttpRoute(method = "GET", path = "/pets")
  public fun listPets(
    @Header(value = "firstHeader") firstHeader: String,
    @Query(value = "requiredLimit") requiredLimit: Int,
    @Query(value = "limit") limit: Int?,
  ): PetsApiResponses.ListPetsApiResponse
}
```

Facts to rely on:

- **The interface and every method are `public`.** No package-private generated API in 2.0.
- **Java methods declare `throws Exception`.** Your override may narrow it away entirely, and
  the migrated examples do — but only if you throw nothing checked.
- **Kotlin methods are plain `fun`, never `suspend`.** Contracts are synchronous.
- The return type is always a nested type of `<Tag>ApiResponses` — see
  [Response Reference](openapi-response-reference.md).
- The routing annotations (`@HttpRoute`, `@Path`, `@Query`, `@Header`, `@Cookie`, `@Json`) that
  appear on the interface are documentation of the contract; routing is actually driven by the
  generated `*ApiController`. Do not copy them onto your implementation.

## 2. Implementing it

===! ":fontawesome-brands-java: `Java`"

    ```java
    package com.example.petapi.delegate;

    import io.koraframework.common.annotation.Component;
    import org.jspecify.annotations.Nullable;
    import com.example.petapi.api.PetApiDelegate;
    import com.example.petapi.api.PetApiResponses;
    import com.example.petapi.model.Pet;

    @Component
    public final class PetDelegate implements PetApiDelegate {

        private final PetService petService;

        public PetDelegate(PetService petService) {
            this.petService = petService;
        }

        @Override
        public PetApiResponses.GetPetByIdApiResponse getPetById(long petId) {
            var pet = petService.find(petId);
            return pet == null
                ? new PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse()
                : new PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet);
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    package com.example.petapi.delegate

    import io.koraframework.common.annotation.Component
    import com.example.petapi.api.PetApiDelegate
    import com.example.petapi.api.PetApiResponses

    @Component
    class PetDelegate(private val petService: PetService) : PetApiDelegate {

        override fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse {
            val pet = petService.find(petId)
                ?: return PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse()
            return PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet)
        }
    }
    ```

`@Component` is `io.koraframework.common.annotation.Component`. Without it the compile-time
graph fails with *"No component found for dependency … PetApiDelegate"* while building the
generated `PetApiController`.

Keep business logic in injected services. The delegate's job is to translate between generated
transport models and your domain, and to pick a response record.

## 3. Signature mapping rules

| OpenAPI | Generated |
|---|---|
| `tags[0]` | interface name `<Tag>ApiDelegate` |
| `operationId` | method name |
| `in: path` | parameter annotated `@Path("<name>")` |
| `in: query` | parameter annotated `@Query("<name>")` |
| `in: header` | parameter annotated `@Header("<name>")` |
| `in: cookie` | parameter annotated `@Cookie("<name>")` |
| JSON `requestBody` | parameter annotated `@Json`, typed as the model |
| `required: false` | parameter is boxed and annotated `@Nullable` (Java) / typed `T?` (Kotlin) |
| `required: true`, primitive schema | unboxed primitive (`int`, `long`, `boolean`) |
| `responses` | return type `<Tag>ApiResponses.<Op>ApiResponse` |
| `deprecated: true` | `@Deprecated` on the method |

`format` matters: `format: uuid` → `java.util.UUID`, `format: date` → `LocalDate`,
`format: date-time` → `OffsetDateTime` (or the `typeMappings` target), `format: binary` → `byte[]`, `type: string` with
`format: uri` → `java.net.URI`, `type: number` → `BigDecimal`.

## 4. Parameter order

The generator appends parameters in a fixed order. Match it exactly:

1. `HttpServerRequest _serverRequest` — only with `requestInDelegateParams: "true"`
2. `HttpHeaders _headers` — only when the operation has a non-JSON or bare-object body
3. every `path` / `query` / `header` / `cookie` / body parameter, in spec order, skipping form
   parameters and any header turned implicit by `implicitHeaders` / `implicitHeadersRegex`
4. `<Op>FormParam form` — only for operations with form parameters

## 5. `requestInDelegateParams`

```groovy
configOptions = [mode: "java-server", requestInDelegateParams: "true"]
```

adds `HttpServerRequest` as the first argument of **every** controller and delegate method:

```java
PetsApiResponses.CreatePetsApiResponse createPets(HttpServerRequest _serverRequest) throws Exception;
```

Use it for things the contract cannot express — a trace header a gateway injects, the remote
address, raw query access. It is all-or-nothing: there is no per-operation switch, and turning it
on changes every existing signature at once.

`HttpServerRequest` is `io.koraframework.http.server.common.request.HttpServerRequest`. Kora 2.0
has no `Context` — request-scoped state travels as ordinary method arguments or through the
`Principal` established by an interceptor.

## 6. `delegateMethodBodyMode`

| Value | Delegate methods | Extra output |
|---|---|---|
| `none` (default) | `abstract` | — |
| `throwException` | `default` bodies that `throw new UnsupportedOperationException("Not yet implemented")` (Kotlin: `TODO()`) | `<Tag>ApiModule`, a `@Module` interface with `default <Tag>ApiDelegate default<Tag>ApiDelegate() { return new <Tag>ApiDelegate() {}; }` |

The 1.x spelling `throw-exception` is rejected — `DelegateMethodBodyMode.of` accepts only `none`
and `throwException`.

```java
@Generated("io.koraframework.openapi.generator.javagen.ServerApiModuleGenerator")
@Module
public interface PetsApiModule {
  default PetsApiDelegate defaultPetsApiDelegate() {
    return new PetsApiDelegate() {};
  }
}
```

That module method is **not** `@DefaultComponent`, and `@Module` interfaces are auto-discovered
by the `@KoraApp` processor. So if you also declare your own `@Component` delegate, two
candidates satisfy the same dependency and the graph build fails with *"Multiple components
match"*. Use `throwException` only to stand a contract up before any handler exists; switch back
to `none` (or delete the flag) the moment you write a real delegate.

## 7. Form and multipart operations

An operation with `application/x-www-form-urlencoded` or `multipart/form-data` gets its form
fields grouped into a record generated **inside the controller**, passed through a generated
request mapper:

```java
PetsApiResponses.UpdatePetWithFormApiResponse updatePetWithForm(
    @Path("petId") long petId,
    @Mapping(PetsApiServerRequestMappers.UpdatePetWithFormFormParamRequestMapper.class)
    PetsApiController.UpdatePetWithFormFormParam form) throws Exception;
```

The record's components follow the form schema; `format: binary` fields become
`FormMultipart.FormPart` (or `List<FormMultipart.FormPart>` for arrays), and every other
non-string field is read through an `HttpServerParameterReader`.

Array form fields (strings, primitives, enums, models) are collected part by part; an absent
optional array arrives as `null`, not an empty list. Boolean form values are parsed strictly —
anything but `true` / `false` answers `400`.

## 8. Raw and binary bodies

A body that is not JSON, or a bare `type: object` with no schema, changes two things:

- the delegate gains a leading `HttpHeaders _headers` parameter so you can read the real
  `Content-Type`;
- the body type follows `configOptions.rawBodyMode`: `BYTES` (default) → `byte[]`, `BODY` →
  `HttpBodyInput` on the server, `OBJECT` → `Object` decoded as JSON.

```java
DefaultApiResponses.FormImagePatchApiResponse formImagePatch(HttpHeaders _headers, byte[] body)
        throws Exception;
```

`HttpHeaders` is `io.koraframework.http.common.header.HttpHeaders`.

## 9. Signature-mismatch troubleshooting

`method does not override or implement a method from a supertype` (Java) and
`'…' overrides nothing` (Kotlin) both mean the same thing: your implementation and the
regenerated interface disagree. In a 1.x → 2.x migration the causes, in order of frequency:

| Symptom in your code | Fix |
|---|---|
| `Mono<…>`, `Flux<…>`, `CompletionStage<…>` return type | Return the response type directly — those modes no longer exist. |
| `override suspend fun` (Kotlin) | Drop `suspend`. |
| `Context` parameter | Removed from the framework; use `requestInDelegateParams` or a `Principal`. |
| Non-null Kotlin parameter for an optional contract parameter | Generated contracts are `@NullMarked`; an `required: false` parameter is `T?` and the override must be `T?`. The Kotlin error text never mentions nullability. |
| Boxed `Integer`/`Long` where the contract is `required: true` | Required primitive schemas generate unboxed `int`/`long`. |
| Extra or missing leading parameter | `requestInDelegateParams` or a raw body added `_serverRequest` / `_headers`; see section 4. |
| Delegate imported from a stale package | Old generated output still on the source set — `./gradlew clean build --no-build-cache`. |

The reliable procedure: open the generated `*ApiDelegate` in `build/generated`, copy the method
signature verbatim, then adjust only the body. Never edit the generated file.

## 10. Related

- [Response Reference](openapi-response-reference.md) — what to return
- [Controllers Reference](openapi-controllers-reference.md) — what calls you
- [Models Reference](openapi-models-reference.md) — the parameter and body types
- [Codegen Reference](openapi-codegen-reference.md) — the options used above
