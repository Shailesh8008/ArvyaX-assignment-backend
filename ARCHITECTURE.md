# Architecture Notes

## 1. How would this scale to 100k users?

- Run multiple FastAPI instances behind a load balancer.
- Keep the API stateless.
- Use MongoDB with proper indexes and replica sets.
- Shard by `userId` if traffic grows further.
- Move expensive analysis work to background workers.
- Add monitoring for latency, queue depth, cache hits, and error rates.

## 2. How would you reduce LLM cost?

- Analyze only on explicit user action.
- Cache repeated analysis results by text hash.
- Limit input size before sending to Groq.
- Use a smaller model for standard analysis.
- Avoid re-analyzing unchanged text.

## 3. How would you cache repeated analysis?

- Normalize text.
- Create a SHA-256 hash of the normalized text.
- Check cache before calling Groq.
- If found, return cached result.
- If not found, call Groq and store the result.

Current simple approach:
- MongoDB cache

Better production approach:
- Redis for hot cache
- MongoDB for durable storage

## 4. How would you protect sensitive journal data?

- Use HTTPS in production.
- Enforce per-user authorization on every route.
- Use secure HTTP-only cookies or short-lived tokens.
- Encrypt data at rest where possible.
- Do not log raw journal text.
- Store secrets in environment variables or a secret manager.
- Add retention and deletion policies for user data.
