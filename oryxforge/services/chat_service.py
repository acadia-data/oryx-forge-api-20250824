"""Chat Service for interactive data analysis conversations."""

import re
from typing import Dict, Optional, Any
from loguru import logger

from .utils import init_supabase_client
from .project_service import ProjectService
from ..agents.claude import ClaudeAgent


class ChatService:
    """
    Service class for managing chat sessions with Claude Agent.

    Uses Claude Agent SDK with session resumption for conversation continuity.
    Claude subagents (@intent-prep, @data-analyst) handle intent classification and analysis.
    """

    def __init__(self, user_id: str, project_id: str):
        """
        Initialize Chat Service.

        Args:
            user_id: User ID
            project_id: Project ID (also used as session_id for Claude SDK)
        """
        self.user_id = user_id
        self.project_id = project_id
        self.session_id = project_id  # session_id = project_id for Claude SDK session resumption

        # Initialize clients and services
        self.supabase_client = init_supabase_client()
        self.project_service = ProjectService(project_id=project_id, user_id=user_id)

        logger.debug(f"ChatService initialized for user {user_id}, project {project_id}")

    def _extract_target_from_result(self, result_text: str) -> Dict[str, str]:
        """
        Extract target dataset/sheet from Claude's result.

        Looks for pattern: "Target: {dataset}.{sheet}"

        Args:
            result_text: Claude's response text

        Returns:
            Dict with 'dataset' and 'sheet' keys
        """
        # Primary pattern: "Target: dataset.sheet"
        match = re.search(r'Target:\s*(\w+)\.(\w+)', result_text, re.IGNORECASE)
        if match:
            return {'dataset': match.group(1), 'sheet': match.group(2)}

        # Fallback: "saved to dataset.sheet"
        match = re.search(r'(?:saved to|written to|output to)\s+(\w+)\.(\w+)', result_text, re.IGNORECASE)
        if match:
            return {'dataset': match.group(1), 'sheet': match.group(2)}

        # Default if not found
        logger.warning("Could not extract target from result, using defaults")
        return {'dataset': 'exploration', 'sheet': 'unknown'}

    def chat(self, message_user: str, mode: str, ds_active: Optional[str] = None,
             sheet_active: Optional[str] = None) -> Dict[str, Any]:
        """
        Process chat message using Claude Agent with session resumption.

        Claude subagents (@intent-prep, @data-analyst) handle intent classification and analysis.
        Session resumption provides conversation continuity via session_id = project_id.

        Args:
            message_user: User's message
            mode: Current mode (explore, edit, plan)
            ds_active: Active dataset ID (optional)
            sheet_active: Active sheet ID (optional)

        Returns:
            Dict with keys:
                - message: Agent response text
                - target_dataset: Target dataset name_python
                - target_sheet: Target sheet name_python
                - cost_usd: Cost of operation
                - duration_ms: Duration of operation
        """
        logger.info(f"Processing chat in {mode} mode")

        try:
            # Step 1: Build minimal context for Claude
            context_parts = []
            if mode:
                context_parts.append(f"Mode: {mode}")

            if ds_active:
                ds = self.project_service.ds_get(id=ds_active)
                context_parts.append(f"Active dataset: {ds['name_python']}")

            if sheet_active:
                sheet = self.project_service.sheet_get(id=sheet_active)
                context_parts.append(f"Active sheet: {sheet['name_python']}")

            context = "\n".join(context_parts) if context_parts else "No active context"

            # Build prompt based on mode
            if mode == 'explore':
                # Use data analyst pattern
                prompt = f"""use the data analyst instructions in @~/.claude/claude-data-analyst.md to respond to the user data analysis request. additional information on how to load and save tables, charts and reports are in @~/.claude/io-service-agent-guide.md

user request: {message_user}"""
            else:
                # Keep existing prompt format for other modes
                prompt = f"""{message_user}

Context:
{context}

Use @intent-prep to prepare data context, then @data-analyst to perform analysis.
"""

            # Step 2: Call Claude with session resumption
            # Session manages conversation history automatically
            logger.info("Calling Claude agent with session resumption")
            result = ClaudeAgent.query_run(
                query_text=prompt,
                session_id=self.session_id,
                verbose=True
            )

            # Step 3: Extract target from result
            target_info = self._extract_target_from_result(result.result)

            # Step 4: Save messages to database (full content, no summaries)
            # User message
            self.supabase_client.table("chat_messages").insert({
                "user_owner": self.user_id,
                "project_id": self.project_id,
                "session_id": self.session_id,
                "role": "user",
                "content": message_user,
                "metadata": {
                    "mode": mode,
                    "ds_active": ds_active,
                    "sheet_active": sheet_active
                }
            }).execute()

            # Agent message
            self.supabase_client.table("chat_messages").insert({
                "user_owner": self.user_id,
                "project_id": self.project_id,
                "session_id": self.session_id,
                "role": "agent",
                "content": result.result,
                "metadata": {
                    "mode": mode,
                    "target": target_info,
                    "cost_usd": result.total_cost_usd,
                    "duration_ms": result.duration_ms
                }
            }).execute()

            logger.success("Saved messages to database")

            # Step 5: Return response
            return {
                "message": result.result,
                "target_dataset": target_info['dataset'],
                "target_sheet": target_info['sheet'],
                "cost_usd": result.total_cost_usd,
                "duration_ms": result.duration_ms
            }

        except Exception as e:
            logger.error(f"Chat processing failed: {str(e)}")
            raise ValueError(f"Failed to process chat message: {str(e)}")
