#!/usr/bin/env python3
"""
Minimal Orchestrator Agent Module

This module implements an orchestrator agent that coordinates between the DataViz Agent
and Electrify Agent using LangChain's create_agent.
"""

import os
import sys
import argparse
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

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
    electrify_server_script: str = "python"
    electrify_server_args: list = None
    electrify_server_path: str = "modules/04/langgraph/electrify_server.py"
    electrify_system_prompt: str = "modules/04/langgraph/electrify_prompt.md"


class OrchestratorAgent:
    """Orchestrator Agent that coordinates DataViz and Electrify agents."""
    
    def __init__(self, config: OrchestratorConfig):
        """Initialize the Orchestrator Agent with configuration."""
        self.config = config
        self.agent = None
        self.dataviz_agent = None
        self.electrify_agent = None
        
        # Configure logging
        logger.setLevel(getattr(logging, config.log_level.upper()))
        logger.info("Initializing Orchestrator Agent...")
        
        # System prompt for orchestration
        self.system_prompt = """You are an intelligent orchestrator agent that coordinates between two specialized agents:

1. **DataViz Agent**: Creates charts and visualizations from CSV data
2. **Electrify Agent**: Retrieves data from an electricity company database

Your role is to analyze user requests and determine which agent(s) to use."""

    async def setup(self):
        """Set up the orchestrator and initialize sub-agents."""
        try:
            logger.info("Setting up Orchestrator agent...")
            
            # Import agents here to avoid circular imports
            from dataviz_agent import DataVizAgent, DataVizConfig
            from electrify_agent import Application as ElectrifyAgent
            
            # Basic config
            username = self.config.user
            thread_id = self.config.thread_id or username
            model_id = self.config.model

            # Initialize LLM
            self.llm = init_chat_model(model=model_id, model_provider='bedrock_converse')
            logger.info("LLM initialized")

            # Agent state configuration
            self.agent_config = {
                "configurable": {"thread_id": thread_id},
                "identity": {"username": username}
            }

            # Initialize DataViz Agent
            dataviz_config = DataVizConfig(
                model=model_id,
                user=username,
                thread_id=f"{thread_id}_dataviz"
            )
            self.dataviz_agent = DataVizAgent(dataviz_config)
            await self.dataviz_agent.setup()
            logger.info("DataViz agent initialized")

            # Initialize Electrify Agent
            electrify_args = argparse.Namespace(
                user=username,
                thread=f"{thread_id}_electrify",
                system_prompt=self.config.electrify_system_prompt,
                server_script=self.config.electrify_server_script,
                server_args=self.config.electrify_server_args or [self.config.electrify_server_path],
                model=model_id
            )
            self.electrify_agent = ElectrifyAgent(electrify_args)
            await self.electrify_agent.setup()
            logger.info("Electrify agent initialized")

            # Define orchestrator tools
            tools = [
                self.create_dataviz_tool(),
                self.create_electrify_tool(),
                self.create_datetime_tool(),
                self.create_json_to_csv_tool()
            ]

            # Set up checkpointer
            checkpointer = InMemorySaver()
            logger.info("Using InMemorySaver for conversation state")

            # Create orchestrator agent
            self.agent = create_agent(
                model=self.llm,
                tools=tools,
                system_prompt=self.system_prompt,
                checkpointer=checkpointer
            )
            
            # Configure recursion limit
            self.agent_config["configurable"]["recursion_limit"] = 50
            logger.info("Orchestrator agent setup complete")

        except Exception as e:
            logger.error(f"Error setting up orchestrator: {str(e)}")
            raise

    def create_dataviz_tool(self):
        """Create a tool that wraps the DataViz agent."""
        @tool(parse_docstring=True)
        async def use_dataviz_agent(data: str, description: str) -> str:
            """Create data visualizations and charts from CSV data."""
            try:
                result = await self.dataviz_agent.visualize_data(data, description)
                return result
            except Exception as e:
                return f"Error using DataViz agent: {str(e)}"
        
        return use_dataviz_agent

    def create_electrify_tool(self):
        """Create a tool that wraps the Electrify agent."""
        @tool(parse_docstring=True)
        async def use_electrify_agent(query: str) -> str:
            """Query the electricity company database."""
            try:
                result = await self.electrify_agent.invoke_agent(query)
                return result
            except Exception as e:
                return f"Error using Electrify agent: {str(e)}"
        
        return use_electrify_agent

    def create_datetime_tool(self):
        """Create a tool for getting current date/time."""
        @tool(parse_docstring=True)
        def get_current_datetime() -> str:
            """Get the current date and time in ISO format."""
            return str(datetime.now().astimezone().isoformat())
        
        return get_current_datetime

    def create_json_to_csv_tool(self):
        """Create a tool for converting JSON data to CSV format."""
        @tool(parse_docstring=True)
        def convert_json_to_csv(json_data: str) -> str:
            """Convert JSON data to CSV format for visualization."""
            try:
                import json
                import pandas as pd
                from io import StringIO
                
                # Parse JSON data
                data = json.loads(json_data)
                
                # Convert to DataFrame
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    df = pd.DataFrame([data])
                else:
                    return f"Error: Unsupported data format for conversion"
                
                # Convert to CSV
                csv_buffer = StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()
                
                return csv_data
                
            except Exception as e:
                return f"Error converting JSON to CSV: {str(e)}"
        
        return convert_json_to_csv

    async def invoke_agent(self, query: str) -> str:
        """Invoke the orchestrator agent with a query."""
        if not self.agent:
            raise RuntimeError("Agent not set up. Call setup() first.")
            
        logger.info(f"Orchestrator query: {query}")
        
        try:
            result = await self.agent.ainvoke({
                "messages": [HumanMessage(content=query)]
            }, config=self.agent_config)
            
            # Get the final state and return the last assistant message
            after_state = await self.agent.aget_state(self.agent_config)
            after_messages = after_state.values.get("messages", []) if after_state else []
            
            if after_messages:
                last_message = after_messages[-1]
                if hasattr(last_message, 'content'):
                    return last_message.content
                else:
                    return str(last_message)
            
            return str(result)
            
        except Exception as e:
            logger.error(f"Error invoking orchestrator: {str(e)}")
            return f"Error: {str(e)}"

    async def chat_loop(self):
        """Interactive chat loop for CLI usage."""
        print("\n==================== Orchestrator Agent ====================")
        print("This orchestrator coordinates between two specialized agents:")
        print("• DataViz Agent: Creates charts and visualizations")
        print("• Electrify Agent: Queries electricity company database")
        print("")
        print("Type 'quit' to exit.")
        print("============================================================")

        while True:
            try:
                query = input("\n>>> Your query: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.invoke_agent(query)
                print(f"\n{response}")

            except (KeyboardInterrupt, asyncio.CancelledError):
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
    
    parser = argparse.ArgumentParser(description="Orchestrator Agent")
    parser.add_argument('-u', '--user', help="Username", default=os.getenv('USER', 'unknown'))
    parser.add_argument('-t', '--thread', help="Thread ID", default=None)
    parser.add_argument('-m', '--model', help="LLM model ID", default="global.anthropic.claude-sonnet-4-20250514-v1:0")
    
    args = parser.parse_args()
    
    config = OrchestratorConfig(
        model=args.model,
        user=args.user,
        thread_id=args.thread
    )
    
    async def run_cli():
        try:
            logger.info("Starting Orchestrator application")
            
            agent = OrchestratorAgent(config)
            await agent.setup()
            await agent.chat_loop()

        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n\nExiting...")
        except Exception as e:
            logger.error(f"Main error: {str(e)}")
            print(str(e))
            sys.exit(1)
    
    asyncio.run(run_cli())


if __name__ == "__main__":
    main()