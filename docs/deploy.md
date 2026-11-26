# Despliegue 24/7 en una VM gratis (Oracle Always Free)

Con esto el bot y los recordatorios funcionan aunque apagues tu PC, y el webhook queda en una URL HTTPS fija (sin ngrok).

```
Internet ──► Caddy :443 (HTTPS automático, Let's Encrypt) ──► asistente :8000 (FastAPI + SQLite en ./data)
```

## 1. Crear la VM (≈15 min)
1. Crea la cuenta en <https://www.oracle.com/cloud/free/>. Pide tarjeta para verificar identidad, pero no cobra.
2. **Recomendado:** pasa la cuenta a **Pay-As-You-Go**. Sigue costando $0 mientras no salgas de los recursos *Always Free*, y evita que Oracle reclame tu VM por "inactiva" (un bot usa muy poca CPU). Pon una **alerta de presupuesto de $1** en *Billing → Budgets* para que te avise ante cualquier cobro.
3. *Compute → Instances → Create instance*:
   - Imagen: **Ubuntu 24.04**
   - Shape: **VM.Standard.A1.Flex** (ARM, Always Free) con 1 OCPU y 6 GB. Sobra para el bot.
   - Si sale *"Out of capacity"*, prueba con otro *Availability Domain* o reintenta más tarde.
   - Descarga la llave SSH privada.
4. Red: en la VCN de la instancia, *Security List → Add Ingress Rules*: `0.0.0.0/0`, TCP, puertos **80** y **443**.

> Plan B sin Oracle: Google Cloud `e2-micro` (Always Free en us-west1, us-central1 o us-east1). Los pasos 2 en adelante son iguales.

## 2. Preparar la VM
```bash
ssh -i llave.key ubuntu@<IP-PUBLICA>
curl -fsSL https://raw.githubusercontent.com/Joseberseker/whatsapp-asistente-ia/main/deploy/setup-vm.sh -o setup-vm.sh
bash setup-vm.sh
```
El script instala Docker, abre 80 y 443 en el firewall del sistema (las imágenes de Oracle lo traen cerrado aunque la VCN lo permita), clona el repo y crea el `.env`.

## 3. Configurar y levantar
1. Completa `~/whatsapp-asistente-ia/.env` con los mismos valores que en tu PC, más:
   ```
   DOMAIN=<IP-con-guiones>.sslip.io      # ej. 129-146-10-20.sslip.io → no hace falta comprar dominio
   DASHBOARD_PASSWORD=<una clave fuerte>  # el dashboard queda público en internet
   ```
   El `.env` debe tener solo líneas `CLAVE=valor` o comentarios: Docker es más estricto que Python y falla con líneas sueltas.
2. Sal y vuelve a entrar por SSH (para usar docker sin sudo) y levanta:
   ```bash
   cd ~/whatsapp-asistente-ia
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
3. Verifica: `https://<DOMAIN>/dashboard` pide usuario y clave.

## 4. Apuntar Meta al servidor
En *WhatsApp → Configuración → Webhook*, cambia la URL a `https://<DOMAIN>/webhook` (mismo verify token) → **Verificar y guardar**. Desde ese momento los mensajes van al servidor y no a tu PC.

## Operación diaria
| Qué | Comando (en `~/whatsapp-asistente-ia`) |
|---|---|
| Ver logs en vivo | `docker compose logs -f asistente` |
| Actualizar a lo último de `main` | `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` |
| Reiniciar | `docker compose restart asistente` |
| Respaldar la base | `cp data/asistente.db ~/respaldo-$(date +%F).db` |

Para volver a desarrollar en tu PC con ngrok, cambia de nuevo la URL del webhook en Meta. Solo un destino recibe los mensajes a la vez.
