# Portcast API

A FastAPI-based service for fetching, storing, and analyzing paragraphs with integrated dictionary functionality and Redis caching.

## Features

- **Paragraph Fetching**: Retrieve paragraphs from external API and store persistently
- **Advanced Search**: Search stored paragraphs with 'AND'/'OR' operators
- **Dictionary Integration**: Get definitions for most frequent words
- **Redis Caching**: High-performance caching for word definitions and analytics
- **Docker Ready**: Complete containerized deployment
- **Comprehensive Testing**: Unit and integration tests included

## Code Structure

```
portcast/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies/
│   │   │   └── __init__.py          # Database session dependency
│   │   └── routes.py                # FastAPI route definitions
│   ├── config.py                    # Pydantic settings configuration
│   ├── db/
│   │   ├── __init__.py              # Database module exports
│   │   └── database.py              # SQLAlchemy engine/session management
│   ├── main.py                      # FastAPI application factory
│   ├── models/
│   │   ├── __init__.py
│   │   ├── paragraph.py             # Paragraph table model
│   │   └── word_index.py            # Inverted-index models (unique words + mappings)
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── paragraph.py             # Pydantic API schemas
│   └── services/
│       ├── cache.py                 # Redis caching service
│       ├── dictionary.py            # Dictionary API client
│       ├── metaphorpsum.py          # Paragraph fetching service
│       ├── paragraph.py             # Business logic for paragraphs
│       └── text.py                  # Text processing utilities
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Test configuration and fixtures
│   ├── test_api_integration.py      # API integration tests
│   └── test_text.py                 # Unit tests for text processing
├── docker-compose.yml               # Multi-service Docker setup
├── Dockerfile                       # Application container
├── pyproject.toml                   # Python dependencies and config
└── .env.example                     # Environment variables template
```

## Architecture

### **Frameworks Used**
- **FastAPI**: REST API framework
- **SQLAlchemy**: ORM and database access layer
- **Pydantic / pydantic-settings**: request/response validation and configuration management
- **Redis / RedisJSON**: caching and fast top-word lookup layer
- **Poetry**: dependency and project management

### **Clean Architecture Pattern**
- **API Layer**: HTTP request/response handling (`api/`)
- **Service Layer**: Business logic and external integrations (`services/`)
- **Data Layer**: Database models and connections (`db/`, `models/`)
- **Configuration**: Centralized settings management (`config.py`)

### **Data Storage Layers Used**
- **SQLite**: primary persistent storage for paragraphs and inverted-index tables (`paragraphs`, `unique_words`, `paragraph_words`)
- **Redis Sorted Set**: cached word-frequency rankings in `word_counts`
- **RedisJSON**: cached dictionary definitions in single key `definitions`

### **Search Architecture (Inverted Index)**
- **`paragraphs`**: Stores paragraph content (`id`, `text`, `created_at`)
- **`unique_words`**: Stores one row per normalized unique word (`id`, `word`)
- **`paragraph_words`**: Mapping table between words and paragraphs (`unique_word_id`, `paragraph_id`)
- **Search execution**: `/search` uses SQL joins + grouping/having (for `and`) rather than scanning all paragraph text in Python.

### **Dictionary Cache Architecture**
- Top word frequencies are stored in Redis sorted set `word_counts`.
- Word definitions are stored in a single RedisJSON document key `definitions`:
  - shape: `{ "word": "definition" }`
  - single-word read/write via JSONPath (e.g. `$.hello`)
  - cache clear is `DEL definitions` (single key)

### **Data Flow**
- **`POST /fetch`** pulls one paragraph from Metaphorpsum and writes it to `paragraphs`.
- The same request indexes unique normalized words into `unique_words` and creates mappings in `paragraph_words`.
- After commit, a background task updates Redis `word_counts` and warms dictionary definitions for current top words.
- **`GET /search`** normalizes input words and queries through `unique_words -> paragraph_words -> paragraphs` joins.
- For `operator=or`, it returns paragraphs matching any requested word.
- For `operator=and`, it uses grouped matches with `HAVING COUNT(DISTINCT word) == query_word_count`.

```text
POST /fetch
  |
  v
Metaphorpsum --> paragraphs(id, text, created_at)
          |
          +--> unique_words(id, word)
          |
          +--> paragraph_words(unique_word_id, paragraph_id)
          |
          +--> (post-commit background)
              +--> Redis ZSET: word_counts
              +--> RedisJSON: definitions {word: definition}

GET /search?words=...&operator=and|or
  |
  v
unique_words -> paragraph_words -> paragraphs
         (GROUP BY paragraph, HAVING for AND)
```

```text
GET /dictionary
  |
  +--> Redis ZSET word_counts (top 10)
  |       |
  |       +--> hit: RedisJSON definitions $.word (per top word)
  |       |
  |       +--> miss: fetch from dictionaryapi.dev -> set definitions $.word
  |
  +--> fallback when word_counts empty:
      DB paragraphs -> recompute counts -> Redis word_counts
      then resolve definitions and cache in RedisJSON
```

### **Complexity at a Glance**

| Operation | Current Approach | Approximate Complexity |
|---|---|---|
| Fetch + store paragraph | Insert paragraph + index unique words + mappings | `O(T + W log U + W log L)` |
| Search (`operator=or`) | Inverted-index join query | `O(R + K)` |
| Search (`operator=and`) | Join + `GROUP BY` + `HAVING COUNT(DISTINCT ...)` | `O(R + K)` |
| Dictionary top words | Redis sorted-set top-N (`ZREVRANGE`) | `O(log N + M)` |
| Dictionary definition read (single word) | RedisJSON path read (`$.word`) | `O(1)` (practical/app-level) |
| Clear definitions cache | Single-key delete (`DEL definitions`) | `O(1)` |

Where:
- `T` = token count in one paragraph
- `W` = unique word count in one paragraph
- `U` = total unique words in corpus
- `L` = total rows in `paragraph_words`
- `R` = matched postings rows touched by query terms
- `K` = result paragraph count
- `N` = number of members in `word_counts`
- `M` = number of items returned (`M=10` for top-10)

## Setup

### **Prerequisites**
- Docker Desktop with `docker compose` support
- Python 3.11+ (for local development)
- [Poetry](https://python-poetry.org/docs/#installation) 2.0+ for dependency management

### **Quick Start with Docker (Recommended)**

Includes Redis automatically — no extra setup needed.

```bash
docker compose up --build
```

To stop all containers:
```bash
docker compose down
```

API available at `http://localhost:8000`

### **Local Development Setup**

1. **Install dependencies (creates virtualenv automatically):**
   ```bash
   poetry install
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```

3. **Start Redis locally (needed for caching):**
  ```bash
  brew install redis
  brew services start redis
  ```

4. **Run the application:**
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

API available at `http://localhost:8000`

If Redis is not running, the app still starts and continues without caching.

### **Useful URLs**

| URL | Description |
|---|---|
| `http://localhost:8000/docs` | Swagger interactive UI |
| `POST http://localhost:8000/fetch` | Fetch and store a paragraph |
| `GET http://localhost:8000/search?words=hello&operator=or` | Search paragraphs |
| `GET http://localhost:8000/dictionary` | Top 10 words and definitions |

## Testing

### **Prerequisites for Testing**
```bash
poetry install
```

### **Run All Tests**
```bash
poetry run pytest
```

### **Run with Coverage**
```bash
poetry run pytest --cov=app --cov-report=html
```

### **Run Specific Test Categories**
```bash
# Unit tests only
poetry run pytest tests/test_text.py tests/test_text_extended.py tests/test_dictionary.py tests/test_metaphorpsum.py tests/test_paragraph_service.py

# Integration tests only
poetry run pytest tests/test_api_integration.py

# Run with verbose output
poetry run pytest -v
```

### **Test Matrix**

| File | Type | Coverage |
|---|---|---|
| `tests/test_text.py` | Unit | Core text parsing/counting sanity checks |
| `tests/test_text_extended.py` | Unit | Text edge cases: normalize/empty/punctuation/numbers/hyphenation/top-word boundaries |
| `tests/test_dictionary.py` | Unit | Dictionary service success path, malformed payloads, and HTTP error handling |
| `tests/test_metaphorpsum.py` | Unit | Paragraph fetch success path and failure handling (empty/HTTP errors) |
| `tests/test_paragraph_service.py` | Unit | Inverted-index helpers and paragraph search behavior (`and`/`or`, case-insensitive, ordering) |
| `tests/test_api_integration.py` | Integration | End-to-end API flow for `/fetch`, `/search`, `/dictionary` with mocked external APIs |

### **Test Structure**
- **Unit Tests**: service-level behavior in `test_text.py`, `test_text_extended.py`, `test_dictionary.py`, `test_metaphorpsum.py`, and `test_paragraph_service.py`
- **Integration Tests**: `test_api_integration.py` for full API workflows
- **Test Database**: Each test uses isolated SQLite database
- **External API Mocking**: Uses `respx` to mock HTTP calls

## API Endpoints

### **POST /fetch**
Fetch and store a new paragraph.

**Response:**
```json
{
  "id": 1,
  "text": "Paragraph content...",
  "created_at": "2024-01-01T12:00:00"
}
```

### **GET /search**
Search stored paragraphs by words.

**Parameters:**
- `words` (array): List of words to search for
- `operator` (string): "or" or "and"

**Example:**
```
GET /search?words=hello&words=world&operator=or
```

**Response:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "text": "Hello world example...",
      "created_at": "2024-01-01T12:00:00"
    }
  ]
}
```

### **GET /dictionary**
Get definitions for top 10 most frequent words.

**Response:**
```json
{
  "top": [
    {
      "word": "example",
      "definition": "a thing characteristic of its kind",
      "source": "dictionaryapi.dev"
    }
  ]
}
```

**Important Notes on Top 10 Selection:**
- Returns **exactly 10 words** (if corpus has at least 10 unique words)
- When multiple words share the same frequency, they are sorted **lexicographically (alphabetically)** as a tiebreaker
- **If there's a tie at rank 10**: Only the first word alphabetically from the tied group is included. For example, if ranks 1-9 are unique frequencies and rank 10 has 3 words tied at frequency 15 (apple, banana, cherry), only "apple" is included in the top 10; banana and cherry are excluded
- This ensures **deterministic, consistent results** — the same corpus always produces the same top-10 list

## Configuration

### **Environment Variables**
```bash
# Database
PORTCAST_DATABASE__URL=sqlite+pysqlite:///./app.db
PORTCAST_DATABASE__ECHO=false

# Redis Caching
PORTCAST_REDIS__URL=redis://localhost:6379
PORTCAST_REDIS__TTL=86400
PORTCAST_REDIS__ENABLED=true

# External APIs
PORTCAST_EXTERNAL_API__METAPHORPSUM_URL=http://metaphorpsum.com/paragraphs/1/50
PORTCAST_EXTERNAL_API__DICTIONARY_BASE_URL=https://api.dictionaryapi.dev/api/v2/entries/en

# API Settings
PORTCAST_API__TITLE=Portcast API
PORTCAST_API__VERSION=0.1.0
```

### **Docker Services**
- **API Service**: FastAPI application on port 8000
- **Redis Service**: Caching layer on port 6379

## Development

### **Code Quality**
```bash
# Type checking
mypy app/

# Linting
flake8 app/

# Formatting
black app/
isort app/
```

### **Database Management**
```bash
# Access database directly
sqlite3 app.db

# View tables
.schema

# Query data
SELECT * FROM paragraphs LIMIT 5;

# Inverted-index tables
SELECT * FROM unique_words LIMIT 10;
SELECT * FROM paragraph_words LIMIT 10;
```

### **Clearing Data**

**Clear SQLite:**
```bash
# Delete all rows (keep tables)
sqlite3 app.db "DELETE FROM paragraphs; DELETE FROM unique_words; DELETE FROM paragraph_words;"

# Or delete entire database file
rm app.db
```

**Clear Redis:**
```bash
# Clear all data
redis-cli FLUSHALL

# Or clear only current database
redis-cli FLUSHDB
```

### **API Documentation**
When running locally, visit: `http://localhost:8000/docs` for interactive Swagger UI.

## Deployment

### **Production Deployment**
```bash
# Build and run in detached mode
docker compose up -d --build

# View logs
docker compose logs -f api

# Scale services
docker compose up -d --scale api=3
```

### **Health Checks**
- API health: `GET /docs` (Swagger UI)
- Redis health: Check container logs
- Database health: Verify file exists and is writable

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Notes on AI Assistance

Usage of AI assistance is allowed. The following outlines which parts were AI-assisted and which were driven by my own thought process.

### My Own Thought Process
- Designed the overall project structure and clean architecture pattern (`api/`, `services/`, `models/`, `schemas/`, `db/`)
- Planned the dependency injection approach (`get_db`, session lifecycle) and directed AI to implement it
- Designed the complete Redis caching structure: sorted set for word frequencies, single RedisJSON key for definitions, SETNX lock pattern for concurrent fetch deduplication
- Designed the SQLite schema including the inverted-index tables (`unique_words`, `paragraph_words`) for scalable search
- Chose the post-commit hook pattern to safely schedule background tasks after transaction commit
- Decided to use Poetry for dependency management and project configuration
- Drove all architectural decisions: AND/OR search semantics, O(1) cache clear via single-key delete, concurrency semaphore bounding, Redis-based definition deduplication

### AI-Assisted
- Writing the implementation code based on my designs and specifications (boilerplate, SQLAlchemy session wiring, Redis commands, route handlers)
- Comparing different approaches (e.g. per-key vs single-key Redis definitions, full scan vs inverted-index search, pip vs Poetry) to inform my decisions
- Dockerfile and docker-compose setup
- Test structure and `respx` mocking
- README documentation and diagrams

