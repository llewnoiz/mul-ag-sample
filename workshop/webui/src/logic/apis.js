// import
import { fetchAuthSession } from "aws-amplify/auth";
import { AmplifyConfig } from '../components/amplify.js';

// Helper function to get API endpoint
const getApiEndpoint = (apiName) => {
    const endpoint = AmplifyConfig.API.endpoints.find(e => e.name === apiName);
    return endpoint ? endpoint.endpoint : '/api';
};

// Helper function to build query string
const buildQueryString = (params) => {
    if (!params || Object.keys(params).length === 0) return '';
    const queryParams = new URLSearchParams(params);
    return `?${queryParams.toString()}`;
};

// Helper function for GET requests
const apiFetch = async (apiName, path, options = {}) => {
    try {
        const session = await fetchAuthSession();
        const token = (apiName === "agentcore-runtime") ? session.tokens?.accessToken?.toString() : session.tokens?.idToken?.toString();
        
        if (!token) {
            throw new Error('No authentication token available');
        }

        const baseUrl = getApiEndpoint(apiName);
        const queryString = options.queryStringParameters ? buildQueryString(options.queryStringParameters) : '';
        const url = `${baseUrl}${path}${queryString}`;

        const fetchOptions = {
            method: options.method || 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        if (options.body) {
            fetchOptions.body = JSON.stringify(options.body);
        }

        const response = await fetch(url, fetchOptions);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API ${options.method || 'GET'} ${path} error:`, error);
        throw error;
    }
};

// get billing (bills)
export const apiGetBilling = async (params = null) => {
    try {
        const result = await apiFetch("cloudfront-api", "/billing", {
            queryStringParameters: params || {}
        });
        return result.Invoices ? result.Invoices : [];
    } catch (error) {
        console.error("apiGetBilling error:", error);
        return false;
    }
};

// get customer(s)
export const apiGetCustomers = async (params = null) => {
    try {
        const result = await apiFetch("cloudfront-api", "/customers", {
            queryStringParameters: params || {}
        });
        return result.Customers ? result.Customers : [];
    } catch (error) {
        console.error("apiGetCustomers error:", error);
        return false;
    }
};

// get meters (typically for a provider)
export const apiGetDevices = async (params = null) => {
    try {
        const result = await apiFetch("cloudfront-api", "/devices", {
            queryStringParameters: params || {}
        });
        return result.Devices ? result.Devices : [];
    } catch (error) {
        console.error("apiGetDevices error:", error);
        return false;
    }
};

// get metrics
export const apiGetMetrics = async (params = null) => {
    try {
        const result = await apiFetch("cloudfront-api", "/metrics", {
            queryStringParameters: params || {}
        });
        return result.Metrics ? result.Metrics : [];
    } catch (error) {
        console.error("apiGetMetrics error:", error);
        return false;
    }
};

// get payments
export const apiGetPayments = async (params = null) => {
    try {
        const result = await apiFetch("cloudfront-api", "/payments", {
            queryStringParameters: params || {}
        });
        return result.Payments ? result.Payments : [];
    } catch (error) {
        console.error("apiGetPayments error:", error);
        return false;
    }
};

// get invoice
export const apiGetInvoice = async (params = null) => {
    try {
        const result = await apiFetch("cloudfront-api", "/invoice", {
            queryStringParameters: params || {}
        });
        return result.Invoice ? result.Invoice : null;
    } catch (error) {
        console.error("apiGetInvoice error:", error);
        return false;
    }
};

// set a customer
export const apiSetCustomer = async (params = null) => {
    try {
        const result = await apiFetch("cloudfront-api", "/customers", {
            method: 'POST',
            body: params
        });
        return result.Customers ? result.Customers : [];
    } catch (error) {
        console.error("apiSetCustomer error:", error);
        return false;
    }
};

// chat with assistant
export const apiChatMessage = async (params = null) => {
    try {
        const { prompt, session_id, identity } = params;
        const session = await fetchAuthSession();
        const token = session.tokens?.accessToken?.toString();
        
        const result = await apiFetch("agentcore-runtime", "", {
            method: 'POST',
            headers: {
                'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
            },
            body: { prompt, identity, token }
        });
        return result;
    } catch (error) {
        console.error("apiChatMessage error:", error);
        return false;
    }
};

// streaming chat with assistant
export const apiChatMessageStream = async (params, onChunk) => {
    try {
        const { prompt, session_id, identity } = params;
        const session = await fetchAuthSession();
        const token = session.tokens?.accessToken?.toString();
        
        if (!token) throw new Error('No authentication token available');

        const baseUrl = getApiEndpoint("agentcore-runtime");
        const response = await fetch(baseUrl, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
                'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
            },
            body: JSON.stringify({ prompt, identity, stream: true, token })
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const chunk = JSON.parse(line.slice(6));
                        onChunk(chunk);
                    } catch (e) {
                        // Non-JSON data, pass as text
                        onChunk({ type: 'text', content: line.slice(6) });
                    }
                }
            }
        }
        return true;
    } catch (error) {
        console.error("apiChatMessageStream error:", error);
        return false;
    }
};

