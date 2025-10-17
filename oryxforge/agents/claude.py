"""Claude Agent wrapper for interacting with Claude SDK."""

import asyncio
import sys
from typing import Optional, AsyncIterator
from claude_agent_sdk import ClaudeSDKClient, ResultMessage, ClaudeAgentOptions
from loguru import logger

# Fix Windows console encoding for unicode characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


class ClaudeAgent:
    """
    Wrapper class for Claude Agent SDK client.

    Provides a simple interface for querying Claude and handling responses.
    Uses predefined options with MCP server integration.
    """

    def __init__(self):
        """
        Initialize Claude Agent with predefined options.

        Options include:
        - Expert Python programmer system prompt
        - Auto-accept edits permission mode
        - Allowed tools: Read, Write, Edit, Bash, Glob, Grep, mcp__oryxforge
        - OryxForge MCP server integration
        """
        options = ClaudeAgentOptions(
            system_prompt='You are an expert python programmer. Ask the user for input when necessary to proceed.',
            permission_mode="acceptEdits",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "mcp__oryxforge"],
            mcp_servers={
                "oryxforge": {
                    "type": "stdio",
                    "command": "oryxforge",
                    "args": ["mcp", "serve"]
                }
            },
        )
        self.client = ClaudeSDKClient(options=options)

    async def query(
        self,
        query_text: str,
        return_result: bool = True
    ) -> Optional[ResultMessage]:
        """
        Send a query to Claude and optionally wait for the result.

        Args:
            query_text: The query/prompt to send to Claude
            return_result: If True, wait for and return the ResultMessage.
                          If False, just send the query and return None.

        Returns:
            ResultMessage if return_result is True, None otherwise

        Raises:
            Exception: If an error occurs during query execution
        """
        try:
            await self.client.connect()
            await self.client.query(query_text)

            if return_result:
                # Iterate through messages until we get the ResultMessage
                async for message in self.client.receive_messages():
                    logger.info(str(message))
                    if isinstance(message, ResultMessage):
                        return message
                return None
            else:
                return None

        except Exception as e:
            logger.error(f"Error during query execution: {e}")
            raise
        finally:
            await self.client.disconnect()

    async def query_stream(
        self,
        query_text: str
    ) -> AsyncIterator:
        """
        Send a query to Claude and stream all messages.

        Args:
            query_text: The query/prompt to send to Claude

        Yields:
            All messages from the Claude SDK

        Raises:
            Exception: If an error occurs during query execution
        """
        try:
            await self.client.connect()
            await self.client.query(query_text)

            async for message in self.client.receive_messages():
                yield message

        except Exception as e:
            logger.error(f"Error during query execution: {e}")
            raise
        finally:
            await self.client.disconnect()

    @staticmethod
    def query_run(
        query_text: str,
        verbose: bool = True,
        session_id: Optional[str] = None
    ) -> ResultMessage:
        """
        Synchronous wrapper to run a query and get the result.

        This is a convenience method that handles the async execution
        and returns the result directly using predefined agent options.

        Args:
            query_text: The query/prompt to send to Claude
            verbose: If True, print execution details
            session_id: Optional session ID to resume previous conversation

        Returns:
            ResultMessage containing the response details

        Raises:
            Exception: If an error occurs during query execution

        Note:
            After successful query execution, automatically commits and pushes
            all changes (modified and untracked files) to the git repository
            with message "edits <UTC timestamp>". Git failures are logged but
            do not affect query completion.
        """
        import time
        from datetime import datetime
        from ..services.repo_service import RepoService

        async def _run():
            agent = ClaudeAgent()
            await agent.client.connect()

            # Query with session_id parameter (defaults to 'default' if None)
            await agent.client.query(query_text, session_id=session_id or 'default')

            # Get result
            async for message in agent.client.receive_messages():
                logger.info(str(message))
                if isinstance(message, ResultMessage):
                    await agent.client.disconnect()
                    return message

            await agent.client.disconnect()
            return None

        start_time = time.time()
        result = asyncio.run(_run())
        execution_time = time.time() - start_time

        # Auto-commit and push changes after successful query
        if result:
            try:
                repo_service = RepoService()
                commit_message = f"edits {datetime.utcnow().isoformat()}"
                commit_hash = repo_service.push(commit_message)
                logger.success(f"Auto-committed changes: {commit_hash[:8]}")
            except ValueError as e:
                logger.warning(f"Git auto-commit failed (non-blocking): {e}")
            except Exception as e:
                logger.warning(f"Unexpected git error (non-blocking): {e}")

        if verbose and result:
            logger.info(f"Result: {result.result}")
            logger.info(f"Cost: ${result.total_cost_usd}")
            logger.info(f"Duration: {result.duration_ms}ms")
            logger.info(f"Execution time: {execution_time:.2f}s")

        return result
