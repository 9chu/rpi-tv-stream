# -*- coding: utf-8 -*-
import logging
import subprocess
from fastapi import FastAPI
from pydantic import BaseModel


# 按需调整
CODE_MAPPING = {
    "left":   "necx:0x402c0e",
    "right":  "necx:0x402c1a",
    "up":     "necx:0x402c03",
    "down":   "necx:0x402c02",
    "back":   "necx:0x402c18",
    "browse": "necx:0x402c48",
    "ok":     "necx:0x402c07",
    "1": "necx:0x402c09",
    "2": "necx:0x402c1d",
    "3": "necx:0x402c1f",
    "4": "necx:0x402c0d",
    "5": "necx:0x402c19",
    "6": "necx:0x402c1b",
    "7": "necx:0x402c11",
    "8": "necx:0x402c15",
    "9": "necx:0x402c17",
    "0": "necx:0x402c12"
}


class KeyArgs(BaseModel):
    key: str


app = FastAPI()
logger = logging.getLogger("uvicorn.error")


@app.post("/key")
async def key(args: KeyArgs):
    scancode = CODE_MAPPING.get(args.key, None)
    if scancode is not None:
        cmd = ["ir-ctl", "-d", "/dev/lirc0", "--scancode", scancode]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
        logger.info(f"call {' '.join(cmd)}, retcode: {proc.returncode}, stdout: {proc.stdout.decode('utf-8')}, " + \
                    f"stderr: {proc.stderr.decode('utf-8')}")
        if proc.returncode == 0:
            return { "code": 0 }
        return { "code": -2 }
    else:
        return { "code": -1 }


@app.post("/restart")
async def restart():
    cmd = ["pm2", "restart", "tv-live-stream"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.info(f"call {' '.join(cmd)}, retcode: {proc.returncode}, stdout: {proc.stdout.decode('utf-8')}, " + \
                f"stderr: {proc.stderr.decode('utf-8')}")
    if proc.returncode == 0:
        return { "code": 0 }
    return { "code": -2 }
