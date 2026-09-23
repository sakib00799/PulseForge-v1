# Rate limiting

PulseForge V1 uses a thread-safe, process-local sliding-window limiter:

| Endpoint | Limit | Identity |
| --- | --- | --- |
| Login | 5/minute | IP + normalized email |
| Register | 3/hour | IP |
| Refresh | 20/minute | Hashed refresh session token |
| Event ingestion | 100/minute | API key ID |

Identity values are hashed before being held in memory. A rejected request returns
HTTP 429, a `Retry-After` header, and the standard PulseForge error body.

## V1 limitation

Memory is not shared between processes, replicas, or hosts, and buckets disappear
on restart. This is correct only while the backend runs as one process. Before
horizontal scaling, use an atomic shared limiter (for example Redis) and validate
it with multi-instance load tests. Proxy-aware client IP handling must also be
configured only for explicitly trusted proxies.
