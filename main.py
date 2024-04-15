import sys
import re
import logging
import time
import multiprocessing
import json
import datetime
import os
import minimalmodbus


from config import CONFIG

REGISTERS = {
    "L1_Voltage": 0,
    "L2_Voltage": 2,
    "L3_Voltage": 4,
    # "L1_Current": 6,
    # "L2_Current": 8,
    # "L3_Current": 10,
    # "L1_L2_Voltage": 200,
    # "L2_L3_Voltage": 202,
    # "L3_L1_Voltage": 204,
    "L1_Active_Power": 12,
    "L2_Active_Power": 14,
    "L3_Active_Power": 16,
    # "L1_Apparent_Power": 18,
    # "L2_Apparent_Power": 20,
    # "L3_Apparent_Power": 22,
    # "L1_Reactive_Power": 24,
    # "L2_Reactive_Power": 26,
    # "L3_Reactive_Power": 28,
    # "L1_Power_Factor": 30,
    # "L2_Power_Factor": 32,
    # "L3_Power_Factor": 34,
    # "L1_Phase_Angle": 36,
    # "L2_Phase_Angle": 38,
    # "L3_Phase_Angle": 40,
    # "L1_Current_THD": 240,
    # "L2_Current_THD": 242,
    # "L3_Current_THD": 244,
    "Total_System_Power": 52,
    # "Total_System_VA": 56,
    # "Total_System_VAR": 60,
    # "Total_System_Power_Demand": 84,
    # "Total_System_Power_Demand_Max": 86,
    # "Total_System_VA_Demand": 100,
    "Frequency": 70,
    "Import_Active_Energy": 72,
    "Export_Active_Energy": 74,
    # "Import_Reactive_Energy": 76,
    # "Export_Reactive_Energy": 78,
    "Total_Active_Energy": 342,
    "Total_Reactive_Energy": 344,
}

TS_FORMAT = "%Y-%m-%d %H:%M:%S"

SQLITE_CREATE = """CREATE TABLE IF NOT EXISTS meter_data
                   ( meter TEXT
                    ,l1 NUMERIC
                    ,l2 NUMERIC
                    ,l3 NUMERIC
                    ,load NUMERIC
                    ,kwh NUMERIC
                    ,TS TEXT DEFAULT CURRENT_TIMESTAMP);"""


def extract(keyword, reading):
    pattern = KEYWORDS[keyword]["keyword"]
    match = re.search(r"%s.*?\((.*?)(?:\*(.*?))?\)" % pattern, reading)
    value, unit = match.groups()
    value = KEYWORDS[keyword]["dtype"](value)
    return value, unit


def setup_serial():
    # serial port setup
    rs485 = minimalmodbus.Instrument(CONFIG["dev"], CONFIG["modbus"]["address"])
    rs485.serial.baudrate = CONFIG["modbus"]["baudrate"]
    rs485.serial.bytesize = CONFIG["modbus"]["bytesize"]
    rs485.serial.parity = CONFIG["modbus"]["parity"]
    rs485.serial.stopbits = CONFIG["modbus"]["stopbits"]
    rs485.serial.timeout = CONFIG["modbus"]["timeout"]
    rs485.mode = minimalmodbus.MODE_RTU
    rs485.debug = False
    return rs485


def worker_read_meter(task_queues):
    task_queues = task_queues[
        :-1
    ]  # remove last entry because is a list with all other queues (=the argument for this worker)
    logger = multiprocessing.get_logger()
    rs845 = setup_serial()
    while True:
        try:
            reading = {}
            for reg_name, reg_no in REGISTERS.items():
                reading[reg_name] = rs845.read_float(
                    reg_no,
                    CONFIG["modbus"]["func_code"],
                    CONFIG["modbus"]["reg_num"],
                )
                logger.debug(f"reg: {reg_name}, reading: {reading[reg_name]}")
                time.sleep(CONFIG["modbus"]["delay_read_register"])

            # add timestamp
            if CONFIG["utc"] is True:
                ts = datetime.datetime.now(datetime.timezone.utc)
            else:
                ts = datetime.datetime.now()

            reading["ts"] = ts.strftime(TS_FORMAT)

            # publish
            for queue in task_queues:
                queue.put(reading)

            time.sleep(CONFIG["modbus"]["interval"])

        except:
            logger.exception("Error in worker_read_meter")


def worker_publish_mqtt(task_queue):
    import paho.mqtt.client as mqtt

    logger = multiprocessing.get_logger()
    client = mqtt.Client()

    def mqtt_connect():
        if CONFIG["mqtt"]["auth"]["enabled"]:
            client.username_pw_set(
                CONFIG["mqtt"]["auth"]["username"], CONFIG["mqtt"]["auth"]["password"]
            )

        client.connect(
            host=CONFIG["mqtt"]["host"],
            port=CONFIG["mqtt"]["port"],
            keepalive=CONFIG["mqtt"]["keepalive"],
            bind_address="",
        )

    def mqtt_publish(payload):
        mqtt_connect()
        return client.publish(
            topic=CONFIG["mqtt"]["topic"],
            payload=json.dumps(reading),
            qos=CONFIG["mqtt"]["qos"],
            retain=CONFIG["mqtt"]["retain"],
        )

    while True:
        try:
            if not task_queue.empty():
                reading = task_queue.get()
                mqtt_publish(reading)
                logger.debug("worker_publish_mqtt" + json.dumps(reading))
        except:
            logger.exception("Error in worker_publish_mqtt")
        time.sleep(0.1)


def worker_sqlite(task_queue):
    import sqlite3

    logger = multiprocessing.get_logger()

    while True:
        try:
            # TODO: Take care the queue doesnt get too large (in case of insert issues here)

            if task_queue.qsize() >= CONFIG["sqlite"]["min_rows_insert"]:
                # get readings and build sqlite filenames (maybe different fnames because of timestamp)
                readings = {}
                while not task_queue.empty():
                    reading = task_queue.get()
                    logger.debug(reading)
                    # build sqlite filename with timestamp
                    ts = datetime.datetime.strptime(reading["ts"], TS_FORMAT)
                    reading["ts_datetime"] = ts
                    fname = ts.strftime(CONFIG["sqlite"]["fname"])
                    logger.debug(fname)

                    # put into dict
                    if fname not in readings:
                        readings[fname] = []
                    readings[fname].append(reading)

                # insert readings with bulk insert statements
                for fname in readings:
                    create_new = False
                    if not os.path.exists(fname):
                        # create new db
                        create_new = True

                    # connect to db
                    conn = sqlite3.connect(fname)
                    c = conn.cursor()
                    logger.debug(f"connected to {fname}")

                    # build insert stmnt
                    sql = """INSERT INTO meter_data
                             (meter, l1, l2, l3, kwh, ts) 
                             VALUES (?,?,?,?,?,?);"""
                    params = [
                        (
                            reading["SERIAL"],
                            reading["L1"],
                            reading["L2"],
                            reading["L3"],
                            reading["A+"],
                            reading["ts_datetime"].strftime("%Y-%m-%d %H:%M:%S"),
                        )
                        for reading in readings[fname]
                    ]  # [(row 1 col 1, row 1 col 2, ...), (...), ... ]

                    try:
                        if create_new:
                            logger.debug("setting up new db...")
                            c.execute(SQLITE_CREATE)

                        # logger.debug(sql)
                        # logger.debug(params)
                        c.executemany(sql, params)
                        conn.commit()
                        logger.debug(
                            f"insert into {fname} was successful. "
                            f"Inserted {len(readings[fname])} readings."
                        )
                    except:
                        logger.exception(f"insert into {fname} failed")

                        # add to queue again
                        for reading in readings[fname]:
                            logger.debug(f"add {reading} to queue again")
                            task_queue.put(reading)

                    # close db
                    c.close()
                    conn.close()
                    logger.debug(f"closed connection to {fname}")

        except:
            logger.exception("Error in worker_sqlite")
        time.sleep(1)


def worker_logfile(task_queue):
    raise NotImplementedError


def run():
    multiprocessing.log_to_stderr(CONFIG["loglevel"])
    multiprocessing.get_logger().setLevel(CONFIG["loglevel"])

    # target functions for publishing services
    targets = {
        "mqtt": worker_publish_mqtt,
        "logfile": worker_logfile,
        "sqlite": worker_sqlite,
    }

    # prepare workers (create queues, link target functions)
    worker_args = []
    worker_targets = []
    for key in targets:
        if CONFIG[key]["enabled"]:
            worker_args.append(multiprocessing.Queue())
            worker_targets.append(targets[key])
    # now add worker_read_meter and give him a ref to all queues as argument
    worker_args.append(worker_args)
    worker_targets.append(worker_read_meter)

    # start workers
    processes = []
    for idx, _ in enumerate(worker_targets):
        p = multiprocessing.Process(
            target=worker_targets[idx], args=(worker_args[idx],)
        )
        p.daemon = True  # main process kills children before it will be terminated
        p.start()
        processes.append(p)

    # because we use deamon=True, the main process has to be kept alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    run()
