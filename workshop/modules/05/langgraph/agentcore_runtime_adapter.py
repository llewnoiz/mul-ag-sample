#!/usr/bin/env python3
"""
AgentCore Runtime Adapter for Orchestrator Agent with AgentCore Memory

This adapter wraps the OrchestratorAgentWithMemory to work with Amazon Bedrock
AgentCore Runtime. It uses AgentCore Memory for persistent conversation state
that survives runtime restarts.

Key Features:
- Persistent memory using AgentCore Memory service
- Session ID maps to LangGraph thread_id
- Actor ID support for multi-user scenarios
- Automatic session management via RequestContext
"""

import os
import sys
import json as _json
import asyncio
import logging
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- OTel setup (patches BEFORE instrument()) ---

import opentelemetry.instrumentation.langchain.utils as _otel_lc_utils
import opentelemetry.instrumentation.langchain.callback_handler as _otel_lc_cb

_OrigEncoder = _otel_lc_utils.CallbackFilteredJSONEncoder


def _flatten_content(content):
    """Flatten LangChain content blocks to plain text for OTLP serialization."""
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = _json.loads(stripped)
                if isinstance(parsed, dict) and "statusCode" in parsed:
                    return f"Tool returned status {parsed['statusCode']}"
                return f"JSON response ({len(stripped)} chars)"
            except Exception:
                pass
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    parts.append(f"[tool_use: {block.get('name', '')}]")
            elif isinstance(block, str):
                parts.append(block)
        text = "\n".join(parts) if parts else str(content)
        return _flatten_content(text)
    return str(content)


# Patch A — Clean JSON encoder
class _CleanLangChainEncoder(_OrigEncoder):
    def default(self, o):
        try:
            from langchain_core.messages import BaseMessage
            if isinstance(o, BaseMessage):
                return {
                    "content": _flatten_content(o.content),
                    "type": getattr(o, "type", "unknown"),
                }
        except ImportError:
            pass
        return super().default(o)

_otel_lc_utils.CallbackFilteredJSONEncoder = _CleanLangChainEncoder
_otel_lc_cb.CallbackFilteredJSONEncoder = _CleanLangChainEncoder


def _extract_final_ai_text(messages):
    from langchain_core.messages import AIMessage
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return _flatten_content(msg.content)
    return None


# Patch B — Simplify chain outputs
_orig_on_chain_end = _otel_lc_cb.TraceloopCallbackHandler.on_chain_end

def _patched_on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
    from langchain_core.messages import AIMessage
    if isinstance(outputs, dict) and "messages" in outputs:
        final_text = _extract_final_ai_text(outputs["messages"])
        if final_text:
            outputs = {"messages": [AIMessage(content=final_text)]}
    kwargs = {}
    return _orig_on_chain_end(self, outputs, run_id=run_id,
                              parent_run_id=parent_run_id, **kwargs)

_otel_lc_cb.TraceloopCallbackHandler.on_chain_end = _patched_on_chain_end

# Patch C — Suppress tool spans
_otel_lc_cb.TraceloopCallbackHandler.on_tool_start = lambda self, *a, **kw: None
_otel_lc_cb.TraceloopCallbackHandler.on_tool_end = lambda self, *a, **kw: None

# NOW activate the instrumentor (after all patches)
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
LangchainInstrumentor().instrument()

# --- End OTel setup ---

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.runtime.context import RequestContext
from bedrock_agentcore.memory.session import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

from orchestrator_agent import OrchestratorAgent
from common.types import AgentConfig, StdioServerConfig, IdentityContext
from common.prompts import orchestrator_prompt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("04 - Adapter code called")

# Initialize AgentCore app
app = BedrockAgentCoreApp(debug=True)


async def _setup_agent(payload: Dict[str, Any], context: RequestContext = None):
    """Common setup logic for agent initialization."""
    # Extract prompt from payload
    prompt = payload.get('prompt', '')
    session_id = context.session_id if context else os.getenv('SESSION_ID', 'default-session')
    
    if not prompt:
        return None, None, session_id, "Missing 'prompt' field in request payload"
    
    # Extract identity from payload
    identity = payload.get('identity', None)
    logger.info(f"Identity from payload: {identity}")
    
    # Extract JWT token from request headers or payload
    jwt_token = None
    
    # Try headers first
    if context and context.request_headers:
        logger.info(f"Request headers present: {list(context.request_headers.keys())}")
        auth_header = context.request_headers.get('authorization') or context.request_headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            jwt_token = auth_header[7:]
            logger.info(f"JWT token extracted from headers (len={len(jwt_token)})")
    
    # Fallback to payload if no token in headers
    if not jwt_token and payload.get('token'):
        jwt_token = payload['token']
        logger.info(f"JWT token extracted from payload (len={len(jwt_token)})")
    
    if not jwt_token:
        logger.warning("No JWT token found in headers or payload")
    
    # Create IdentityContext if we have identity info
    identity_context = None
    if identity or jwt_token:
        identity_context = IdentityContext(
            username=identity or 'unknown',
            sub=identity or 'unknown',
            email=identity if identity and '@' in identity else None,
            jwt_token=jwt_token
        )
    
    logger.info(f"Processing request for session {session_id}, identity {identity}: {prompt[:100]}...")
    
    # Use AgentCore Memory for persistent conversation state
    memory_id = os.getenv('BEDROCK_AGENTCORE_MEMORY_ID')
    if memory_id:
        logger.info(f"Using AgentCore Memory: {memory_id}")
    else:
        logger.info("Using InMemorySaver (no persistent memory)")
    
    config = AgentConfig(
        name="orchestrator_agent",
        description="This agent reasons and decides what downstream tools or agents to invoke to complete the user request.",
        identity=identity or 'unknown',
        thread=session_id,
        system_prompt=orchestrator_prompt(),
        model=os.getenv('AGENT_MODEL_ID', 'global.anthropic.claude-sonnet-4-20250514-v1:0'),
        memory=memory_id or '',
        region=os.getenv('AWS_REGION', 'us-east-1'),
        identity_context=identity_context,
    )

    agent = OrchestratorAgent(config)
    await agent.setup()
    agent.config.thread = session_id

    # Query long-term memories and prepend to prompt
    memory_session = None
    original_prompt = prompt
    if memory_id:
        try:
            actor_id = (identity or 'unknown').replace('@', '-').replace('.', '-')
            mgr = MemorySessionManager(memory_id=memory_id, region_name=config.region)
            memory_session = mgr.create_memory_session(actor_id=actor_id, session_id=session_id)
            records = memory_session.search_long_term_memories(query=prompt, namespace_prefix="/", top_k=5)
            if records:
                facts = [r.get('content', {}).get('text', '') for r in records if r.get('content', {}).get('text')]
                if facts:
                    ltm_context = "\n".join(f"- {f}" for f in facts)
                    prompt = f"[Recalled from previous sessions]\n{ltm_context}\n\n[Current request]\n{prompt}"
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
    """Streaming handler for orchestrator agent."""
    session_id = None
    try:
        logger.info("Initializing OrchestratorAgent...")
        
        # Check if streaming is requested
        stream_enabled = payload.get('stream', False)
        
        agent, prompt, session_id, original_prompt, memory_session, error = await _setup_agent(payload, context)
        
        if error:
            yield {"error": error, "session_id": session_id}
            return
        
        logger.info("OrchestratorAgent initialized successfully")
        
        if stream_enabled:
            # Streaming mode - yield chunks as they come
            logger.info("Streaming mode enabled")
            collected_text = []
            try:
                async for chunk in agent.stream(prompt):
                    if isinstance(chunk, dict) and chunk.get("type") == "text":
                        collected_text.append(chunk.get("content", ""))
                    yield chunk
            except (ExceptionGroup, BaseExceptionGroup) as eg:
                # Extract meaningful error messages from the exception group
                error_msgs = []
                for exc in eg.exceptions:
                    error_msgs.append(str(exc))
                combined = "; ".join(error_msgs)
                logger.error(f"Tool call error during streaming: {combined}")
                yield {"type": "text", "content": f"\n\n⚠️ A tool call was denied by policy: {combined}"}
                yield {"type": "done"}
            
            # Write conversation turns to memory for LTM extraction
            if memory_session and collected_text:
                agent_response = "".join(collected_text)
                _write_memory_turns(memory_session, original_prompt, agent_response)
        else:
            # Non-streaming mode - return full result
            try:
                result = await agent.invoke(prompt)
            except (ExceptionGroup, BaseExceptionGroup) as eg:
                error_msgs = []
                for exc in eg.exceptions:
                    error_msgs.append(str(exc))
                combined = "; ".join(error_msgs)
                logger.error(f"Tool call error: {combined}")
                yield {
                    "result": {"text": f"⚠️ A tool call was denied by policy: {combined}", "images": []},
                    "session_id": session_id
                }
                return
            logger.info(f"Request processed successfully for session {session_id}")
            
            # Write conversation turns to memory for LTM extraction
            if memory_session:
                agent_text = result.get("text", "") if isinstance(result, dict) else str(result)
                _write_memory_turns(memory_session, original_prompt, agent_text)
            
            response = {
                "result": result,
                "session_id": session_id
            }
            
            identity = payload.get('identity')
            if identity:
                response["identity"] = identity
            
            yield response
        
    except (ExceptionGroup, BaseExceptionGroup) as eg:
        error_msgs = [str(exc) for exc in eg.exceptions]
        combined = "; ".join(error_msgs)
        logger.error(f"Tool call error (outer): {combined}", exc_info=True)
        if payload.get('stream', False):
            yield {"type": "text", "content": f"\n\n⚠️ A tool call was denied by policy: {combined}"}
            yield {"type": "done"}
        else:
            yield {
                "result": {"text": f"⚠️ A tool call was denied by policy: {combined}", "images": []},
                "session_id": session_id
            }
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
    
    # Agent not yet initialized (will be on first request)
    return PingStatus.HEALTHY


if __name__ == "__main__":
    # Run the AgentCore app
    app.run()
