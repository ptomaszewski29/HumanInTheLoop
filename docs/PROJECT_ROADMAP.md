# 👑 Human In The Loop

## Project Vision

Human In The Loop is a multi-agent software engineering platform where AI agents generate, review and validate code while humans retain final decision authority.

The long-term goal is to integrate:

- AI Development Agents
- Architecture Review
- Automated Testing
- Git Automation
- Pull Requests
- GitHub / Azure Boards integration

while maintaining Human-In-The-Loop governance.

---

# Current Version

## MVP v0.2

Status: ✅ COMPLETE

### Implemented

#### Infrastructure

- [x] Python Environment
- [x] GitHub Repository
- [x] VS Code Setup
- [x] Ruff Configuration
- [x] README
- [x] .gitignore

#### AI Layer

- [x] Gemini Integration
- [x] GeminiService
- [x] DeveloperAgent

#### Human In The Loop

- [x] Generate Code
- [x] Approve Workflow
- [x] Reject Workflow

#### Domain Model

- [x] Task
- [x] TaskStatus Enum

#### Persistence

- [x] SQLite
- [x] TaskRepository
- [x] Save Task
- [x] Load Task
- [x] Update Status

#### Dashboard

- [x] Task History
- [x] Open Task from History
- [x] Status Tracking

---

# Sprint 3

Status: 🚧 NEXT

## Goal

Introduce true multi-agent workflow.

---

## ArchitectAgent

### GitHub Issue

Title

```text
Create Architect Agent
```

### Description

Implement agent responsible for architecture review.

Inputs:

- task description
- generated code

Outputs:

- architecture review
- architecture score
- architecture approval recommendation

### Acceptance Criteria

- [ ] ArchitectAgent created
- [ ] Generates architecture review
- [ ] Generates architecture score
- [ ] Stores review in Task

---

## QAAgent

### GitHub Issue

Title

```text
Create QA Agent
```

### Description

Implement testing specialist agent.

Inputs:

- generated code

Outputs:

- Vitest unit tests

### Acceptance Criteria

- [ ] QAAgent created
- [ ] Generates tests
- [ ] Stores tests in Task

---

## Expand Task Model

### GitHub Issue

Title

```text
Extend Task Domain Model
```

### Acceptance Criteria

- [ ] generated_tests
- [ ] architecture_review
- [ ] architecture_score

Target model:

```python
Task(
    id,
    description,
    generated_code,
    generated_tests,
    architecture_review,
    architecture_score,
    status,
)
```

---

## Dashboard Refactor

### GitHub Issue

Title

```text
Add Review Tabs
```

### Acceptance Criteria

- [ ] Code Tab
- [ ] Architecture Review Tab
- [ ] Tests Tab

---

## First Multi-Agent Workflow

### GitHub Issue

Title

```text
Implement Multi-Agent Flow
```

Target flow:

```text
Task
 ↓
DeveloperAgent
 ↓
ArchitectAgent
 ↓
QAAgent
 ↓
Human Approval
```

---

# Sprint 4

Status: 📋 PLANNED

## Workflow Orchestrator

### GitHub Issue

```text
Create Workflow Orchestrator
```

Target:

```text
app.py
 ↓
WorkflowOrchestrator
 ↓
DeveloperAgent
 ↓
ArchitectAgent
 ↓
QAAgent
```

---

# Sprint 5

Status: 📋 PLANNED

## LangGraph Integration

### GitHub Issue

```text
Implement LangGraph Workflow
```

Target flow:

```text
Developer
 ↓
Architect
 ↓
QA
 ↓
WAITING_FOR_APPROVAL
 ↓
Human
```

---

# Sprint 6

Status: 📋 PLANNED

## Repository Management

### GitHub Issue

```text
Repository Domain Model
```

Acceptance Criteria:

- [ ] Repository entity
- [ ] Repository selection
- [ ] Repository path storage

Example:

```python
Repository(
    name="Frontend",
    path="C:/Projects/Frontend"
)
```

---

# Sprint 7

Status: 📋 PLANNED

## File Generation

### GitHub Issue

```text
Generate Real Files
```

Acceptance Criteria:

- [ ] Generate TypeScript files
- [ ] Generate test files
- [ ] Write files to repository

---

# Sprint 8

Status: 📋 PLANNED

## GitAgent

### GitHub Issue

```text
Create Git Agent
```

Workflow:

```text
Approved Task
 ↓
Create Branch
 ↓
Commit Files
```

---

# Sprint 9

Status: 📋 PLANNED

## Pull Request Automation

### GitHub Issue

```text
Automate Pull Requests
```

Acceptance Criteria:

- [ ] GitHub PR
- [ ] Azure DevOps PR

---

# Sprint 10

Status: 📋 PLANNED

## Issue Driven Development

### GitHub Issue

```text
Import GitHub Issues
```

Workflow:

```text
GitHub Issue
 ↓
Task
 ↓
Repository
 ↓
Developer
 ↓
Architect
 ↓
QA
 ↓
Human
 ↓
GitAgent
 ↓
Pull Request
```

---

# Future Vision

```text
GitHub Issue
        ↓
Task
        ↓
Repository Selection
        ↓
DeveloperAgent
        ↓
ArchitectAgent
        ↓
QAAgent
        ↓
Human Approval
        ↓
GitAgent
        ↓
Branch
        ↓
Commit
        ↓
Pull Request
```

# 👑 Human In The Loop

## Current State

Status: 🚧 Sprint 3 In Progress

Date: 2026-10-06

---

# What Works

## Core Application

- [x] Streamlit UI
- [x] SQLite persistence
- [x] Task history
- [x] Task loading
- [x] Task status updates

## Domain Model

- [x] Task
- [x] TaskStatus
- [x] TaskRepository

## Agent Layer

- [x] DeveloperAgent
- [x] ArchitectAgent
- [x] QAAgent

## Workflow

- [x] WorkflowOrchestrator
- [x] Human Approval Workflow

## LLM Providers

- [x] GeminiService
- [x] OllamaService
- [x] LLMFactory
- [x] Provider abstraction

---

# Current Architecture

```text
Task
 ↓
WorkflowOrchestrator
 ↓
DeveloperAgent
 ↓
ArchitectAgent
 ↓
QAAgent
 ↓
Task
 ↓
SQLite
 ↓
Streamlit UI
```

---

# Verified Working Components

## Ollama

Verified:

- [x] Ollama installed
- [x] Local endpoint works
- [x] Qwen model loaded
- [x] generate_text() returns responses

## Developer Agent

Verified:

- [x] Generates TypeScript code
- [x] Returns non-empty response

Example result:

```typescript
function validateEmail(email: string): boolean {
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

  return emailRegex.test(email);
}
```

---

# Known Problems

## ArchitectAgent

Current state:

- Prompt executes
- Ollama responds
- Review generation unstable

Observed behavior:

```text
"Please provide the TypeScript code you'd like reviewed."
```

Need further debugging.

---

## QAAgent

Current state:

- Agent exists
- Workflow integration exists

Not yet verified end-to-end.

---

## Database

Current schema:

```sql
tasks
```

Columns:

- id
- description
- generated_code
- architecture_review
- architecture_score
- generated_tests
- status
- created_at

---

# Next Task

## Debug ArchitectAgent

Goal:

Verify complete flow:

```text
Developer
 ↓
Generated Code
 ↓
Architect
 ↓
Architecture Review
```

Acceptance criteria:

- architecture_review populated
- review visible in UI

---

# After ArchitectAgent Works

## Verify QAAgent

Goal:

```text
Generated Code
 ↓
QAAgent
 ↓
Vitest Tests
```

Acceptance criteria:

- tests generated
- tests saved to SQLite
- tests displayed in UI

---

# Sprint 3 Completion Criteria

Workflow:

```text
Task
 ↓
DeveloperAgent
 ↓
ArchitectAgent
 ↓
QAAgent
 ↓
SQLite
 ↓
UI
```

All outputs visible:

- [ ] Code
- [ ] Architecture Review
- [ ] Tests

---

# Future Work

## Sprint 4

Workflow Orchestration Improvements

- [ ] Graph based execution
- [ ] Agent feedback loop
- [ ] Architect -> Developer corrections

Target:

```text
Architect
 ↓
Developer
 ↓
Architect
 ↓
QA
 ↓
Human
```

---

## Sprint 5

LangGraph

- [ ] Graph State
- [ ] Nodes
- [ ] Human Checkpoint

---

## Sprint 6

Repository Management

- [ ]
