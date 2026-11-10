"""
Xclock - Gestor de Casting y Guardián (Watchdog) para Xiaomi Mi Smart Clock
Usa `catt` (Cast All The Things) para proyectar la web y mantener la sesión viva 24/7.
"""

import time
import socket
import subprocess
import config

def get_local_ip():
    """Obtiene la dirección IP local de la Raspberry Pi en la red."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No realiza conexión real a internet, solo determina la interfaz de salida hacia el router
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def cast_url(target, url):
    """Lanza la URL al reloj Xiaomi usando catt."""
    print(f"[Cast] Proyectando {url} en '{target}'...")
    try:
        cmd = ["catt", "-d", str(target), "cast_site", url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if result.returncode == 0:
            print("[Cast] Proyección iniciada con éxito.")
            return True
        else:
            print(f"[Cast Error]: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"[Cast Exception]: {e}")
        return False

def check_clock_status(target):
    """
    Comprueba si el reloj está mostrando contenido activo.
    Devuelve True si está reproduciendo, False si está en reposo o falló.
    """
    try:
        cmd = ["catt", "-d", str(target), "status"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        output = result.stdout.lower()
        
        # Si la salida indica que no hay nada reproduciéndose o está libre
        if "nothing is playing" in output or "idle" in output or "playback state: none" in output:
            return False
        if "casting:" in output or "playing" in output or "buffering" in output:
            return True
        return False
    except Exception as e:
        print(f"[Watchdog Status Exception]: {e}")
        return False

def main():
    target = config.CLOCK_NAME_OR_IP
    local_ip = get_local_ip()
    target_url = f"http://{local_ip}:{config.SERVER_PORT}"

    print("==================================================")
    print("   Xclock - Iniciando Guardián de Transmisión    ")
    print(f"   Destino: {target}")
    print(f"   URL a castear: {target_url}")
    print("==================================================")

    # Espera inicial para asegurarse de que el servidor Flask esté levantado
    time.sleep(5)

    # Primer lanzamiento
    cast_url(target, target_url)

    # Bucle guardián (Watchdog): comprueba cada 45 segundos si la sesión sigue activa
    while True:
        try:
            time.sleep(45)
            is_active = check_clock_status(target)
            
            if not is_active:
                print("[Watchdog] La pantalla del reloj parece inactiva o cerrada. Relanzando...")
                cast_url(target, target_url)
                # Pequeña pausa adicional tras relanzar
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n[Watchdog] Deteniendo gestor de transmisión.")
            break
        except Exception as e:
            print(f"[Watchdog Loop Error]: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
