"""Claude Agent wrapper for interacting with Claude SDK."""

import asyncio
import sys
from typing import Optional, AsyncIterator
from claude_agent_sdk import ClaudeSDKClient, ResultMessage, ClaudeAgentOptions

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
                    print(message)
                    if isinstance(message, ResultMessage):
                        return message
                return None
            else:
                return None

        except Exception as e:
            print(f"Error during query execution: {e}")
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
            print(f"Error during query execution: {e}")
            raise
        finally:
            await self.client.disconnect()

    @staticmethod
    def query_run(
        query_text: str,
        verbose: bool = True
    ) -> ResultMessage:
        """
        Synchronous wrapper to run a query and get the result.

        This is a convenience method that handles the async execution
        and returns the result directly using predefined agent options.

        Args:
            query_text: The query/prompt to send to Claude
            verbose: If True, print execution details

        Returns:
            ResultMessage containing the response details

        Raises:
            Exception: If an error occurs during query execution
        """
        import time

        async def _run():
            agent = ClaudeAgent()
            return await agent.query(query_text, return_result=True)

        start_time = time.time()
        result = asyncio.run(_run())
        execution_time = time.time() - start_time

        if verbose and result:
            print(f"Result: {result.result}")
            print(f"Cost: ${result.total_cost_usd}")
            print(f"Duration: {result.duration_ms}ms")
            print(f"Execution time: {execution_time:.2f}s")

        return result
