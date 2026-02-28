/**
 * Hocuspocus – Real-time collaboration server for the Accountant office suite.
 *
 * Handles Yjs document sync between multiple browser clients.
 * Auth: validates JWT tokens via the FastAPI backend.
 * Storage: loads/saves Yjs document state via the FastAPI backend.
 */

import { Hocuspocus } from "@hocuspocus/server";
import { Database } from "@hocuspocus/extension-database";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const PORT = parseInt(process.env.HOCUSPOCUS_PORT || "1234", 10);

/**
 * Fetch helper that throws on non-OK responses.
 */
async function apiFetch(path, options = {}) {
  const url = `${BACKEND_URL}${path}`;
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${options.method || "GET"} ${path} → ${res.status}: ${text}`);
  }
  return res;
}

const server = new Hocuspocus({
  port: PORT,
  name: "accountant-collab",

  /**
   * Authentication hook – validate the JWT token from the connecting client.
   * The client passes the token via the WebSocket connection params.
   */
  async onAuthenticate({ token }) {
    if (!token) {
      throw new Error("No authentication token provided");
    }

    // Validate the token against the backend /api/auth/me endpoint
    const res = await apiFetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    });

    const body = await res.json();
    const user = body.data || body;

    return {
      user: {
        id: user.id,
        name: user.full_name || user.email,
        email: user.email,
      },
    };
  },

  extensions: [
    new Database({
      /**
       * Load Yjs state from the backend when a document is first opened.
       * The document name is the office document UUID.
       */
      async fetch({ documentName }) {
        try {
          const res = await apiFetch(`/api/office/${documentName}/state`);
          const buffer = await res.arrayBuffer();
          if (buffer.byteLength === 0) return null;
          return new Uint8Array(buffer);
        } catch {
          // Document doesn't exist yet or backend unavailable
          return null;
        }
      },

      /**
       * Save Yjs state back to the backend whenever the document changes.
       * Debounced by Hocuspocus (default: 2 seconds after last change).
       */
      async store({ documentName, state }) {
        await apiFetch(`/api/office/${documentName}/state`, {
          method: "PUT",
          headers: { "Content-Type": "application/octet-stream" },
          body: state,
        });
      },
    }),
  ],
});

server.listen().then(() => {
  console.log(`Hocuspocus collaboration server running on port ${PORT}`);
});
