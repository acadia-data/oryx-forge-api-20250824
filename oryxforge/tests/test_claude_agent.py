"""Integration tests for ClaudeAgent."""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from claude_agent_sdk import ResultMessage

from ..agents.claude import ClaudeAgent


class TestClaudeAgent:
    """Integration test cases for ClaudeAgent."""

    @pytest.fixture
    def mock_result_message(self):
        """Create a mock ResultMessage for testing."""
        result = MagicMock(spec=ResultMessage)
        result.result = "Test response"
        result.total_cost_usd = 0.001
        result.duration_ms = 500
        return result

    @pytest.fixture
    def mock_sdk_client(self, mock_result_message):
        """Create a mock ClaudeSDKClient."""
        client = AsyncMock()
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.query = AsyncMock()

        async def mock_receive_messages():
            yield "Thinking..."
            yield mock_result_message

        client.receive_messages = mock_receive_messages
        return client

    def test_init_with_predefined_options(self):
        """Test initialization with predefined options."""
        with patch('oryxforge.agents.claude.ClaudeSDKClient') as mock_client, \
             patch('oryxforge.agents.claude.ClaudeAgentOptions') as mock_options:

            agent = ClaudeAgent()
            assert agent.client is not None

            # Verify ClaudeAgentOptions was called with correct predefined settings
            mock_options.assert_called_once()
            call_kwargs = mock_options.call_args[1]

            assert 'expert python programmer' in call_kwargs['system_prompt'].lower()
            assert call_kwargs['permission_mode'] == "acceptEdits"
            assert "mcp__oryxforge" in call_kwargs['allowed_tools']
            assert "oryxforge" in call_kwargs['mcp_servers']

            # Verify client was initialized with options
            mock_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_result(self, mock_sdk_client, mock_result_message):
        """Test query method returning a result."""
        with patch('oryxforge.agents.claude.ClaudeSDKClient', return_value=mock_sdk_client):
            agent = ClaudeAgent()
            result = await agent.query("What is 2+2?", return_result=True)

            assert result == mock_result_message
            mock_sdk_client.connect.assert_called_once()
            mock_sdk_client.query.assert_called_once_with("What is 2+2?")
            mock_sdk_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_without_result(self, mock_sdk_client):
        """Test query method without returning result."""
        with patch('oryxforge.agents.claude.ClaudeSDKClient', return_value=mock_sdk_client):
            agent = ClaudeAgent()
            result = await agent.query("Test query", return_result=False)

            assert result is None
            mock_sdk_client.connect.assert_called_once()
            mock_sdk_client.query.assert_called_once_with("Test query")
            mock_sdk_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_stream(self, mock_sdk_client, mock_result_message):
        """Test query_stream method."""
        with patch('oryxforge.agents.claude.ClaudeSDKClient', return_value=mock_sdk_client):
            agent = ClaudeAgent()
            messages = []

            async for message in agent.query_stream("Streaming test"):
                messages.append(message)

            assert len(messages) == 2
            assert messages[0] == "Thinking..."
            assert messages[1] == mock_result_message
            mock_sdk_client.connect.assert_called_once()
            mock_sdk_client.query.assert_called_once_with("Streaming test")
            mock_sdk_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_error_handling(self):
        """Test error handling in query method."""
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.query = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.disconnect = AsyncMock()

        with patch('oryxforge.agents.claude.ClaudeSDKClient', return_value=mock_client):
            agent = ClaudeAgent()

            with pytest.raises(Exception, match="Connection error"):
                await agent.query("Test query")

            # Ensure disconnect is called even on error
            mock_client.disconnect.assert_called_once()

    @pytest.mark.skip(reason="Test uses mocks - requires refactoring for real integration testing")
    def test_query_run_success(self, mock_result_message):
        """Test query_run static method success."""
        async def mock_query(*args, **kwargs):
            return mock_result_message

        with patch.object(ClaudeAgent, 'query', mock_query), \
             patch('builtins.print') as mock_print:

            result = ClaudeAgent.query_run(
                "What is Python?",
                verbose=True
            )

            assert result == mock_result_message
            # Check that verbose output was printed
            assert any("Result:" in str(call) for call in mock_print.call_args_list)
            assert any("Cost:" in str(call) for call in mock_print.call_args_list)

    @pytest.mark.skip(reason="Test uses mocks - requires refactoring for real integration testing")
    def test_query_run_no_verbose(self, mock_result_message):
        """Test query_run with verbose=False."""
        async def mock_query(*args, **kwargs):
            return mock_result_message

        with patch.object(ClaudeAgent, 'query', mock_query), \
             patch('builtins.print') as mock_print:

            result = ClaudeAgent.query_run(
                "Test query",
                verbose=False
            )

            assert result == mock_result_message
            # Ensure nothing was printed for result/cost/duration
            result_prints = [call for call in mock_print.call_args_list
                           if "Result:" in str(call) or "Cost:" in str(call)]
            assert len(result_prints) == 0

if __name__ == '__main__':
    pytest.main([__file__])
