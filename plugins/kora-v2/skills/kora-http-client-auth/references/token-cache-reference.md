# Token Cache Reference

A thread-safe in-memory cache for access tokens, used by
`HttpClientTokenProvider` implementations.

## Contents

- [TokenCache implementation](#tokencache-implementation)
- [Usage from a token provider](#usage-from-a-token-provider)
- [Design decisions](#design-decisions)
- [Alternative: Caffeine](#alternative-caffeine)
- [Testing](#testing)
- [See also](#see-also)

---

## TokenCache implementation

```java
@Component
public final class TokenCache {

    private static final Duration DEFAULT_MARGIN = Duration.ofSeconds(60);

    private volatile String token;
    private volatile Instant expiryTime;
    private final Object refreshLock = new Object();

    /** Returns the cached token, or null if missing or already expired. */
    @Nullable
    public String get() {
        synchronized (refreshLock) {
            if (token == null || expiryTime == null || Instant.now().isAfter(expiryTime)) {
                return null;
            }
            return token;
        }
    }

    /** Stores a token with the given lifetime. */
    public void set(String token, Duration expiresIn) {
        synchronized (refreshLock) {
            this.token = token;
            this.expiryTime = Instant.now().plus(expiresIn);
        }
    }

    /** True when the token will expire within the given margin. */
    public boolean isExpiringSoon(Duration margin) {
        synchronized (refreshLock) {
            return expiryTime != null && Instant.now().plus(margin).isAfter(expiryTime);
        }
    }

    /**
     * Returns the cached token, or fetches a new one under a lock with double-check
     * to avoid concurrent refreshes. The supplier must return the raw token; this
     * method assumes a one-hour lifetime unless you call {@link #set} inside it.
     */
    public CompletionStage<String> getOrRefresh(Supplier<CompletionStage<String>> refreshSupplier) {
        String cached = get();
        if (cached != null && !isExpiringSoon(DEFAULT_MARGIN)) {
            return CompletableFuture.completedFuture(cached);
        }
        synchronized (refreshLock) {
            cached = get();
            if (cached != null && !isExpiringSoon(DEFAULT_MARGIN)) {
                return CompletableFuture.completedFuture(cached);
            }
            return refreshSupplier.get()
                    .thenApply(newToken -> {
                        this.token = newToken;
                        this.expiryTime = Instant.now().plus(Duration.ofHours(1));
                        return newToken;
                    });
        }
    }
}
```

Imports: `ru.tinkoff.kora.common.Component`, `jakarta.annotation.Nullable`,
`java.time.*`, `java.util.concurrent.*`, `java.util.function.Supplier`.

---

## Usage from a token provider

```java
@Component
public final class JwtTokenProvider implements HttpClientTokenProvider {

    private final TokenCache cache;
    private final AuthClient authClient;

    public JwtTokenProvider(TokenCache cache, AuthClient authClient) {
        this.cache = cache;
        this.authClient = authClient;
    }

    @Override
    public CompletionStage<String> getToken(HttpClientRequest request) {
        return cache.getOrRefresh(() ->
                authClient.fetchToken().thenApply(AuthClient.TokenResponse::accessToken));
    }
}
```

---

## Design decisions

1. **Thread safety** — `synchronized` with double-check prevents duplicate
   refreshes when many requests arrive at once.
2. **Refresh margin** — refresh *before* expiry (60s margin) to avoid sending a
   token that expires in flight.
3. **Volatile fields** — `token` and `expiryTime` are `volatile` so updates are
   visible across threads.

---

## Alternative: Caffeine

For production you may prefer Caffeine (see `kora-aop-caching` for the Kora cache
module). A standalone wrapper:

```java
@Component
public final class CaffeineTokenCache {

    private final Cache<String, CachedToken> cache = Caffeine.newBuilder()
            .expireAfterWrite(1, TimeUnit.HOURS)
            .build();

    @Nullable
    public String get() {
        var cached = cache.getIfPresent("access_token");
        if (cached == null || cached.isExpiringSoon(Duration.ofSeconds(60))) {
            return null;
        }
        return cached.token();
    }

    public void set(String token, Duration expiresIn) {
        cache.put("access_token", new CachedToken(token, Instant.now().plus(expiresIn)));
    }

    record CachedToken(String token, Instant expiryTime) {
        boolean isExpiringSoon(Duration margin) {
            return Instant.now().plus(margin).isAfter(expiryTime);
        }
    }
}
```

```groovy
implementation "com.github.ben-manes.caffeine:caffeine:3.1.8"
```

---

## Testing

```java
@Test
void cachesUntilExpiry() {
    var cache = new TokenCache();

    assertThat(cache.get()).isNull();

    cache.set("test-token", Duration.ofHours(1));
    assertThat(cache.get()).isEqualTo("test-token");
    assertThat(cache.isExpiringSoon(Duration.ofSeconds(60))).isFalse();

    cache.set("expiring-token", Duration.ofSeconds(30));
    assertThat(cache.isExpiringSoon(Duration.ofSeconds(60))).isTrue();
}
```

---

## See also

- [jwt-token-provider-reference.md](jwt-token-provider-reference.md)
- [http-client-auth-reference.md](http-client-auth-reference.md)
