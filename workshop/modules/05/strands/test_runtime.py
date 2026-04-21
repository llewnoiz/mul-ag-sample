import os
import requests
import json
import uuid
import boto3
from urllib.parse import quote
from argparse import ArgumentParser


def main():
    parser = ArgumentParser(description="Test Bedrock AgentCore Runtime deployed agent.")
    parser.add_argument('--token', help='The JWT token to use when authenticating.')
    parser.add_argument('--runtime-id', help='The ID of the AgentCore Runtime hosting the agent.')
    parser.add_argument('--prompt', default='Who are you?', help='The question you want to ask the agent.')
    parser.add_argument('--region', default=os.getenv('AWS_REGION', 'us-east-1'), help='AWS region for deployment')
    parser.add_argument('--session-id', default='conv-sesion-000000000000000000123', help='session id')
    parser.add_argument('--stream', action='store_true', help='Enable streaming response')
    args = parser.parse_args()

    session_id = args.session_id
    print(f'Invoking agent for session: {session_id}')

    prompt = {
        "prompt": args.prompt,
        "identity": "rroe@example.com",
        "stream": args.stream,
        "token": args.token  # Pass token in payload since headers may not be forwarded
    }

    headers = {
        'Authorization': f'Bearer {args.token}',
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream' if args.stream else 'application/json',
        'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
    }

    account_id = boto3.client('sts').get_caller_identity()['Account']
    escaped_agent_arn = quote(f"arn:aws:bedrock-agentcore:{args.region}:{account_id}:runtime/{args.runtime_id}", safe='')
    print(f'Agent URL: https://bedrock-agentcore.{args.region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations')

    url = f'https://bedrock-agentcore.{args.region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations'

    if args.stream:
        # Streaming request
        print("\n--- Streaming Response ---")
        with requests.post(url, headers=headers, data=json.dumps(prompt), stream=True) as response:
            print(f"HTTP {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text}")
            else:
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        # Handle SSE format
                        if decoded.startswith('data: '):
                            data = decoded[6:]
                            try:
                                chunk = json.loads(data)
                                if chunk.get('error'):
                                    print(f"\n⚠️  Agent error: {chunk['error']}")
                                    if chunk.get('session_id'):
                                        print(f"   Session: {chunk['session_id']}")
                                elif chunk.get('type') == 'text':
                                    print(chunk.get('content', ''), end='', flush=True)
                                elif chunk.get('type') == 'tool_start':
                                    print(f"\n[Tool: {chunk.get('tool')}...]", flush=True)
                                elif chunk.get('type') == 'tool_end':
                                    print(f"[Done]\n", flush=True)
                                elif chunk.get('type') == 'done':
                                    print("\n--- Stream Complete ---")
                                else:
                                    # Unknown chunk type, print as-is
                                    print(json.dumps(chunk, indent=2))
                            except json.JSONDecodeError:
                                print(data, end='', flush=True)
                        else:
                            print(decoded, end='', flush=True)
        print()
    else:
        # Non-streaming request
        response = requests.post(url, headers=headers, data=json.dumps(prompt))
        print(f"HTTP {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
        else:
            try:
                result = response.json()
                if result.get('error'):
                    print(f"⚠️  Agent error: {result['error']}")
                elif result.get('result'):
                    print(result['result'])
                else:
                    print(json.dumps(result, indent=2))
                if result.get('session_id'):
                    print(f"\nSession: {result['session_id']}")
            except json.JSONDecodeError:
                print(response.text)


if __name__ == "__main__":
    main()