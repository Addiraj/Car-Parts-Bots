// import { useState } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { adminAPI } from '../services/api';

// export default function PromptModal({ data, onClose, onSaved, onLogout }) {
//   const [intentKey, setIntentKey] = useState(data?.intent_key || '');
//   const [displayName, setDisplayName] = useState(data?.display_name || '');
//   const [promptText, setPromptText] = useState(data?.prompt_text || '');
//   const [loading, setLoading] = useState(false);
//   const [error, setError] = useState('');

//   const navigate = useNavigate();

//   const save = async () => {
//     if (!intentKey.trim() || !displayName.trim() || !promptText.trim()) {
//       setError('All fields are required');
//       return;
//     }

//     setLoading(true);
//     setError('');

//     const payload = {
//       // 🔒 machine-safe identifier
//       intent_key: intentKey
//         .toLowerCase()
//         .replace(/[^a-z0-9_]/g, '_'),

//       // 🧑 human-friendly label
//       display_name: displayName.trim(),

//       prompt_text: promptText.trim(),
//     };

//     try {
//       if (data) {
//         await adminAPI.updatePrompt(data.id, payload);
//       } else {
//         await adminAPI.createPrompt(payload);
//       }

//       onSaved();
//       onClose();
//     } catch (err) {
//       if (err.response?.status === 401 || err.response?.status === 403) {
//         onLogout?.();
//         navigate('/', { replace: true });
//       } else {
//         setError(err.response?.data?.error || 'Failed to save prompt');
//       }
//     } finally {
//       setLoading(false);
//     }
//   };

//   return (
//     <div className="fixed inset-0 flex justify-center items-center bg-black/50 z-50">
//       <div className="bg-white p-6 rounded-xl w-[600px] space-y-4">

//         <h2 className="text-xl font-semibold">
//           {data ? 'Edit Prompt' : 'Create Prompt'}
//         </h2>

//         {error && (
//           <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
//             {error}
//           </div>
//         )}

//         <input
//           className="w-full p-2 border rounded"
//           placeholder="Intent Key (snake_case)"
//           value={intentKey}
//           onChange={(e) => setIntentKey(e.target.value)}
//           disabled={loading}
//         />

//         <input
//           className="w-full p-2 border rounded"
//           placeholder="Display Name (shown to humans)"
//           value={displayName}
//           onChange={(e) => setDisplayName(e.target.value)}
//           disabled={loading}
//         />

//         <textarea
//           className="w-full p-2 border rounded h-40"
//           placeholder="Prompt text"
//           value={promptText}
//           onChange={(e) => setPromptText(e.target.value)}
//           disabled={loading}
//         />

//         <div className="flex justify-end gap-2">
//           <button onClick={onClose} disabled={loading}>
//             Cancel
//           </button>
//           <button
//             disabled={loading}
//             onClick={save}
//             className="bg-primary-600 text-white px-4 py-2 rounded"
//           >
//             {loading ? 'Saving…' : 'Save'}
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
  const [displayName, setDisplayName] = useState(data?.display_name || '');
  const [promptText, setPromptText] = useState(data?.prompt_text || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const navigate = useNavigate();

  const save = async () => {
    if (!displayName.trim() || !promptText.trim()) {
      setError('All fields are required');
      return;
    }

    setLoading(true);
    setError('');

    const payload = {
      display_name: displayName.trim(),
      prompt_text: promptText.trim(),
    };

    // ONLY include intent_key on CREATE
    if (!data) {
      if (!intentKey.trim()) {
        setError('Intent key is required');
        setLoading(false);
        return;
      }

      payload.intent_key = intentKey
        .toLowerCase()
        .replace(/[^a-z0-9_]/g, '_');
    }

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
        onLogout?.();
        navigate('/', { replace: true });
      } else {
        setError(err.response?.data?.error || 'Failed to save prompt');
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
          className={`w-full p-2 border rounded ${
            data
              ? 'bg-gray-100 cursor-not-allowed'
              : 'bg-white'
          }`}
          placeholder="Intent Key"
          value={intentKey}
          onChange={(e) => setIntentKey(e.target.value)}
          disabled={!!data}
        />

        <input
          className="w-full p-2 border rounded"
          placeholder="Display Name (shown to humans)"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
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
          <button onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button
            disabled={loading}
            onClick={save}
            className="bg-primary-600 text-white px-4 py-2 rounded"
          >
            {loading ? 'Saving…' : 'Save'}
          </button>
        </div>

      </div>
    </div>
  );
}
