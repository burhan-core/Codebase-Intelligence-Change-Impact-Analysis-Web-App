const API_BASE_URL = 'http://localhost:8000';

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
    }
};
