export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });

  try {
    // Si tienes desplegado Python en Render/Railway colocas la URL en PYTHON_ENGINE_URL,
    // de lo contrario apunta a tu servidor local.
    const PYTHON_ENGINE_URL = process.env.PYTHON_ENGINE_URL || 'http://127.0.0.1:8000';

    const response = await fetch(`${PYTHON_ENGINE_URL}/api/analizar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body)
    });

    const data = await response.json();
    if (!response.ok) {
      return res.status(response.status).json({ error: data.detail || 'Error en motor Python' });
    }

    return res.status(200).json(data);

  } catch (err) {
    return res.status(500).json({ error: 'Error de conexión con el motor Python: ' + err.message });
  }
}
