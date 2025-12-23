// import { useState } from "react";
// import { adminAPI } from '../services/api';

// export default function PromptModal({ data, onClose, onSaved }) {
//   const [intentKey, setIntentKey] = useState(data?.intent_key || "");
//   const [promptText, setPromptText] = useState(data?.prompt_text || "");
//   const [loading, setLoading] = useState(false);

//   const save = async () => {
//     if (!intentKey || !promptText) return alert("All fields required");
//     setLoading(true);

//     const payload = {
//       intent_key: intentKey.toLowerCase().replace(/[^a-z0-9_]/g, "_"),
//       prompt_text: promptText
//     };

//     if (data) {
//       await adminAPI.updatePrompt(data.id, payload);
//     } else {
//       await adminAPI.createPrompt(payload);
//     }

//     setLoading(false);
//     onSaved();
//     onClose();
//   };

//   return (
//     <div className="fixed inset-0 flex justify-center items-center bg-black/50">
//       <div className="bg-white p-6 rounded-xl w-[600px] space-y-4">
//         <h2 className="text-xl font-semibold">
//           {data ? "Edit Prompt" : "Create Prompt"}
//         </h2>
//         <input
//           className="w-full p-2 border rounded"
//           placeholder="intent_key"
//           value={intentKey}
//           onChange={(e) => setIntentKey(e.target.value)}
//         />
//         <textarea
//           className="w-full p-2 border rounded h-40"
//           placeholder="Prompt text"
//           value={promptText}
//           onChange={(e) => setPromptText(e.target.value)}
//         />
//         <div className="flex justify-end gap-2">
//           <button className="px-4 py-2" onClick={onClose}>
//             Cancel
//           </button>
//           <button
//             disabled={loading}
//             onClick={save}
//             className="bg-primary-600 text-white px-4 py-2 rounded hover:bg-primary-700"
//           >
//             {loading ? "Saving..." : "Save"}
//           </button>
//         </div>
//       </div>
//     </div>
//   );
// }
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI } from '../services/api';

export default function PromptModal({ data, onClose, onSaved, onLogout }) {
  const [intentKey, setIntentKey] = useState(data?.intent_key || '');
  const [promptText, setPromptText] = useState(data?.prompt_text || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const navigate = useNavigate();

  const save = async () => {
    if (!intentKey.trim() || !promptText.trim()) {
      setError('All fields are required');
      return;
    }

    setLoading(true);
    setError('');

    const payload = {
      intent_key: intentKey
        .toLowerCase()
        .replace(/[^a-z0-9_]/g, '_'),
      prompt_text: promptText.trim(),
    };

    try {
      if (data) {
        await adminAPI.updatePrompt(data.id, payload);
      } else {
        await adminAPI.createPrompt(payload);
      }

      onSaved();
      onClose();
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        // 🔐 Session expired → force logout
        onLogout?.();
        navigate('/', { replace: true });
      } else if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError('Failed to save prompt. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 flex justify-center items-center bg-black/50 z-50">
      <div className="bg-white p-6 rounded-xl w-[600px] space-y-4">

        <h2 className="text-xl font-semibold">
          {data ? 'Edit Prompt' : 'Create Prompt'}
        </h2>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
            {error}
          </div>
        )}

        <input
          className="w-full p-2 border rounded"
          placeholder="intent_key"
          value={intentKey}
          onChange={(e) => setIntentKey(e.target.value)}
          disabled={loading}
        />

        <textarea
          className="w-full p-2 border rounded h-40"
          placeholder="Prompt text"
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          disabled={loading}
        />

        <div className="flex justify-end gap-2">
          <button
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>

          <button
            disabled={loading}
            onClick={save}
            className="bg-primary-600 text-white px-4 py-2 rounded hover:bg-primary-700 disabled:opacity-60"
          >
            {loading ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
