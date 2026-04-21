export const AmplifyConfig = {
    aws_project_region: (import.meta.env.VITE_AWS_REGION) ? import.meta.env.VITE_AWS_REGION : 'us-east-1',
    aws_cognito_region: (import.meta.env.VITE_AWS_REGION) ? import.meta.env.VITE_AWS_REGION : 'us-east-1',
    aws_cognito_identity_pool_id: (import.meta.env.VITE_IDENTITY_POOL) ? import.meta.env.VITE_IDENTITY_POOL : null,
    aws_user_pools_id: (import.meta.env.VITE_COGNITO_POOL) ? import.meta.env.VITE_COGNITO_POOL : null,
    aws_user_pools_web_client_id: (import.meta.env.VITE_COGNITO_CLIENT) ? import.meta.env.VITE_COGNITO_CLIENT : null,
    oauth: {
        domain: `${(import.meta.env.VITE_COGNITO_DOMAIN) ? import.meta.env.VITE_COGNITO_DOMAIN : ""}.auth.${(import.meta.env.VITE_AWS_REGION) ? import.meta.env.VITE_AWS_REGION : 'us-east-1'}.amazoncognito.com`,
        scope: ["email", "openid", "profile"],
        redirectSignIn: `${window.location.protocol}//${window.location.host}/`,
        redirectSignOut: `${window.location.protocol}//${window.location.host}/`,
        responseType: "code",
    },
    API: {
        endpoints: [
            {
                name: "cloudfront-api",
                endpoint: (import.meta.env.VITE_API_ENDPOINT) ? `${import.meta.env.VITE_API_ENDPOINT}/api` : "/api",
            },
            {
                name: "agentcore-runtime",
                endpoint: (import.meta.env.VITE_AGENTCORE_URL) ? `${import.meta.env.VITE_AGENTCORE_URL}` : "/agentcore",
            }
        ]
    }
};