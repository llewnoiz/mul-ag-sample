#!/usr/bin/env python3
"""
AgentCore Runtime Adapter for Orchestrator Agent (Strands SDK)

Strands equivalent of the LangGraph agentcore_runtime_adapter.py.
Wraps the Strands OrchestratorAgent to work with Amazon Bedrock AgentCore Runtime.

Key Features:
- Persistent memory using AgentCore Memory service
- Session ID support for multi-turn conversations
- Actor ID support for multi-user scenarios
- Automatic session management via RequestContext
"""

import os
import sys
import json
import logging
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.runtime.context import RequestContext
from bedrock_agentcore.memory.session import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

from orchestrator_agent import OrchestratorAgent, OrchestratorConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("05 - Strands Adapter code called")

# Initialize AgentCore app
app = BedrockAgentCoreApp(debug=True)


def _setup_agent(payload: Dict[str, Any], context: RequestContext = None):
    """Common setup logic for agent initialization (synchronous)."""
    prompt = payload.get('prompt', '')
    session_id = context.session_id if context else os.getenv('SESSION_ID', 'default-session')

    if not prompt:
        return None, None, session_id, None, None, "Missing 'prompt' field in request payload"

    # Extract identity from payload
    identity = payload.get('identity', None)
    logger.info(f"Identity from payload: {identity}")

    # Extract JWT token from request headers or payload
    jwt_token = None
    if context and context.request_headers:
        auth_header = context.request_headers.get('authorization') or context.request_headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            jwt_token = auth_header[7:]
            logger.info(f"JWT token extracted from headers (len={len(jwt_token)})")

    if not jwt_token and payload.get('token'):
        jwt_token = payload['token']
        logger.info(f"JWT token extracted from payload (len={len(jwt_token)})")

    logger.info(f"Processing request for session {session_id}, identity {identity}: {prompt[:100]}...")

    memory_id = os.getenv('BEDROCK_AGENTCORE_MEMORY_ID')
    if memory_id:
        logger.info(f"Using AgentCore Memory: {memory_id}")
    else:
        logger.info("No persistent memory configured")

    config = OrchestratorConfig(
        model=os.getenv('AGENT_MODEL_ID', 'global.anthropic.claude-sonnet-4-20250514-v1:0'),
        user=identity or 'unknown',
        thread_id=session_id,
        region=os.getenv('AWS_REGION', 'us-east-1'),
        memory_id=memory_id or '',
        identity=identity or 'unknown',
        jwt_token=jwt_token
    )

    agent = OrchestratorAgent(config)
    agent.setup()

    # Query long-term memories and prepend to prompt
    memory_session = None
    original_prompt = prompt
    if memory_id:
        try:
            actor_id = (identity or 'unknown').replace('@', '-').replace('.', '-')
            mgr = MemorySessionManager(memory_id=memory_id, region_name=config.region)
            memory_session = mgr.create_memory_session(actor_id=actor_id, session_id=session_id)

            # Retrieve short-term memory (previous conversation turns in this session)
            # This is the Strands equivalent of AgentCoreMemorySaver in the LangGraph version
            try:
                previous_turns = memory_session.get_last_k_turns(k=10)
                if previous_turns:
                    stm_lines = []
                    for turn in previous_turns:
                        for msg in turn:
                            role = msg.get('role', 'UNKNOWN')
                            text = msg.get('content', {}).get('text', '')
                            if text:
                                stm_lines.append(f"{role}: {text}")
                    if stm_lines:
                        stm_context = "\n".join(stm_lines)
                        prompt = f"[Conversation history from this session]\n{stm_context}\n\n[Current request]\n{prompt}"
                        logger.info(f"Injected {len(previous_turns)} previous turns as short-term memory context")
            except Exception as e:
                logger.warning(f"Short-term memory retrieval failed (non-fatal): {e}")

            # Retrieve long-term memories (extracted facts from previous sessions)
            records = memory_session.search_long_term_memories(query=prompt, namespace_prefix="/", top_k=5)
            if records:
                facts = [r.get('content', {}).get('text', '') for r in records if r.get('content', {}).get('text')]
                if facts:
                    ltm_context = "\n".join(f"- {f}" for f in facts)
                    prompt = f"[Recalled from previous sessions]\n{ltm_context}\n\n{prompt}"
                    logger.info(f"Injected {len(facts)} long-term memories into prompt")
        except Exception as e:
            logger.warning(f"LTM retrieval failed (non-fatal): {e}")

    return agent, prompt, session_id, original_prompt, memory_session, None


def _write_memory_turns(memory_session, user_prompt: str, agent_response: str):
    """Write user prompt and agent response to memory for LTM strategy extraction."""
    try:
        memory_session.add_turns(messages=[
            ConversationalMessage(user_prompt, MessageRole.USER),
            ConversationalMessage(agent_response, MessageRole.ASSISTANT),
        ])
        logger.info("Wrote conversation turns to memory for LTM extraction")
    except Exception as e:
        logger.warning(f"Failed to write memory turns (non-fatal): {e}")


@app.entrypoint
async def orchestrator_handler(payload: Dict[str, Any], context: RequestContext = None):
    """Handler for orchestrator agent."""
    session_id = None
    try:
        logger.info("Initializing Strands OrchestratorAgent...")

        agent, prompt, session_id, original_prompt, memory_session, error = _setup_agent(payload, context)

        if error:
            yield {"error": error, "session_id": session_id}
            return

        logger.info("OrchestratorAgent initialized successfully")

        # Open MCP contexts for sub-agents
        mcp_contexts = []

        if agent.dataviz_agent and agent.dataviz_agent.mcp_client:
            agent.dataviz_agent.mcp_client.__enter__()
            mcp_contexts.append(agent.dataviz_agent.mcp_client)
            mcp_tools = agent.dataviz_agent.mcp_client.list_tools_sync()
            from dataviz_agent import getDateTime as dataviz_getDateTime
            from strands import Agent as StrandsAgent
            # Use ONLY gateway tools (+ getDateTime) so policy enforcement applies.
            # Do NOT include BUILTIN_TOOLS — they duplicate gateway tools and bypass policies.
            agent.dataviz_agent.agent = StrandsAgent(
                model=agent.dataviz_agent.model,
                system_prompt=agent.dataviz_agent._system_prompt,
                tools=[dataviz_getDateTime] + mcp_tools
            )

        if agent.electrify_agent and agent.electrify_agent.https_mcp_client:
            agent.electrify_agent.https_mcp_client.__enter__()
            mcp_contexts.append(agent.electrify_agent.https_mcp_client)
            from electrify_agent import getDateTime as electrify_getDateTime, calculateSavings as electrify_calculateSavings
            from strands import Agent as StrandsAgent
            https_tools = agent.electrify_agent.https_mcp_client.list_tools_sync()
            agent.electrify_agent.agent = StrandsAgent(
                model=agent.electrify_agent.model,
                system_prompt=agent.electrify_agent.system_prompt,
                tools=[electrify_getDateTime, electrify_calculateSavings] + https_tools
            )

        try:
            # Create orchestrator tools and agent
            tools = agent._create_tools()
            from strands import Agent as StrandsAgent

            stream_enabled = payload.get('stream', False)

            if stream_enabled:
                # Streaming mode - use stream_async and yield chunks
                agent.agent = StrandsAgent(
                    model=agent.model,
                    system_prompt=agent.system_prompt,
                    tools=tools,
                    callback_handler=None
                )
                collected_text = []
                active_tool = None
                async for event in agent.agent.stream_async(prompt):
                    if isinstance(event, dict):
                        data = event.get("data", "")
                        if data and isinstance(data, str):
                            if active_tool:
                                yield {"type": "tool_end"}
                                active_tool = None
                            collected_text.append(data)
                            yield {"type": "text", "content": data}
                        elif event.get("current_tool_use") and not event.get("complete"):
                            tool_name = event["current_tool_use"].get("name", "unknown")
                            if tool_name != active_tool:
                                if active_tool:
                                    yield {"type": "tool_end"}
                                active_tool = tool_name
                                yield {"type": "tool_start", "tool": tool_name}

                if active_tool:
                    yield {"type": "tool_end"}

                # Extract chart images from tool results in conversation history
                import re
                chart_pattern = r'<chart>(data:image/svg\+xml;base64,[^<]+)</chart>'
                full_streamed = "".join(collected_text)
                collected_images = []
                if hasattr(agent.agent, 'messages'):
                    for msg in agent.agent.messages:
                        role = msg.get("role", "")
                        content = msg.get("content", [])
                        if isinstance(content, str):
                            collected_images.extend(re.findall(chart_pattern, content))
                        elif isinstance(content, list):
                            for block in content:
                                text = ""
                                if isinstance(block, str):
                                    text = block
                                elif isinstance(block, dict):
                                    text = block.get("text", "") or block.get("content", "") or str(block)
                                collected_images.extend(re.findall(chart_pattern, text))

                logger.info(f"Chart extraction: scanned messages, found {len(collected_images)} charts")

                seen = set()
                for img in collected_images:
                    if img not in full_streamed and img not in seen:
                        seen.add(img)
                        yield {"type": "text", "content": f"<chart>{img}</chart>"}

                yield {"type": "done"}

                if memory_session and collected_text:
                    _write_memory_turns(memory_session, original_prompt, "".join(collected_text))
            else:
                # Non-streaming mode
                agent.agent = StrandsAgent(
                    model=agent.model,
                    system_prompt=agent.system_prompt,
                    tools=tools
                )
                result_text = agent.invoke_agent(prompt)

                # Extract chart images from conversation history
                import re
                chart_pattern = r'<chart>(data:image/svg\+xml;base64,[^<]+)</chart>'
                images = []
                for msg in agent.agent.messages:
                    role = msg.get("role", "")
                    content = msg.get("content", [])
                    if isinstance(content, str):
                        images.extend(re.findall(chart_pattern, content))
                    elif isinstance(content, list):
                        for block in content:
                            text = ""
                            if isinstance(block, str):
                                text = block
                            elif isinstance(block, dict):
                                text = block.get("text", "") or block.get("content", "") or str(block)
                            images.extend(re.findall(chart_pattern, text))

                logger.info(f"Chart extraction (non-stream): scanned {len(agent.agent.messages)} messages, found {len(images)} charts")

                if memory_session:
                    _write_memory_turns(memory_session, original_prompt, result_text)

                response = {
                    "result": {"text": result_text, "images": images},
                    "session_id": session_id
                }

                identity = payload.get('identity')
                if identity:
                    response["identity"] = identity

                yield response

        finally:
            for ctx in mcp_contexts:
                try:
                    ctx.__exit__(None, None, None)
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        yield {
            "error": f"Agent error: {str(e)}",
            "session_id": session_id
        }


@app.ping
def health_check():
    """Custom health check for the orchestrator agent."""
    from bedrock_agentcore.runtime import PingStatus
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run()
