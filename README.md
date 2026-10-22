# CodePilot AI

> **AI-powered software engineering assistant for GitHub repositories**

CodePilot AI is a developer-focused AI system that connects to a GitHub repository, understands its source code structurally, indexes the code for semantic retrieval, and uses an LLM to answer questions, explain code, review code, identify potential security issues, trace dependencies, and generate documentation.

This README is also a **project handoff specification**. Another AI/developer should be able to use this document to understand what CodePilot AI is, what it must do, the intended architecture, technology stack, milestones, constraints, and expected behavior without needing the previous conversation.

---

## 1. Project Vision

Build an AI assistant that can take a GitHub repository and build a structured, searchable understanding of that repository.

The final system should be able to answer questions such as:

- "Explain how authentication works in this repository."
- "Where is the login functionality implemented?"
- "Which classes call `UserService.login()`?"
- "Explain this class and its dependencies."
- "Find potential security vulnerabilities."
- "Find unused or suspicious code."
- "What happens when a user places an order?"
- "Generate documentation for this repository."
- "Generate an architecture overview."
- "What files are affected if I change this method?"
- "Find code related to database access."
- "Review this repository for code-quality problems."

The system should combine:

1. Repository ingestion
2. Repository analysis
3. AST-based code parsing
4. Semantic code chunking
5. Embeddings
6. FAISS vector search
7. Metadata / relationship-based retrieval
8. Hybrid retrieval
9. LLM reasoning
10. Static analysis and security scanning
11. Code intelligence / dependency relationships
12. Documentation generation

---

## 2. Core Problem

A normal LLM cannot reliably "read an entire GitHub repository" by putting every file into its context window.

Large repositories can contain hundreds or thousands of files, multiple programming languages, duplicated/generated code, tests, configuration, documentation, and dependencies.

Sending all files to an LLM is inefficient, expensive, and eventually impossible because of context-window limits.

CodePilot AI solves this by creating a **repository knowledge layer**:

```text
GitHub Repository
       |
       v
Repository Ingestion
       |
       v
File Filtering
       |
       v
AST / Tree-sitter Parsing
       |
       v
Semantic Code Chunks
       |
       +--------------------+
       |                    |
       v                    v
  Embeddings          Code Metadata /
       |              Relationships
       v                    |
     FAISS                  |
       |                    |
       +---------+----------+
                 |
                 v
          Hybrid Retrieval
                 |
                 v
              LLM
                 |
                 v
        Developer Answer
```

---

## 3. Final Product Capabilities

### A. GitHub Repository Connection

Input:

```text
https://github.com/user/repository
```

The system should:

1. Validate the URL.
2. Clone the repository.
3. Optionally support selecting a branch.
4. Prepare the repository for analysis.
5. Avoid indexing `.git` and other irrelevant/generated directories.

Future support:

- public repositories
- private repositories using GitHub authentication/token
- branch selection
- commit/version selection
- incremental re-indexing

### B. Repository Analysis

Determine:

- repository name
- total source files
- programming languages
- file counts by language
- folder structure
- largest files
- supported/unsupported file types
- repository size
- source/test/configuration file distribution

### C. Source File Loading

The FileLoader should:

- recursively discover files
- filter ignored directories
- filter binary/generated files
- detect language from extension
- read source code safely
- preserve file paths and language information

Typical ignored directories:

```text
.git
node_modules
venv
__pycache__
.idea
.vscode
dist
build
target
```

---

## 4. AST-Based Code Understanding

### Tree-sitter

Use Tree-sitter to parse source code into syntax trees.

Do not rely on regex for understanding source-code structure.

Example:

```python
class UserService:

    def login(self):
        pass

    def logout(self):
        pass
```

The parser should understand:

```text
Class
    UserService

Methods
    login
    logout
```

Initial languages:

- Python
- Java

Architecture should make it easy to add:

- JavaScript
- TypeScript
- C++
- C
- Go
- Kotlin
- C#
- Rust
- PHP

---

## 5. Parser Architecture

Recommended:

```text
backend/
└── parsers/
    ├── base_parser.py
    ├── python_parser.py
    ├── java_parser.py
    └── parser_factory.py
```

### Base parser

Defines a common interface.

```python
class BaseParser:
    def parse(self, source_file):
        raise NotImplementedError
```

### Python parser

Extract at minimum:

- classes
- functions
- methods
- imports
- decorators
- relevant control structures where useful

### Java parser

Extract at minimum:

- classes
- interfaces
- enums
- methods
- constructors
- imports
- annotations
- fields
- inheritance
- method calls where feasible

---

## 6. CodeChunk Data Model

Each meaningful source-code unit should become a structured object.

Recommended fields:

```text
CodeChunk
    repository_id
    file_path
    language
    chunk_type
    name
    code
    start_line
    end_line
    parent_symbol
    metadata
```

Example:

```text
file_path:
    src/auth/UserService.java

language:
    Java

chunk_type:
    method

name:
    login

start_line:
    42

end_line:
    68
```

The model should remain extensible for embeddings, relationships, callers, callees, and analysis results.

---

## 7. Semantic Code Chunking

Do not use only naive fixed-size splitting.

Bad:

```text
Every 500 characters
```

Preferred:

```text
Class
  |
  +-- Method
  |
  +-- Method
  |
  +-- Constructor
```

The chunking strategy should preserve code boundaries.

If a method is very large, it may be split further while retaining metadata such as:

```text
parent_symbol = UserService.login
```

Each chunk should retain:

- file path
- language
- symbol name
- chunk type
- line range
- parent class/module
- repository identifier

---

## 8. Embeddings

### Primary embedding model

**BAAI BGE-M3**

Pipeline:

```text
Code Chunk
    |
    v
Embedding Vector
    |
    v
FAISS
```

Recommended module:

```text
backend/embedding.py
```

Responsibilities:

- load embedding model
- generate embeddings
- batch generation
- normalize vectors where appropriate
- expose a stable interface to the vector store

The embedding model should be configurable.

---

## 9. Vector Search

### FAISS

Use **FAISS** as the initial vector store rather than Qdrant.

Reasons:

- local
- lightweight
- fast similarity search
- simple deployment
- no separate vector database server for the initial prototype

Pipeline:

```text
CodeChunks
    |
    v
BGE-M3
    |
    v
Vectors
    |
    v
FAISS Index
```

Store enough metadata to map search results back to:

```text
file_path
chunk_id
symbol
language
line range
code
```

Recommended module:

```text
backend/vector_store.py
```

Responsibilities:

- create index
- add vectors
- save index
- load index
- similarity search
- map results to CodeChunk metadata

---

## 10. Hybrid Retrieval

Do not rely only on vector similarity.

Use:

### Semantic retrieval

FAISS + embeddings.

### Structural retrieval

AST/symbol metadata:

```text
Class
Method
Import
Caller
Callee
Parent
Child
```

### Keyword / lexical retrieval

Useful for exact identifiers:

```text
UserService
login
JWT_SECRET
database_url
```

### Static-analysis retrieval

Security and quality findings should also be available to retrieval.

Concept:

```text
             User Query
                 |
       +---------+---------+
       |         |         |
       v         v         v
   Semantic   Keyword   Structural
   Retrieval  Search    Retrieval
       |         |         |
       +---------+---------+
                 |
                 v
          Result Ranking
                 |
                 v
        Relevant Code Context
                 |
                 v
                LLM
```

---

## 11. RAG Pipeline

```text
User Question
      |
      v
Query Understanding
      |
      v
Retrieve Relevant Chunks
      |
      v
Rank / Filter Results
      |
      v
Build Context
      |
      v
LLM
      |
      v
Grounded Answer
```

The LLM should not invent repository facts that were not retrieved.

Answers should preferably cite source locations:

```text
src/auth/UserService.java:42-68
```

---

## 12. LLM Layer

The LLM must be replaceable.

### Planned local runtime

**Ollama**

Keep the exact model configurable because model choices change over time.

Recommended module:

```text
backend/llm.py
```

Responsibilities:

- model configuration
- prompt construction
- context injection
- LLM invocation
- response parsing
- error handling
- optional streaming

The LLM is for reasoning/generation, not the primary source-code parser.

---

## 13. Code Knowledge Graph

Advanced feature.

Represent relationships such as:

```text
UserController
      |
      | calls
      v
UserService.login()
      |
      | uses
      v
UserRepository.findUser()
```

Possible relationships:

```text
contains
imports
extends
implements
calls
called_by
uses
depends_on
overrides
instantiates
```

This enables:

- "Who calls this method?"
- "What depends on this class?"
- "What is the dependency chain?"
- "What could be affected if this method changes?"

A dedicated graph database is **not required initially**. Start with structured metadata/lightweight graph representations. Evaluate a graph database such as Neo4j only after the core pipeline works.

---

## 14. Static Analysis and Security

The LLM should not be the only security/code-quality mechanism.

### General

**Semgrep**

Use for:

- security patterns
- dangerous APIs
- code patterns
- framework-specific rules
- custom rules

### Java

- **SpotBugs**
- **PMD**
- **Checkstyle**

### Python

- **Ruff**
- **Pylint**

Potential later security addition:

- **Bandit**

Architecture:

```text
Static Analyzer
      |
      v
Finding
      |
      +--> Rule
      +--> File
      +--> Line
      +--> Severity
      +--> Message
      |
      v
LLM Explanation
```

Static-analysis results should be presented as tool findings. The LLM may explain them, but should not automatically claim that every finding is a confirmed vulnerability.

---

## 15. Agentic Architecture

### LangGraph

Use LangGraph for multi-step/multi-agent workflows when they provide real value.

Potential agents:

```text
                    User Query
                         |
                         v
                Orchestrator Agent
                         |
       +-----------------+-----------------+
       |                 |                 |
       v                 v                 v
 Code Search        Security Agent    Dependency Agent
       |                 |                 |
       +-----------------+-----------------+
                         |
                         v
                  Reviewer / Synthesizer
                         |
                         v
                       LLM
```

Do not introduce agents just to make the project look "agentic." First build a reliable RAG pipeline, then add orchestration where branching or multi-step workflows genuinely help.

---

## 16. Frontend

### Streamlit

Use Streamlit for the initial UI because the project is Python-first.

The UI should provide:

### Repository input

```text
GitHub Repository URL
[________________________]

[Analyze Repository]
```

### Repository dashboard

Show:

- repository name
- main language
- total files
- language distribution
- folder structure
- indexing status

### Repository chat

```text
Ask about your repository...

[________________________________]
```

### Code review

Allow selection of:

- repository
- file
- class
- method

### Security dashboard

Show:

- scanner
- severity
- file
- line
- finding
- explanation
- remediation guidance

### Documentation

Generate:

- README
- architecture overview
- module documentation
- API documentation
- class/method explanations

---

## 17. Backend

### FastAPI

FastAPI is the planned backend/API layer when the application is separated from the Streamlit UI.

Initial prototype can call Python services directly from Streamlit.

Later:

```text
Streamlit
    |
    v
FastAPI
    |
    v
Application Services
    |
    +-- Repository Service
    +-- Parser Service
    +-- Embedding Service
    +-- Retrieval Service
    +-- Analysis Service
    +-- LLM Service
```

This allows future clients such as:

- web frontend
- REST clients
- IDE integrations

---

## 18. Background Processing

Large repositories should eventually be processed asynchronously.

Planned:

- **Celery**
- **Redis**

Example:

```text
User
 |
 v
FastAPI
 |
 +----> Queue Job ----> Celery Worker
                            |
                            +--> Clone
                            +--> Parse
                            +--> Embed
                            +--> Index
                            +--> Scan
```

Redis can also provide:

- job broker
- caching
- temporary state

For the first prototype, keep processing synchronous until the basic pipeline works.

---

## 19. Caching

### Redis

Planned uses:

- embedding cache
- LLM response cache where appropriate
- job queue
- temporary processing state
- indexing status

Do not cache sensitive/private repository content without considering isolation, retention, access control, and security.

---

## 20. Database

### SQLite initially

Use SQLite for lightweight metadata.

Possible tables:

```text
repositories
files
code_chunks
symbols
relationships
analysis_results
security_findings
index_metadata
```

Production migration option:

**PostgreSQL**

---

## 21. Complete Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Primary language | Python | Main application language |
| UI | Streamlit | Initial developer UI |
| API/backend | FastAPI | Planned service/API layer |
| AI orchestration | LangGraph | Multi-step/agentic workflows |
| GitHub ingestion | GitPython | Clone repositories |
| Code parsing | Tree-sitter | AST/syntax parsing |
| Language grammars | tree-sitter-language-pack | Precompiled language parsers |
| Embeddings | BAAI BGE-M3 | Semantic vector representations |
| Vector search | FAISS | Local similarity search |
| LLM runtime | Ollama | Local LLM serving |
| General static analysis | Semgrep | Security/pattern analysis |
| Java analysis | SpotBugs | Java bug analysis |
| Java analysis | PMD | Java quality/static analysis |
| Java style | Checkstyle | Java style analysis |
| Python linting | Ruff | Fast Python linting |
| Python linting | Pylint | Python quality analysis |
| Background jobs | Celery | Async processing |
| Cache/queue | Redis | Caching and task broker |
| Metadata DB | SQLite | Initial persistence |
| Production DB | PostgreSQL | Planned scalable persistence |
| Version control | Git | Source control |
| Repository hosting | GitHub | Source hosting |
| Containerization | Docker | Reproducible deployment |
| Multi-container local deployment | Docker Compose | Planned local orchestration |
| Testing | pytest | Unit/integration testing |

Potential advanced technology:

- Neo4j for graph storage, only if the knowledge graph outgrows lightweight metadata.
- Bandit for Python security scanning.
- GitHub REST API/Webhooks for richer GitHub integration.

---

## 22. Recommended Project Structure

```text
CodePilot-AI/
│
├── app.py
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
│
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── github_loader.py
│   ├── repository_analyzer.py
│   ├── file_loader.py
│   ├── chunker.py
│   ├── embedding.py
│   ├── vector_store.py
│   ├── retriever.py
│   ├── rag.py
│   ├── llm.py
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base_parser.py
│   │   ├── python_parser.py
│   │   ├── java_parser.py
│   │   └── parser_factory.py
│   │
│   ├── analyzers/
│   │   ├── semgrep_analyzer.py
│   │   ├── java_analyzer.py
│   │   └── python_analyzer.py
│   │
│   ├── graph/
│   │   ├── symbol_graph.py
│   │   └── relationship_builder.py
│   │
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── code_agent.py
│   │   ├── security_agent.py
│   │   └── documentation_agent.py
│   │
│   └── services/
│       ├── repository_service.py
│       ├── indexing_service.py
│       ├── analysis_service.py
│       └── chat_service.py
│
├── models/
│   ├── __init__.py
│   ├── source_file.py
│   ├── code_chunk.py
│   ├── repository.py
│   └── analysis_result.py
│
├── repositories/
│   └── .gitkeep
│
├── vector_db/
│   └── .gitkeep
│
├── tests/
│   ├── test_repository_analyzer.py
│   ├── test_file_loader.py
│   ├── test_python_parser.py
│   ├── test_java_parser.py
│   ├── test_chunker.py
│   └── test_retriever.py
│
└── assets/
```

Do not commit:

```text
venv/
repositories/
vector_db/
.env
__pycache__/
```

---

## 23. Current Development Status

### Milestone 1 — GitHub Repository Loader

**Status: COMPLETE**

Implemented:

- Streamlit UI
- GitHub URL input
- GitPython
- repository cloning
- local repository storage
- error handling

### Milestone 2 — Repository Analyzer

**Status: COMPLETE**

Implemented:

- repository name detection
- file counting
- programming-language detection
- folder discovery
- largest-file detection
- ignored directory handling
- ignored extension handling
- Streamlit repository statistics

### Milestone 3.1 — File Loader

**Status: IMPLEMENTED / INTEGRATION**

Designed to:

- recursively load source files
- filter unwanted directories
- filter unwanted extensions
- detect language
- create `SourceFile` objects
- provide source code to the parser

### Milestone 3.2 — Tree-sitter Parser

**Status: NEXT CORE TASK**

Known development environment:

```text
tree-sitter                 0.26.0
tree-sitter-language-pack   1.12.2
```

The Tree-sitter playground has already been tested successfully.

For this installed version:

```python
root = tree.root_node()
```

Verify library APIs against the installed version rather than copying old tutorials blindly.

---

## 24. Development Roadmap

### Phase 1 — Repository ingestion

- [x] GitHub URL input
- [x] Clone repository
- [x] Repository analyzer
- [x] Language detection
- [x] File loader

### Phase 2 — Code understanding

- [ ] Parser architecture
- [ ] Tree-sitter Python parser
- [ ] Tree-sitter Java parser
- [ ] Class extraction
- [ ] Method/function extraction
- [ ] Import extraction
- [ ] Constructor/interface extraction
- [ ] Symbol metadata

### Phase 3 — Semantic indexing

- [ ] Semantic code chunking
- [ ] CodeChunk metadata
- [ ] BGE-M3 embeddings
- [ ] FAISS index
- [ ] Metadata persistence
- [ ] Index loading
- [ ] Incremental indexing

### Phase 4 — RAG

- [ ] Query processing
- [ ] Semantic retrieval
- [ ] Keyword retrieval
- [ ] Structural retrieval
- [ ] Hybrid ranking
- [ ] Context construction
- [ ] LLM response generation
- [ ] Source/line references

### Phase 5 — Code intelligence

- [ ] Symbol relationships
- [ ] Call relationships
- [ ] Imports/dependencies
- [ ] Class inheritance
- [ ] Dependency graph
- [ ] Impact analysis

### Phase 6 — Static analysis

- [ ] Semgrep
- [ ] SpotBugs
- [ ] PMD
- [ ] Checkstyle
- [ ] Ruff
- [ ] Pylint
- [ ] Optional Bandit
- [ ] Unified finding model

### Phase 7 — AI Software Engineer

- [ ] Repository chat
- [ ] Code explanation
- [ ] Code review
- [ ] Security explanation
- [ ] Dependency analysis
- [ ] Bug investigation
- [ ] Change-impact analysis
- [ ] Documentation generation

### Phase 8 — Agentic workflows

- [ ] LangGraph
- [ ] Orchestrator
- [ ] Code analysis agent
- [ ] Security agent
- [ ] Documentation agent
- [ ] Result synthesizer

### Phase 9 — Production engineering

- [ ] FastAPI
- [ ] Celery
- [ ] Redis
- [ ] SQLite metadata
- [ ] PostgreSQL migration option
- [ ] Docker
- [ ] Docker Compose
- [ ] Logging
- [ ] Configuration management
- [ ] Unit tests
- [ ] Integration tests
- [ ] Error handling
- [ ] Authentication/security

---

## 25. Engineering Principles

### Single Responsibility Principle

Each component should have one primary responsibility.

```text
GitHubLoader
    -> clone repository

RepositoryAnalyzer
    -> analyze repository

FileLoader
    -> load source files

Parser
    -> understand syntax

Chunker
    -> create semantic chunks

EmbeddingGenerator
    -> generate vectors

VectorStore
    -> search vectors

Retriever
    -> retrieve relevant context

LLM
    -> reason and generate response
```

Do not put the whole system into `app.py`.

### Separation of UI and business logic

Streamlit should primarily:

- collect input
- call services
- display results

Business logic belongs in backend modules/services.

### Configuration over hard-coding

Models, paths, ignored directories, API keys, and limits should be configurable.

Never commit secrets.

---

## 26. Git Workflow

Use meaningful milestone commits:

```text
Initial commit: Repository cloning and analysis
Add Tree-sitter parser
Add Python code extraction
Add Java code extraction
Implement semantic code chunking
Add BGE-M3 embeddings
Implement FAISS vector search
Add hybrid retrieval
Build repository RAG
Add AI code review
Add static security analysis
Add documentation generation
```

Never commit:

```text
venv/
repositories/
vector_db/
.env
__pycache__/
```

---

## 27. Testing Strategy

Important components should have automated tests.

### Repository analyzer

Verify:

- file counts
- language detection
- ignored directories
- folders

### Parser

Input:

```python
class User:
    def login(self):
        pass
```

Expected:

```text
class = User
method = login
```

### Chunker

Verify semantic boundaries and metadata.

### Retriever

Query:

```text
Where is login implemented?
```

Expected result should contain relevant authentication code.

### RAG

Verify that answers are grounded in retrieved repository content.

---

## 28. Important Product Constraint

The system must distinguish:

```text
Tool finding
```

from:

```text
LLM interpretation
```

For example:

```text
Semgrep:
Potential SQL injection pattern detected
```

is a tool finding.

The LLM can explain:

- why the pattern may be dangerous
- how the code reaches the database
- possible remediation

Do not let the LLM invent a vulnerability simply because the user asked for one.

---

## 29. Performance Strategy

Repositories can be large.

Eventually support:

- batch file loading
- batch embedding generation
- caching
- incremental indexing
- background jobs
- safe parallel static analysis
- file-size limits
- binary detection
- generated-code exclusion

Core principle:

```text
Large Repository
      |
      v
Small Relevant Context
      |
      v
LLM
```

---

## 30. Interview Explanation

A concise technical explanation:

> CodePilot AI is an AI-powered code intelligence platform that ingests GitHub repositories, analyzes their structure using Tree-sitter, creates semantic code chunks, generates BGE-M3 embeddings, indexes them with FAISS, and uses hybrid retrieval to provide relevant repository context to an LLM. It also integrates static-analysis tools such as Semgrep, SpotBugs, PMD, Checkstyle, Ruff, and Pylint so deterministic analysis can complement LLM reasoning. The system is designed as a modular backend with Streamlit initially and FastAPI/Celery/Redis planned for production-style deployment.

---

## 31. Interview Questions to Prepare

### Repository ingestion

- Why clone instead of sending files directly?
- How do you handle private repositories?
- How do you handle large repositories?

### Parsing

- What is an AST?
- Why Tree-sitter?
- Why not regex?
- Why parse at symbol level?

### Chunking

- Why not fixed-size chunks?
- How do you preserve context?
- How do you handle very large methods?

### Embeddings

- What are embeddings?
- Why BGE-M3?
- What does vector similarity mean?
- How are embeddings generated efficiently?

### FAISS

- Why FAISS?
- What is an index?
- What is approximate nearest-neighbor search?
- How do you map vectors back to source files?

### RAG

- Why RAG?
- How does retrieval work?
- How do you reduce hallucinations?
- Why hybrid retrieval?

### Security

- Why not rely only on an LLM?
- What does Semgrep provide?
- How do static analyzers complement LLM reasoning?

### Architecture

- Why separate parser, chunker, embedding, and retrieval layers?
- Why use services?
- Why use FastAPI?
- When would Celery/Redis become necessary?

### Agentic AI

- Why LangGraph?
- When is a multi-agent system actually useful?
- What should happen if an agent fails?

---

## 32. Non-Goals for the First Version

Do not try to build everything at once.

The first working version does not need:

- every programming language
- a complex frontend
- a graph database
- Kubernetes
- microservices
- multiple LLM providers
- dozens of agents
- distributed FAISS
- enterprise authentication

Priority:

```text
Working pipeline
      >
Correctness
      >
Good architecture
      >
Testing
      >
Advanced features
      >
UI polish
```

---

## 33. Definition of Done

The final system should support:

```text
                    GitHub URL
                         |
                         v
                 Repository Loader
                         |
                         v
                Repository Analyzer
                         |
                         v
                    File Loader
                         |
                         v
                  Tree-sitter AST
                         |
                         v
                 Semantic Chunker
                         |
              +----------+----------+
              |                     |
              v                     v
         BGE-M3 Embeddings     Code Metadata
              |                     |
              v                     v
             FAISS          Relationships/Graph
              |                     |
              +----------+----------+
                         |
                         v
                  Hybrid Retriever
                         |
              +----------+----------+
              |          |          |
              v          v          v
             Code     Security   Dependency
           Evidence   Findings    Context
              |          |          |
              +----------+----------+
                         |
                         v
                   LangGraph
                  Orchestration
                         |
                         v
                       LLM
                         |
                         v
             AI Software Engineer
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      Explanation     Code Review   Documentation
```

---

## 34. Instructions for Any AI Continuing This Project

If another AI is given this README, it should:

1. Treat this README as the project's source-of-truth specification.
2. Preserve the overall architecture unless a concrete technical issue requires change.
3. Preserve FAISS as the initial vector store.
4. Preserve Tree-sitter as the source-code parser.
5. Preserve BGE-M3 as the planned primary embedding model unless compatibility or quality testing justifies a change.
6. Keep Streamlit as the initial UI.
7. Keep FastAPI as the planned API/backend layer.
8. Do not introduce LangGraph, Celery, Redis, graph databases, or other advanced infrastructure before the simpler pipeline works.
9. Build incrementally and test every milestone.
10. Keep business logic out of `app.py`.
11. Keep modules focused on one responsibility.
12. Explain important architectural decisions so the developer can defend them in interviews.
13. When a library API/version matters, verify the installed version before providing code.
14. Never assume an LLM can reliably detect every vulnerability; combine LLM reasoning with deterministic/static analysis.
15. Prefer working, understandable engineering over unnecessary complexity.
16. Continue from the current milestone instead of rebuilding already completed components.
17. Ask for the current code or error output when a debugging issue depends on implementation details rather than guessing.

---

## 35. Current Immediate Next Task

### Milestone 3.2 — Implement the Tree-sitter parser architecture

Start with:

```text
backend/
└── parsers/
    ├── __init__.py
    ├── base_parser.py
    ├── python_parser.py
    ├── java_parser.py
    └── parser_factory.py
```

First implement the Python parser.

It should:

1. Receive a `SourceFile`.
2. Parse it using the installed Tree-sitter version.
3. Traverse the AST.
4. Extract classes.
5. Extract functions.
6. Extract methods.
7. Create `CodeChunk` objects.
8. Preserve file path and line ranges.
9. Return structured chunks.
10. Test the parser before integrating it into Streamlit.

Then implement Java using the same interface.

---

## 36. Final Project Identity

**Name:** CodePilot AI

**Category:** AI Software Engineer / Code Intelligence Platform

**Primary purpose:** Understand, search, analyze, review, and explain GitHub repositories using structured code analysis, semantic retrieval, static analysis, and LLM reasoning.

### Core differentiator

```text
Not:
GitHub files -> embeddings -> chatbot

Instead:
GitHub repository
    -> structural code understanding
    -> semantic + structural retrieval
    -> static analysis
    -> dependency intelligence
    -> grounded LLM reasoning
    -> software-engineering assistance
```

The final project should demonstrate practical AI engineering, RAG, code intelligence, software architecture, static analysis, backend engineering, and production-oriented development while remaining understandable and defensible in technical placement interviews.
