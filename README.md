# Xclock 🕒
**Dashboard multi-vista para Xiaomi Mi Smart Clock (800x480) alojado en Raspberry Pi**

Proyecto diseñado para mostrar en un **Xiaomi Mi Smart Clock** una interfaz de alto contraste y bajo consumo con 3 vistas intercambiables:

### 🎨 Vistas disponibles:
1. **📱 Dashboard Completo (Por defecto):**
   * Fecha grande en formato estricto `DD/MM/YYYY`.
   * Hora digital gigante con segundos en tiempo real.
   * Indicador `AM` / `PM` automático cuando se selecciona formato de 12 horas.
   * Sensores de temperatura: Salón (Google Nest) y Exterior por Ciudad (Open-Meteo).
2. **⏱️ Retro Flip Clock (Fichas mecánicas partidas a pantalla completa):**
   * Reloj vintage estilo *Solari / Copal* ocupando toda la pantalla de 800×480 px.
   * Animación 3D de caída de ficha cada vez que cambia el minuto o la hora.
   * Indicador vintage de `AM` / `PM` en formato de 12 horas.
3. **📟 Digital Full Screen (Reloj digital a pantalla completa):**
   * Dígitos gigantes de alto impacto que llenan los 800×480 píxeles con segundero.
   * **Color de dígitos personalizable:**
     * 🟢 **Verde** (Estilo fósforo / Matrix LED con resplandor)
     * 🔵 **Azul** (Cian cibernético brillante)
     * 🔴 **Rojo** (Rojo alarma digital clásico de mesita de noche)
     * 🎲 **Aleatorio** (Color dinámico aleatorio)

---

## ⚙️ Panel de Ajustes (Settings)

Puedes configurar tu reloj de dos formas:
1. **En la pantalla del reloj:** Tocando el icono **⚙️** en cualquier vista.
2. **Desde el navegador de tu móvil o PC:** Entrando en `http://<IP_DE_LA_RASPBERRY_PI>:5000/settings`.

**Opciones disponibles:**
* **🎨 Vista:** *Dashboard*, *Retro Flip* o *Digital Full*.
* **🌈 Color Digital:** Verde, Azul, Rojo o Aleatorio.
* **⏰ Formato de Hora:** 24 Horas (`19:08`) o 12 Horas con AM/PM (`07:08 PM`).
* **📍 Ubicación (Ciudad):** Buscador inteligente mundial (Open-Meteo).
* **🌙 Modo Noche Automático:** Atenuación a tonos ámbar cálidos para descansar.

---

## 🚀 Puesta en marcha en la Raspberry Pi Model B+

1. **Copia la carpeta a la Raspberry Pi:**
   ```bash
   scp -r Xclock pi@<IP_DE_TU_PI>:~/
   ```
2. **Ejecuta el instalador automático:**
   ```bash
   ssh pi@<IP_DE_TU_PI>
   cd ~/Xclock
   chmod +x install.sh
   ./install.sh
   ```
El instalador creará el entorno virtual y configurará los servicios `xclock-server` y `xclock-cast` con **systemd** para que arranque y proyecte solo al encender la placa.
