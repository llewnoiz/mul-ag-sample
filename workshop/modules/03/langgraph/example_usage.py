"""
Example usage of the DataViz Agent Module

This file demonstrates different ways to use the data visualization agent
both as a module and with direct tool calls.
"""

import asyncio
from modules.dataviz import (
    DataVizAgent,
    DataVizConfig,
    create_dataviz_agent,
    quick_visualize,
    create_bar_chart,
    create_pie_chart,
    analyze_data_structure
)

# Sample data
SAMPLE_DATA = """Month,Sales,Region
Jan,1000,North
Feb,1200,North
Mar,800,South
Apr,1500,South
May,1100,North
Jun,1300,South"""

SAMPLE_DATA_2 = """Product,Price,Category,Rating
Laptop,999,Electronics,4.5
Phone,699,Electronics,4.2
Desk,299,Furniture,4.0
Chair,199,Furniture,4.3
Tablet,399,Electronics,4.1"""


async def example_1_quick_visualize():
    """Example 1: Quick visualization with minimal setup."""
    print("=== Example 1: Quick Visualization ===")
    
    result = await quick_visualize(
        data=SAMPLE_DATA,
        description="Create a bar chart showing sales by month",
        model="global.anthropic.claude-sonnet-4-20250514-v1:0"
    )
    
    print("Result:", result[:200] + "..." if len(result) > 200 else result)
    print()


async def example_2_agent_with_config():
    """Example 2: Using agent with custom configuration."""
    print("=== Example 2: Agent with Custom Config ===")
    
    config = DataVizConfig(
        model="global.anthropic.claude-sonnet-4-20250514-v1:0",
        user="data_analyst",
        thread_id="analysis_session_1",
        log_level="DEBUG"
    )
    
    agent = DataVizAgent(config)
    await agent.setup()
    
    result = await agent.visualize_data(
        data=SAMPLE_DATA_2,
        description="Create a scatter plot showing the relationship between price and rating, colored by category"
    )
    
    print("Result:", result[:200] + "..." if len(result) > 200 else result)
    print()


async def example_2b_agent_with_mcp_config():
    """Example 2b: Using agent with MCP YAML configuration."""
    print("=== Example 2b: Agent with MCP YAML Config ===")
    
    config = DataVizConfig(
        model="global.anthropic.claude-sonnet-4-20250514-v1:0",
        user="data_analyst",
        mcp_config_file="modules/03/langgraph/dataviz.yml",  # Use the sample config file
        log_level="INFO"
    )
    
    agent = DataVizAgent(config)
    await agent.setup()
    
    result = await agent.visualize_data(
        data=SAMPLE_DATA,
        description="Create a visualization showing sales trends"
    )
    
    print("Result with MCP config:", result[:200] + "..." if len(result) > 200 else result)
    print()


async def example_2c_agent_save_to_file():
    """Example 2c: Using agent with file saving enabled."""
    print("=== Example 2c: Agent with File Saving ===")
    
    config = DataVizConfig(
        model="global.anthropic.claude-sonnet-4-20250514-v1:0",
        user="data_analyst",
        save_charts_to_file=True,
        chart_output_dir="./charts",
        log_level="INFO"
    )
    
    agent = DataVizAgent(config)
    await agent.setup()
    
    result = await agent.visualize_data(
        data=SAMPLE_DATA_2,
        description="Create a bar chart showing product prices by category and save it to a file"
    )
    
    print("Result with file saving:", result)
    print()


async def example_3_convenience_function():
    """Example 3: Using the convenience function."""
    print("=== Example 3: Convenience Function ===")
    
    agent = await create_dataviz_agent()
    
    # Multiple visualizations with the same agent
    result1 = await agent.visualize_data(
        data=SAMPLE_DATA,
        description="Analyze the data structure first, then create the most appropriate visualization"
    )
    
    print("Analysis and visualization:", result1[:200] + "..." if len(result1) > 200 else result1)
    print()


async def example_4_direct_tool_usage():
    """Example 4: Using tools directly without the agent."""
    print("=== Example 4: Direct Tool Usage ===")
    
    # Analyze data structure
    analysis = analyze_data_structure.invoke({"data": SAMPLE_DATA})
    print("Data Analysis:")
    print(analysis)
    print()
    
    # Create a bar chart directly
    chart = create_bar_chart.invoke({
        "data": SAMPLE_DATA,
        "x_column": "Month",
        "y_column": "Sales",
        "title": "Monthly Sales",
        "x_label": "Month",
        "y_label": "Sales ($)"
    })
    
    print("Direct chart creation:", chart[:100] + "..." if len(chart) > 100 else chart)
    print()


async def example_4b_direct_tool_with_file_saving():
    """Example 4b: Using tools directly with file saving."""
    print("=== Example 4b: Direct Tool Usage with File Saving ===")
    
    # Import the configuration function
    from modules.dataviz import set_chart_config
    
    # Enable file saving for direct tool usage
    set_chart_config(save_to_file=True, output_dir="./direct_charts")
    
    # Create a pie chart directly
    chart = create_pie_chart.invoke({
        "data": SAMPLE_DATA_2,
        "values_column": "Price",
        "names_column": "Product",
        "title": "Product Price Distribution"
    })
    
    print("Direct chart with file saving:", chart)
    
    # Reset to default (base64 encoding)
    set_chart_config(save_to_file=False)
    print()


async def example_5_conversational_agent():
    """Example 5: Multiple interactions with the same agent."""
    print("=== Example 5: Conversational Agent ===")
    
    agent = await create_dataviz_agent()
    
    # First interaction
    result1 = await agent.invoke_agent(
        "I have sales data by month and region. What would be the best way to visualize this?"
    )
    print("Agent recommendation:", result1[:200] + "..." if len(result1) > 200 else result1)
    
    # Second interaction with data
    result2 = await agent.visualize_data(
        data=SAMPLE_DATA,
        description="Based on your recommendation, create that visualization"
    )
    print("Visualization result:", result2[:200] + "..." if len(result2) > 200 else result2)
    print()


async def main():
    """Run all examples."""
    print("DataViz Agent Module Usage Examples")
    print("=" * 50)
    
    try:
        await example_1_quick_visualize()
        await example_2_agent_with_config()
        await example_2b_agent_with_mcp_config()
        await example_2c_agent_save_to_file()
        await example_3_convenience_function()
        await example_4_direct_tool_usage()
        await example_4b_direct_tool_with_file_saving()
        await example_5_conversational_agent()
        
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Make sure environment is set up
    import os
    from dotenv import load_dotenv
    load_dotenv('.env')
    
    # Run examples
    asyncio.run(main())