#!/usr/bin/env python3
"""
Minimal Orchestrator Agent Module (Strands SDK)

Strands equivalent of the LangGraph orchestrator_minimal.py.
Coordinates between the DataViz Agent and Electrify Agent.
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator-agent")


@dataclass
class OrchestratorConfig:
    """Configuration for the Orchestrator Agent."""
    model: str = "global.anthropic.claude-sonnet-4-20250514-v1:0"
    user: str = "unknown"
    thread_id: Optional[str] = None
    log_level: str = "INFO"
    electrify_server_script: str = "modules/04/strands/electrify_server.py"
    electrify_server_args: list = None
    electrify_system_prompt: str = "modules/04/strands/electrify_prompt.md"


class OrchestratorAgent:
    """Orchestrator Agent that coordinates DataViz and Electrify agents (Strands SDK)."""

    def __init__(self, config: OrchestratorConfig):
        """Initialize the Orchestrator Agent with configuration."""
        self.config = config
        self.agent = None
        self.dataviz_agent = None
        self.electrify_agent = None
        self.mcp_client = None

        # Configure logging
        logger.setLevel(getattr(logging, config.log_level.upper()))
        logger.info("Initializing Orchestrator Agent...")

        # System prompt for orchestration
        self.system_prompt = """You are an intelligent orchestrator agent that coordinates between two specialized agents:

1. **DataViz Agent**: Creates charts and visualizations from CSV data
2. **Electrify Agent**: Retrieves data from an electricity company database

Your role is to analyze user requests and determine which agent(s) to use."""

    def setup(self):
        """Set up the orchestrator and initialize sub-agents."""
        try:
            logger.info("Setting up Orchestrator agent...")

            # Import agents here to avoid circular imports
            from dataviz_agent import DataVizAgent, DataVizConfig
            from electrify_agent import Application as ElectrifyAgent

            username = self.config.user
            model_id = self.config.model

            # Initialize Bedrock model
            self.model = BedrockModel(
                model_id=model_id,
                region_name=os.getenv('MODEL_REGION', 'us-west-2')
            )
            logger.info("Bedrock model initialized")

            # Initialize DataViz Agent
            dataviz_config = DataVizConfig(
                model=model_id,
                user=username,
                thread_id=f"{self.config.thread_id or username}_dataviz"
            )
            self.dataviz_agent = DataVizAgent(dataviz_config)
            self.dataviz_agent.setup()
            self.dataviz_agent.agent = self.dataviz_agent._create_agent_with_tools()
            logger.info("DataViz agent initialized")

            # Initialize Electrify Agent
            electrify_args = argparse.Namespace(
                user=username,
                thread=f"{self.config.thread_id or username}_electrify",
                system_prompt=self.config.electrify_system_prompt,
                server_script=self.config.electrify_server_script,
                server_args=self.config.electrify_server_args or ["python", "modules/04/strands/electrify_server.py"],
                model=model_id
            )
            self.electrify_agent = ElectrifyAgent(electrify_args)
            self.electrify_agent.setup()
            logger.info("Electrify agent initialized")

            # Set up MCP client for the electrify server
            server_args = self.config.electrify_server_args or ["python", "modules/04/strands/electrify_server.py"]
            self.mcp_client = MCPClient(
                lambda: StdioServerParameters(
                    command=self.config.electrify_server_script,
                    args=server_args
                )
            )

            logger.info("Orchestrator agent setup complete")

        except Exception as e:
            logger.error(f"Error setting up orchestrator: {str(e)}")
            raise

    def _create_tools(self):
        """Create orchestrator tools that wrap sub-agents."""
        dataviz = self.dataviz_agent
        electrify = self.electrify_agent

        @tool
        def use_dataviz_agent(data: str, description: str) -> str:
            """Create data visualizations and charts from CSV data.

            Args:
                data: CSV formatted data as string
                description: Description of what visualization to create
            """
            try:
                result = dataviz.visualize_data(data, description)
                return result
            except Exception as e:
                return f"Error using DataViz agent: {str(e)}"

        @tool
        def use_electrify_agent(query: str) -> str:
            """Query the electricity company database.

            Args:
                query: Natural language query about customers, bills, or rate plans
            """
            try:
                result = electrify.invoke_agent(query)
                return result
            except Exception as e:
                return f"Error using Electrify agent: {str(e)}"

        @tool
        def get_current_datetime() -> str:
            """Get the current date and time in ISO format."""
            return str(datetime.now().astimezone().isoformat())

        @tool
        def convert_json_to_csv(json_data: str) -> str:
            """Convert JSON data to CSV format for visualization.

            Args:
                json_data: JSON formatted data as string
            """
            try:
                import pandas as pd
                from io import StringIO

                data = json.loads(json_data)
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    df = pd.DataFrame([data])
                else:
                    return "Error: Unsupported data format for conversion"

                csv_buffer = StringIO()
                df.to_csv(csv_buffer, index=False)
                return csv_buffer.getvalue()
            except Exception as e:
                return f"Error converting JSON to CSV: {str(e)}"

        return [use_dataviz_agent, use_electrify_agent, get_current_datetime, convert_json_to_csv]

    def invoke_agent(self, query: str) -> str:
        """Invoke the orchestrator agent with a query."""
        if not self.agent:
            raise RuntimeError("Agent not set up. Call setup() first.")

        logger.info(f"Orchestrator query: {query}")

        try:
            response = self.agent(query)
            return str(response)
        except Exception as e:
            logger.error(f"Error invoking orchestrator: {str(e)}")
            return f"Error: {str(e)}"

    def chat_loop(self):
        """Interactive chat loop for CLI usage."""
        print("\n==================== Orchestrator Agent (Strands) ====================")
        print("This orchestrator coordinates between two specialized agents:")
        print("• DataViz Agent: Creates charts and visualizations")
        print("• Electrify Agent: Queries electricity company database")
        print("")
        print("Type 'quit' to exit.")
        print("=====================================================================")

        # Keep MCP client open for the entire chat session
        with self.mcp_client:
            mcp_tools = self.mcp_client.list_tools_sync()
            logger.info(f"Retrieved {len(mcp_tools)} MCP tools for electrify agent")

            # Create the electrify agent with MCP tools
            from electrify_agent import getDateTime as electrify_getDateTime
            self.electrify_agent.agent = Agent(
                model=self.electrify_agent.model,
                system_prompt=self.electrify_agent.system_prompt,
                tools=[electrify_getDateTime] + mcp_tools
            )

            # Create orchestrator tools and agent
            tools = self._create_tools()
            self.agent = Agent(
                model=self.model,
                system_prompt=self.system_prompt,
                tools=tools
            )
            logger.info("Orchestrator agent created")

            while True:
                try:
                    query = input("\n>>> Your query: ").strip()

                    if query.lower() == 'quit':
                        break

                    response = self.invoke_agent(query)
                    print(f"\n{response}")

                except KeyboardInterrupt:
                    print("\n\nExiting...")
                    break
                except Exception as e:
                    error_msg = f"Error in chat loop: {str(e)}"
                    logger.error(error_msg)
                    print(f"\n{error_msg}")


# CLI interface
def main():
    """Main function for CLI usage."""
    load_dotenv('.env')

    parser = argparse.ArgumentParser(description="Orchestrator Agent (Strands)")
    parser.add_argument('-u', '--user', help="Username", default=os.getenv('USER', 'unknown'))
    parser.add_argument('-t', '--thread', help="Thread ID", default=None)
    parser.add_argument('-m', '--model', help="LLM model ID", default="global.anthropic.claude-sonnet-4-20250514-v1:0")

    args = parser.parse_args()

    config = OrchestratorConfig(
        model=args.model,
        user=args.user,
        thread_id=args.thread
    )

    try:
        logger.info("Starting Orchestrator application")

        agent = OrchestratorAgent(config)
        agent.setup()
        agent.chat_loop()

    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        logger.error(f"Main error: {str(e)}")
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
