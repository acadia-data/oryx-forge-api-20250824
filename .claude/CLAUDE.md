# Claude Subagent Workflow for Data Analysis

## Overview
Two-stage workflow using Claude subagents with session-based conversation memory for data analysis tasks.

## Claude's Responsibilities (via subagents)

### Stage 1: Intent Preparation (@intent-prep)
- Parse user request for sheet references (@SheetName or natural language)
- List available datasets/sheets via MCP tools
- Ask user for clarification when references are ambiguous
- Detect multi-step requests
- Create target sheet if needed (with user confirmation)
- For multi-step: prepare FIRST step only, note remaining steps
- Output prepared context for analysis agent

### Stage 2: Data Analysis (@data-analyst)
- Receive prepared inputs/targets from @intent-prep
- Write and execute exploratory code via MCP tools
- Iterate until analysis requirements met
- Write and execute production code via MCP tools
- Output result with target information
- For multi-step: prompt user to continue if more steps pending

## Multi-Step Workflow Example

```
User: "create sheet 'Target Analysis' joining @Sheet1 with @Sheet2, then join Target Analysis with @Sheet3"

↓ @intent-prep recognizes 2 steps, prepares Step 1 only

Output:
# Intent Preparation Complete

**Multi-Step Request: Step 1 of 2**

## Current Step
Inputs: sources.Sheet1, sources.Sheet2
Target: exploration.TargetAnalysis (creating)
Goal: Join Sheet1 and Sheet2

## Remaining Steps
- Step 2: Join exploration.TargetAnalysis with sources.Sheet3

@data-analyst: Load sources.Sheet1 and sources.Sheet2, join them, save to exploration.TargetAnalysis

↓ @data-analyst executes Step 1

Output:
Analysis complete.
Target: exploration.TargetAnalysis
Results: Successfully joined Sheet1 and Sheet2, created 1,250 rows.

Next Step: Join this result with Sheet3 (type 'continue' to proceed)

↓ User types "continue"

↓ @intent-prep checks session memory, sees Step 2 pending

Output:
# Intent Preparation Complete

**Multi-Step Request: Step 2 of 2**

## Current Step
Inputs: exploration.TargetAnalysis, sources.Sheet3
Target: exploration.TargetAnalysis (updating)
Goal: Join TargetAnalysis with Sheet3

@data-analyst: Load exploration.TargetAnalysis and sources.Sheet3, join them, update exploration.TargetAnalysis

↓ @data-analyst executes Step 2

Output:
Analysis complete.
Target: exploration.TargetAnalysis
Results: Successfully joined with Sheet3, final dataset has 1,180 rows.
```

**Key Points**:
- Session memory tracks original multi-step request
- Session memory remembers which step is current and what steps remain
- Each step is reviewed before proceeding to next
- Results from previous steps inform next step preparation

## ChatService's Responsibilities

### Session Management
- Use `project_id` as `session_id` for Claude Agent SDK
- Resume existing session for conversation continuity
- Claude Agent SDK manages full conversation history automatically
- No need to manually retrieve or pass chat history

### Request Processing Flow
1. Build prompt with user message + minimal context (mode, active dataset/sheet)
2. Call `ClaudeAgent.query_run(session_id=project_id)`
3. Claude automatically delegates to subagents (@intent-prep → @data-analyst)
4. Capture result from Claude

### Response Handling Flow
1. Extract target dataset/sheet from Claude's result (parse for "Target: dataset.sheet")
2. Save user message to `chat_messages` table (full content)
3. Save agent response to `chat_messages` table (full content)
4. Return `{message, target_dataset, target_sheet, cost_usd, duration_ms}`

## Communication Flow Diagram

```
User Message
    ↓
ChatService.chat(message, mode, ds_active, sheet_active)
    ↓
Build prompt with minimal context
    ↓
ClaudeAgent.query_run(prompt, session_id=project_id)  ← Resume session
    ↓
Claude Agent SDK (session memory active)
    ↓
    ├─→ @intent-prep subagent
    │     ├─ List datasets/sheets via MCP
    │     ├─ Multi-step? Prepare first step only
    │     ├─ Ambiguous? Clarify with user
    │     ├─ Create target sheet (after confirmation)
    │     └─ Hand off to @data-analyst
    │
    └─→ @data-analyst subagent
          ├─ code_upsert_eda() → write exploratory code
          ├─ Bash → execute code
          ├─ Iterate until requirements met
          ├─ code_upsert_run() → write production code
          ├─ Bash → execute production workflow
          ├─ More steps? Prompt user to continue
          └─ Return result with "Target: dataset.sheet"
    ↓
ChatService.chat() receives result
    ↓
Extract target using regex: "Target: (\w+)\.(\w+)"
    ↓
Save user message to chat_messages (full content)
Save agent response to chat_messages (full content)
    ↓
Return {message, target_dataset, target_sheet, cost_usd, duration_ms}
    ↓
Frontend receives response and activates view for target sheet
```

## Why Session-Based Approach Works

### Benefits
1. **No Manual History Management**: Claude SDK maintains full conversation history via session_id
2. **Multi-Step Memory**: Session automatically remembers pending steps
3. **Natural User Flow**: User reviews each step, types "continue" to proceed
4. **Error Recovery**: If step fails, session context preserved for retry
5. **Clean Separation**: Claude handles workflow logic, ChatService handles persistence

### Session Memory Tracks
- All previous user messages and agent responses
- Multi-step workflow state (current step, remaining steps)
- Results from previous steps (e.g., created sheets available for next step)
- Active context (mode, datasets, sheets)

### No Need For
- Manual chat history retrieval (`_get_chat_history()`)
- Message summarization (`_summarize_user_message()`, `_summarize_agent_message()`)
- OpenAI intent classifier (Claude does it via @intent-prep)
- Template rendering (Claude handles prompting internally)

## Implementation Notes

### Claude Subagents
- **@intent-prep**: Only uses `mcp__oryxforge` tools (no file access)
- **@data-analyst**: Uses `mcp__oryxforge` + `Bash` tools
- Both use `model: inherit` to match main conversation model

### ChatService Simplifications
- Remove OpenAI LangChain dependencies
- Remove template loading and rendering
- Remove chat history retrieval methods
- Remove message summarization methods
- Keep only: session management, MCP context, target extraction, database persistence

### Target Extraction
ChatService extracts target from Claude's response using regex patterns:
- Primary: `Target: dataset.sheet`
- Fallback: `saved to dataset.sheet`, `written to dataset.sheet`
- Default: `exploration.unknown` if pattern not found

### Database Schema
`chat_messages` table stores:
- Full user message content (no summary needed)
- Full agent response content (no summary needed)
- Metadata: mode, active dataset/sheet, target info, cost, duration
- Session ID = Project ID for grouping conversations
