# AI-Assisted Journal System Backend

This backend service powers the AI-Assisted Journal System.

It provides:
- user registration and login
- session-based authentication
- journal entry creation and retrieval
- Groq-powered llama-3 LLM for journal analysis
- cached analysis results
- per-user rate limiting for analysis
- aggregate journal insights

## Tech Stack

- FastAPI
- MongoDB
- Groq API
- PyMongo

## Project Structure

```text
backend/
  app/
    db.py
    main.py
    middleware/
    schemas.py
    services/
  models/
  routers/
  Dockerfile
```

## Environment Variables

Create a `.env` file in the `backend` folder.

Example:

```env
GROQ_API_KEY=your_groq_api_key
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=journal_service
MONGODB_JOURNAL_COLLECTION=journal_entries
ENV=dev
```

## Running Locally

Install dependencies in your Python environment, then start the server:

```bash
uvicorn app.main:app --reload
```

Default server:

```text
http://127.0.0.1:8000
```

## Docker

Build:

```bash
docker build -t journal-backend .
```

Run:

```bash
docker run -p 8000:8000 --env-file .env journal-backend
```

## Main Features

### 1. Authentication

Session cookie based auth is used.

Routes:
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/user-details`

## 2. Journal Entries

Routes:
- `POST /api/journal`
- `GET /api/journal/{userId}`

Journal entries are grouped by `userId` in MongoDB.

## 3. Journal Analysis

Route:
- `POST /api/journal/analyze`

Input:

```json
{
  "text": "I felt calm today after listening to the rain"
}
```

Example response:

```json
{
  "emotion": "calm",
  "keywords": ["rain", "nature", "peace"],
  "summary": "User experienced relaxation during the forest session",
  "cached": false
}
```

### Analysis Caching

Repeated analysis requests with the same normalized text are cached in MongoDB.

Cache behavior:
- first request: Groq is called
- repeated request for same text: result is returned from cache

The response includes:
- `cached: false` for fresh model output
- `cached: true` for cache hits

## 4. Rate Limiting

Analysis requests are rate limited per user:
- 5 requests per minute
- 100 requests per day

If the user exceeds the limit, the API returns:

```json
{
  "detail": "Rate limit exceeded: max 5 analysis requests per minute."
}
```

or

```json
{
  "detail": "Rate limit exceeded: max 100 analysis requests per day."
}
```

## 5. Insights

Route:
- `GET /api/journal/insights/{userId}`

Returns:
- total entries
- top emotion
- most used ambience
- recent keywords

`topEmotion` is derived from stored analysis history by grouping on the `emotion` field and selecting the highest-count emotion.

## Notes

- MongoDB is required for persistence.
- Groq API key is required for analysis.
- Session cookies are used for authenticated routes.
- The frontend typically accesses this backend through Next.js rewrites on `/api/*`.
