const API_BASE_URL = 'http://127.0.0.1:8000';

export const api = {
    ingest: async (url) => {
        const response = await fetch(`${API_BASE_URL}/api/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to ingest repository');
        }
        return response.json();
    },

    getFileContent: async (projectId, path) => {
        const response = await fetch(`${API_BASE_URL}/api/project/${projectId}/file?path=${encodeURIComponent(path)}`);
        if (!response.ok) {
            throw new Error('Failed to fetch file content');
        }
        return response.json();
    },

    parseProject: async (projectId) => {
        const response = await fetch(`${API_BASE_URL}/api/project/${projectId}/parse`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to parse project');
        return response.json();
    },

    getMetadata: async (projectId, path) => {
        const response = await fetch(`${API_BASE_URL}/api/project/${projectId}/metadata?path=${encodeURIComponent(path)}`);
        if (!response.ok) return null; // Graceful fallback
        return response.json();
    },

    getDependencies: async (projectId, nodeId) => {
        const url = nodeId
            ? `${API_BASE_URL}/api/project/${projectId}/dependencies?node_id=${encodeURIComponent(nodeId)}`
            : `${API_BASE_URL}/api/project/${projectId}/dependencies`;

        const response = await fetch(url);
        if (!response.ok) {
            console.warn("Failed to fetch dependencies");
            return null;
        }
        return response.json();
    }
};
