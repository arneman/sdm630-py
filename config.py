PARITY_NONE, PARITY_EVEN, PARITY_ODD, PARITY_MARK, PARITY_SPACE = (
    "N",
    "E",
    "O",
    "M",
    "S",
)

CONFIG = {
    "dev": "/dev/usb-carport-pv-sdm630",
    "modbus": {
        "address": 1,
        "func_code": 4,
        "reg_num": 2,
        "baudrate": 9600,
        "bytesize": 8,
        "parity": PARITY_NONE,
        "stopbits": 1,
        "timeout": 0.6,
    },
    "registers": [],
    "loglevel": "DEBUG",  # "ERROR",
    "utc": True,
    "mqtt": {
        "enabled": True,
        "host": "localhost",
        "port": 1883,
        "keepalive": 60,
        "auth": {"enabled": False, "username": "mqtt_user", "password": "pwd"},
        "topic": "devices/pv-carport/reading",
        "retain": False,
        "qos": 0,
    },
    "logfile": {"enabled": False},
    "sqlite": {
        "enabled": False,
        "fname": "/mnt/usb-stick/meterdata/powermeter_%Y-%m.sqlite3",
        "min_rows_insert": 5,
    },
}
