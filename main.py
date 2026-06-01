from machine import Pin, ADC, I2C, PWM
from dht import DHT22
from ssd1306 import SSD1306_I2C
from time import sleep, ticks_ms, ticks_diff
import network
from umqtt.simple import MQTTClient
import ubinascii
import machine

# ==========================================
# QUARTO INTELIGENTE IOT - ESP32 + HIVEMQ
# ==========================================

# Wi-Fi Wokwi
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

# HiveMQ Cloud
MQTT_BROKER = "51817863dc174a74b09c7b04b65dec4f.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "bruno_silva"
MQTT_PASSWORD = "Silv@1215"

CLIENT_ID = b"quarto-inteligente-" + ubinascii.hexlify(machine.unique_id())

# Intervalo de envio dos sensores
INTERVALO_PUBLICACAO = 5000

# Topico unico em JSON
TOP_DADOS = b"quarto/sensores/dados"

# Topicos sensores separados
TOP_TEMP = b"quarto/sensores/temperatura"
TOP_UMID = b"quarto/sensores/umidade"
TOP_LUZ = b"quarto/sensores/luminosidade"
TOP_GAS = b"quarto/sensores/gas"
TOP_MOV = b"quarto/sensores/movimento"
TOP_ALERTA = b"quarto/alertas"

# Topicos comandos dos atuadores
TOP_CMD_LUZ = b"quarto/atuadores/luz"
TOP_CMD_TOMADA = b"quarto/atuadores/tomada"
TOP_CMD_VENT = b"quarto/atuadores/ventilador"
TOP_CMD_ALARME = b"quarto/atuadores/alarme"

# Topicos status dos atuadores
TOP_STATUS_LUZ = b"quarto/status/luz"
TOP_STATUS_TOMADA = b"quarto/status/tomada"
TOP_STATUS_VENT = b"quarto/status/ventilador"
TOP_STATUS_ALARME = b"quarto/status/alarme"

# ==========================================
# SENSORES
# ==========================================

dht = DHT22(Pin(15))

ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)

mq2 = ADC(Pin(35))
mq2.atten(ADC.ATTN_11DB)

pir = Pin(27, Pin.IN)

# ==========================================
# ATUADORES
# ==========================================

rele_luz = Pin(2, Pin.OUT)
rele_tomada = Pin(4, Pin.OUT)
buzzer = Pin(5, Pin.OUT)
servo = PWM(Pin(18), freq=50)

# ==========================================
# OLED
# ==========================================

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
oled = SSD1306_I2C(128, 64, i2c)

# ==========================================
# ESTADOS
# ==========================================

estado_luz = "OFF"
estado_tomada = "OFF"
estado_ventilador = "OFF"
estado_alarme = "OFF"

mqtt = None
ultimo_envio = 0

# ==========================================
# FUNCOES AUXILIARES
# ==========================================

def tela(linha1, linha2="", linha3="", linha4="", linha5=""):
    oled.fill(0)
    oled.text(str(linha1)[:16], 0, 0)
    oled.text(str(linha2)[:16], 0, 12)
    oled.text(str(linha3)[:16], 0, 24)
    oled.text(str(linha4)[:16], 0, 36)
    oled.text(str(linha5)[:16], 0, 48)
    oled.show()

def mover_servo(angulo):
    duty = int((angulo / 180) * 75 + 40)
    servo.duty(duty)

def conectar_wifi():
    print("Conectando ao Wi-Fi...")
    tela("QUARTO SMART", "Conectando WiFi")

    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.connect(WIFI_SSID, WIFI_PASSWORD)

    tentativas = 0
    while not wifi.isconnected():
        sleep(0.5)
        tentativas += 1
        print(".", end="")

        if tentativas > 40:
            print("\nFalha no Wi-Fi")
            tela("ERRO WIFI", "Verifique Wokwi")
            return False

    ip = wifi.ifconfig()[0]
    print("\nWi-Fi conectado:", ip)
    tela("WiFi OK", ip)
    sleep(1)

    return True

def aplicar_luz(valor):
    global estado_luz

    if valor == "ON":
        rele_luz.value(1)
        estado_luz = "ON"
    elif valor == "OFF":
        rele_luz.value(0)
        estado_luz = "OFF"

def aplicar_tomada(valor):
    global estado_tomada

    if valor == "ON":
        rele_tomada.value(1)
        estado_tomada = "ON"
    elif valor == "OFF":
        rele_tomada.value(0)
        estado_tomada = "OFF"

def aplicar_ventilador(valor):
    global estado_ventilador

    if valor == "ON":
        mover_servo(180)
        estado_ventilador = "ON"
    elif valor == "OFF":
        mover_servo(90)
        estado_ventilador = "OFF"

def aplicar_alarme(valor):
    global estado_alarme

    if valor == "ON":
        buzzer.value(1)
        estado_alarme = "ON"
    elif valor == "OFF":
        buzzer.value(0)
        estado_alarme = "OFF"

def publicar(topic, payload):
    global mqtt

    if mqtt is None:
        return False

    try:
        mqtt.publish(topic, str(payload))
        return True
    except Exception as erro:
        print("Falha MQTT publish:", erro)
        mqtt = None
        return False

def publicar_status():
    publicar(TOP_STATUS_LUZ, estado_luz)
    publicar(TOP_STATUS_TOMADA, estado_tomada)
    publicar(TOP_STATUS_VENT, estado_ventilador)
    publicar(TOP_STATUS_ALARME, estado_alarme)

def callback_mqtt(topic, msg):
    comando = msg.decode().strip().upper()
    print("Comando MQTT:", topic, comando)

    if topic == TOP_CMD_LUZ:
        aplicar_luz(comando)
    elif topic == TOP_CMD_TOMADA:
        aplicar_tomada(comando)
    elif topic == TOP_CMD_VENT:
        aplicar_ventilador(comando)
    elif topic == TOP_CMD_ALARME:
        aplicar_alarme(comando)

    publicar_status()

def conectar_mqtt():
    global mqtt

    print("Conectando MQTT HiveMQ Cloud...")
    tela("Conectando MQTT", "HiveMQ Cloud")

    try:
        client = MQTTClient(
            CLIENT_ID,
            MQTT_BROKER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            ssl=True,
            ssl_params={"server_hostname": MQTT_BROKER}
        )

        client.set_callback(callback_mqtt)
        client.connect()

        client.subscribe(TOP_CMD_LUZ)
        client.subscribe(TOP_CMD_TOMADA)
        client.subscribe(TOP_CMD_VENT)
        client.subscribe(TOP_CMD_ALARME)

        mqtt = client

        print("MQTT conectado ao HiveMQ Cloud")
        print("Topicos dos atuadores inscritos")

        tela("MQTT OK", "HiveMQ Cloud")
        sleep(1)

        publicar_status()
        return True

    except Exception as erro:
        print("Erro MQTT:", erro)
        tela("ERRO MQTT", str(erro))
        mqtt = None
        sleep(2)
        return False

def ler_sensores():
    try:
        dht.measure()
        temperatura = dht.temperature()
        umidade = dht.humidity()
    except:
        temperatura = 0
        umidade = 0

    luminosidade = ldr.read()
    gas = mq2.read()
    movimento = pir.value()

    return temperatura, umidade, luminosidade, gas, movimento

def definir_alerta(temperatura, luminosidade, gas, movimento):
    if gas > 3000:
        return "GAS DETECT"
    elif temperatura > 35:
        return "TEMP ALTA"
    elif movimento == 1:
        return "MOVIMENTO"
    elif luminosidade < 500:
        return "AMBIENTE ESCURO"
    else:
        return "NORMAL"

def mostrar_dados(temp, umid, luz, gas, mov, alerta):
    oled.fill(0)
    oled.text("QUARTO SMART", 0, 0)
    oled.text("T:{:.1f}C U:{:.1f}%".format(temp, umid), 0, 12)
    oled.text("Luz:{} G:{}".format(luz, gas), 0, 24)
    oled.text("Mov:{} {}".format(mov, alerta[:8]), 0, 36)
    oled.text("L:{} T:{} V:{} A:{}".format(
        estado_luz[0],
        estado_tomada[0],
        estado_ventilador[0],
        estado_alarme[0]
    ), 0, 48)
    oled.show()

def publicar_sensores(temp, umid, luz, gas, mov, alerta):
    temp = round(temp, 1)
    umid = round(umid, 1)

    dados = '{{"temperatura":{},"umidade":{},"luminosidade":{},"gas":{},"movimento":{},"alerta":"{}"}}'.format(
        temp, umid, luz, gas, mov, alerta
    )

    publicar(TOP_DADOS, dados)

    publicar(TOP_TEMP, temp)
    publicar(TOP_UMID, umid)
    publicar(TOP_LUZ, luz)
    publicar(TOP_GAS, gas)
    publicar(TOP_MOV, mov)
    publicar(TOP_ALERTA, alerta)
    publicar_status()

def imprimir_resumo(temp, umid, luz, gas, mov, alerta):
    temp = round(temp, 1)
    umid = round(umid, 1)

    print("--------------------------------")
    print("Temp: {:.1f} C | Umid: {:.1f} %".format(temp, umid))
    print("Luz:", luz, "| Gas:", gas, "| Mov:", mov)
    print("Alerta:", alerta)
    print("Estados -> Luz:", estado_luz,
          "| Tomada:", estado_tomada,
          "| Vent:", estado_ventilador,
          "| Alarme:", estado_alarme)

# ==========================================
# INICIALIZACAO
# ==========================================

tela("QUARTO SMART", "Iniciando...")
sleep(1)

aplicar_luz("OFF")
aplicar_tomada("OFF")
aplicar_ventilador("OFF")
aplicar_alarme("OFF")

wifi_ok = conectar_wifi()

if wifi_ok:
    conectar_mqtt()
else:
    tela("SEM WIFI", "Modo local")

# ==========================================
# LOOP PRINCIPAL
# ==========================================

while True:
    try:
        if mqtt is not None:
            try:
                mqtt.check_msg()
            except Exception as erro:
                print("MQTT desconectado:", erro)
                mqtt = None

        if mqtt is None and wifi_ok:
            conectar_mqtt()

        temp, umid, luz, gas, mov = ler_sensores()
        alerta = definir_alerta(temp, luz, gas, mov)

        mostrar_dados(temp, umid, luz, gas, mov, alerta)

        agora = ticks_ms()

        if ticks_diff(agora, ultimo_envio) >= INTERVALO_PUBLICACAO:
            ultimo_envio = agora
            imprimir_resumo(temp, umid, luz, gas, mov, alerta)

            if mqtt is not None:
                publicar_sensores(temp, umid, luz, gas, mov, alerta)

        sleep(0.2)

    except Exception as erro:
        print("Erro geral:", erro)
        tela("ERRO GERAL", str(erro))
        sleep(2)