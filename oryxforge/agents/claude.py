import asyncio
from claude_agent_sdk import ClaudeSDKClient, ResultMessage, ClaudeAgentOptions

import os
import sys
import adtiam

# Fix Windows console encoding for unicode characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

adtiam.load_creds('adt-llm')
# os.environ['ANTHROPIC_API_KEY']=adtiam.creds['llm']['claude']['agent-sdk']

async def query_csv_load(csv_path: str = "@data/hpi_master.csv") -> ResultMessage:
    """
    Query Claude to load CSV file into a dataframe and return the ResultMessage.

    Args:
        csv_path: Path to the CSV file (default: "@data/hpi_master.csv")

    Returns:
        ResultMessage containing the response details
    """
    # Note: ClaudeAgentOptions with system_prompt causes timeout issues on some systems
    # Using inline instructions in the query instead
    client = ClaudeSDKClient()
    options = ClaudeAgentOptions(system_prompt='your are an expert python programmer. ask the user for input when necessary to proceed.')
    client = ClaudeSDKClient(options=options)

    try:
        await client.connect()
        # await client.query(f"{csv_path} load the first 10 lines into a python dataframe")
        await client.query(f" ask me back what i would like to do next")

        # Iterate through messages until we get the ResultMessage
        async for message in client.receive_messages():
            print(message)
            if isinstance(message, ResultMessage):
                return message

    except Exception as e:
        print(f"Error during query execution: {e}")
        raise
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import time
    start_time = time.time()
    result = asyncio.run(query_csv_load())
    execution_time = time.time() - start_time
    print(f"Result: {result.result}")
    print(f"Cost: ${result.total_cost_usd}")
    print(f"Duration: {result.duration_ms}ms")
    print(f"Execution time: {execution_time:.2f}s")
