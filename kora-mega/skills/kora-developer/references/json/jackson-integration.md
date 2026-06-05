# Jackson Integration with Kora

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-json/`

---
## 1. Overview

Kora provides `jackson-module` for integration with Jackson JSON processor:

- **When to use:** Jackson annotations compatibility, complex polymorphic types, legacy code integration
- **Default:** Kora's native json-module (compile-time, no reflection)
- **Alternative:** Jackson module (runtime, reflection-based, more features)

---
## 2. Dependency
### 2.1 Gradle Setup

```groovy
dependencies {
    // Kora JSON module (required) 
    implementation "ru.tinkoff.kora:json-module"
     
    // Jackson module (optional)
    implementation "ru.tinkoff.kora:jackson-module" 
    
    // Jackson annotation processor (for Kora integration) 
    annotationProcessor "ru.tinkoff.kora:json-annotation-processor"
}
```
### 2.2 Kotlin Setup

```kotlin
dependencies {
    implementation("ru.tinkoff.kora:json-module")
    implementation("ru.tinkoff.kora:jackson-module")
    annotationProcessor("ru.tinkoff.kora:json-annotation-processor")
}
```

---
## 3. Module Configuration
### 3.1 Enable Jackson Module

```java
@KoraApp
public interface Application extends JacksonModule {
    static void main(String[] args) { 
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

**What JacksonModule provides:**
- `ObjectMapper` bean configured for Kora
- `JsonReader`/`JsonWriter` adapters for Jackson
- Integration with Kora HTTP server/client
### 3.2 Combined with JsonModule

```java
@KoraApp
public interface Application extends 
    JsonModule,      // Native Kora JSON
    JacksonModule {  // Jackson integration

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

---
## 4. Jackson Annotations
### 4.1 @JsonProperty

```java
import com.fasterxml.jackson.annotation.JsonProperty;

public record UserDto(
    @JsonProperty("user_id") String userId, 
    @JsonProperty("first_name") String firstName,
    @JsonProperty("last_name") String lastName
) {}
```

**JSON:**

```json
{
    "user_id": "123",
    "first_name": "John",
    "last_name": "Doe"
}
```
### 4.2 @JsonIgnore

```java
public record InternalDto(
    String publicField, 
    @JsonIgnore String internalField  // Ignored by Jackson
) {}
```
### 4.3 @JsonInclude

```java
import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record Response(
    String id,
    @Nullable String optionalField  // Not serialized if null
) {}
```

**Include options:**

| Option | Behavior |
|--------|----------|
| `ALWAYS` | Always include |
| `NON_NULL` | Skip null values |
| `NON_EMPTY` | Skip null and empty |
| `NON_ABSENT` | Skip Optional.empty |
### 4.4 @JsonFormat

```java
public record EventDto(
    @JsonFormat(pattern = "dd.MM.yyyy HH:mm") LocalDateTime timestamp, 
    @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal amount
) {}
```

**JSON:**

```json
{
    "timestamp": "15.01.2024 10:30",
    "amount": "99.99"
}
```

---
## 5. Polymorphic Types with Jackson
### 5.1 @JsonTypeInfo + @JsonSubTypes

```java
import com.fasterxml.jackson.annotation.*;

@JsonTypeInfo(
    use = JsonTypeInfo.Id.NAME, 
    include = JsonTypeInfo.As.PROPERTY,
    property = "type"
)
@JsonSubTypes({
    @JsonSubTypes.Type(value = PaymentSuccess.class, name = "SUCCESS"), 
    @JsonSubTypes.Type(value = PaymentError.class, name = "ERROR")
})
public abstract class PaymentResult {}

public class PaymentSuccess extends PaymentResult {
    public String type = "SUCCESS"; 
    public String transactionId;
    public BigDecimal amount;
}

public class PaymentError extends PaymentResult {
    public String type = "ERROR"; 
    public String errorCode;
    public String message;
}
```

**JSON:**

```json
// Success
{
    "type": "SUCCESS",
    "transactionId": "txn_123",
    "amount": 99.99
}

// Error
{
    "type": "ERROR",
    "errorCode": "CARD_DECLINED",
    "message": "Card declined"
}
```
### 5.2 Comparison: Kora vs Jackson

| Feature | Kora @Json | Jackson |
|---------|------------|---------|
| Performance | Compile-time (fast) | Runtime (slower) |
| Reflection | None | Required |
| Polymorphic | @JsonDiscriminatorField | @JsonTypeInfo |
| Null handling | @Nullable | @JsonInclude |
| Custom format | Custom mapper | @JsonFormat |

---
## 6. ObjectMapper Configuration
### 6.1 Custom ObjectMapper Bean

```java
@Module
public interface JacksonConfigModule {
     
    @DefaultComponent
    default ObjectMapper objectMapper() { 
        return new ObjectMapper()
            .registerModule(new JavaTimeModule()) 
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL); 
    }
}
```
### 6.2 Kora-Configured ObjectMapper

```java
@Module
public interface JacksonConfigModule {

    @DefaultComponent
    default ObjectMapper objectMapper(JacksonConfig config) {
        ObjectMapper mapper = new ObjectMapper();

        // Kora-specific configuration
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false); 
        mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

        // Register Java 8 time module
        mapper.registerModule(new JavaTimeModule());

        return mapper;
    }
}
```

---
## 7. HTTP Integration
### 7.1 Controller with Jackson

```java
@HttpController
public final class UserController {
     
    private final UserService userService;
     
    public UserController(UserService userService) {
        this.userService = userService; 
    }
     
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    public HttpServerResponse createUser( 
        @Mapping(JacksonHttpServerRequestMapper.class) UserRequest request
    ) { 
        User user = userService.create(request);
        return JacksonHttpServerResponseMapper.toJson(user); 
    }
}
```
### 7.2 Automatic Jackson Mapping

When `JacksonModule` is enabled, Kora automatically uses Jackson for:

- HTTP request body deserialization
- HTTP response body serialization
- gRPC message serialization

---
## 8. Migration from Jackson to Kora JSON
### 8.1 Before (Jackson)

```java
import com.fasterxml.jackson.annotation.*;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class UserDto {

    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("email_address")
    private String email;

    @JsonIgnore
    private String internalField;

    // Constructors, getters, setters
}
```
### 8.2 After (Kora JSON)

```java
import ru.tinkoff.kora.json.common.annotation.Json;
import ru.tinkoff.kora.json.common.annotation.JsonField;
import ru.tinkoff.kora.json.common.annotation.JsonSkip;

@Json
@JsonInclude(IncludeType.NON_NULL)
public record UserDto(
    @JsonField("user_id") String userId, 
    @JsonField("email_address") String email,
    @JsonSkip String internalField
) {}
```
### 8.3 Migration Checklist

- [ ] Replace `@JsonProperty` with `@JsonField`
- [ ] Replace `@JsonIgnore` with `@JsonSkip`
- [ ] Replace `@JsonInclude` with Kora's `@JsonInclude`
- [ ] Convert classes to records (Java 17+)
- [ ] Update polymorphic types to sealed interfaces
- [ ] Test serialization/deserialization
- [ ] Benchmark performance improvement

---
## 9. When to Use Jackson
### 9.1 Use Kora JSON (Default)

- New projects
- Simple DTOs
- Performance-critical code
- Compile-time safety preferred
### 9.2 Use Jackson

- Existing Jackson codebase
- Complex polymorphic hierarchies
- Need advanced Jackson features:
  - Mix-ins
  - Custom serializers via annotations
  - XML/YAML support
  - CBOR, Smile binary formats
- Third-party libraries requiring Jackson

---
## 10. Testing Jackson Integration
### 10.1 Serialization Test

```java
class JacksonSerializationTest {

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void testUserSerialization() throws JsonProcessingException {
        UserDto user = new UserDto("usr_123", "john@example.com");

        String json = objectMapper.writeValueAsString(user);

        assertThat(json).contains("\"user_id\":\"usr_123\"");
        assertThat(json).contains("\"email_address\":\"john@example.com\"");
    }
}
```
### 10.2 Deserialization Test

```java
@Test
void testUserDeserialization() throws JsonProcessingException {
    String json = """ 
        {
            "user_id": "usr_123", 
            "email_address": "john@example.com"
        } 
        """;
     
    UserDto user = objectMapper.readValue(json, UserDto.class);
     
    assertThat(user.userId()).isEqualTo("usr_123");
    assertThat(user.email()).isEqualTo("john@example.com");
}
```

---
## 11. Quick Reference
### Dependency

```groovy
implementation "ru.tinkoff.kora:jackson-module"
annotationProcessor "ru.tinkoff.kora:json-annotation-processor"
```
### Module

```java
@KoraApp
public interface Application extends JacksonModule {}
```
### Common Jackson Annotations

| Jackson | Kora Equivalent |
|---------|-----------------|
| `@JsonProperty("name")` | `@JsonField("name")` |
| `@JsonIgnore` | `@JsonSkip` |
| `@JsonInclude(NON_NULL)` | `@JsonInclude(IncludeType.NON_NULL)` |
| `@JsonFormat(pattern = "...")` | Custom mapper |
| `@JsonTypeInfo` | `@JsonDiscriminatorField` |
| `@JsonSubTypes` | `@JsonDiscriminatorValue` |
### ObjectMapper Configuration

```java
ObjectMapper mapper = new ObjectMapper()
    .registerModule(new JavaTimeModule())
    .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
    .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
```
