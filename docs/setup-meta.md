# Configuración en Meta (número de prueba, costo $0)

Tiempo estimado: unos 20 minutos. Al final tendrás todas las variables de `.env`.

## 1. App y número de prueba
1. Entra a <https://developers.facebook.com/apps> → **Crear app** → caso de uso **"Conectar con clientes por WhatsApp"** y asóciala a un portfolio de negocio (se crea uno si no tienes).
2. En **WhatsApp → Configuración de la API** verás el **número de prueba** y su **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`.
3. En **"Para"**, agrega y verifica (por código) los números que van a probar el bot. **Máximo 5**: es la limitación del número de prueba.

## 2. Token permanente (el temporal vence en 24 h)
1. <https://business.facebook.com/settings> → **Usuarios del sistema** → **Agregar** (rol Admin).
2. **Asignar activos** → tu app, con control total.
3. **Generar token** → la app, vencimiento **Nunca**, permisos `whatsapp_business_messaging` y `whatsapp_business_management` → `WHATSAPP_TOKEN`.

## 3. App Secret
**Configuración de la app → Básica → Clave secreta de la app** → `WHATSAPP_APP_SECRET`. Sirve para validar que cada webhook viene de Meta.

## 4. Túnel HTTPS gratis (ngrok con dominio estático)
1. Crea una cuenta en <https://ngrok.com>, instala el agente y ejecuta `ngrok config add-authtoken <token>`.
2. En **Domains**, reclama tu dominio estático gratis (por ejemplo, `algo-algo.ngrok-free.app`).
3. Con la app corriendo: `ngrok http --url=<tu-dominio> 8000`.

## 5. Webhook
1. Inventa un string cualquiera → `WHATSAPP_VERIFY_TOKEN`.
2. **WhatsApp → Configuración → Webhook**: URL `https://<tu-dominio>/webhook` y el mismo verify token → **Verificar y guardar** (la app tiene que estar corriendo).
3. En **Campos del webhook**, suscríbete a `messages`.

## 6. Plantilla para recordatorios (fuera de la ventana de 24 h)
WhatsApp solo deja enviar texto libre durante las 24 h siguientes al último mensaje del usuario. Pasado ese plazo, el recordatorio sale como plantilla.
1. **WhatsApp Manager → Plantillas de mensajes → Crear** → categoría **Utilidad**, nombre `recordatorio`, idioma **Español** (`es`).
2. Cuerpo: `⏰ Te recuerdo: {{1}}` (con un ejemplo para la variable).
3. Espera a que quede aprobada (suelen ser minutos). Si no está aprobada, el envío queda como `failed` en el dashboard.

## 7. Gemini (gratis)
<https://aistudio.google.com/apikey> → **Create API key** → `GEMINI_API_KEY`.

## 8. Prueba
Desde uno de los números verificados, escríbele al número de prueba: "hola" y después "recuérdame tomar agua en 2 minutos". Puedes seguir todo en `https://<tu-dominio>/dashboard`.
