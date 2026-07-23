export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });

  try {
    // Obtenemos la URL base de Render sin diagonales al final
    let baseUrl = (process.env.PYTHON_ENGINE_URL || 'http://127.0.0.1:8000').trim();
    if (baseUrl.endsWith('/')) {
      baseUrl = baseUrl.slice(0, -1);
    }

    // La ruta en main.py es /api/analizar
    const targetUrl = `${baseUrl}/api/analizar`;

    const response = await fetch(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body)
    });

    const text = await response.text();
    
    // Si Render devuelve un HTML de error o 404, mostramos el mensaje claro
    if (!response.ok) {
      return res.status(response.status).json({ error: `Error del motor Python (${response.status}): ${text}` });
    }

    const data = JSON.parse(text);
    return res.status(200).json(data);

  } catch (err) {
    return res.status(500).json({ error: 'Error de conexión con el motor Python: ' + err.message });
  }
}
