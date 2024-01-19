# -*- coding: utf-8 -*-
"""
Functions to get FOD from DWI data:
    - run_processing_fod
"""
import os

from useful import execute_command


def run_processing_fod(in_dwi, brain_mask):
    """
    Get response function estimation and estimate Fiber
    Orientation Distributions (FOD) using MRTrix command
    """
    info = {}
    dir_name = os.path.dirname(in_dwi)

    # DWI response
    wm = os.path.join(dir_name, "response_wm.txt")
    gm = os.path.join(dir_name, "response_gm.txt")
    csf = os.path.join(dir_name, "response_csf.txt")
    voxels = os.path.join(dir_name, "response_voxels.mif")
    cmd = [
        "dwi2response",
        "dhollander",
        in_dwi,
        wm,
        gm,
        csf,
        "-voxels",
        voxels,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch dwi2response (exit code {result})"
        return 0, msg, info

    # FOD
    wm_fod = os.path.join(dir_name, "wmfod.mif")
    gm_fod = os.path.join(dir_name, "gmfod.mif")
    csf_fod = os.path.join(dir_name, "csffod.mif")
    cmd = [
        "dwi2fod",
        "msmt_csd",
        in_dwi,
        "-mask",
        brain_mask,
        wm,
        wm_fod,
        gm,
        gm_fod,
        csf,
        csf_fod,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch FOD (exit code {result})"
        return 0, msg, info

    # Normalise
    wm_fod_norm = os.path.join(dir_name, "wmfod_norm.mif")
    gm_fod_norm = os.path.join(dir_name, "gmfod_norm.mif")
    csf_fod_norm = os.path.join(dir_name, "csffod_norm.mif")
    cmd = [
        "mtnormalise",
        wm_fod,
        wm_fod_norm,
        gm_fod,
        gm_fod_norm,
        csf_fod,
        csf_fod_norm,
        "-mask",
        brain_mask,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch normalise (exit code {result})"
        return 0, msg, info

    # Extract peaks
    peaks = os.path.join(dir_name, "peaks.mif")
    cmd = ["sh2peaks", wm_fod_norm, peaks]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch sh2peaks (exit code {result})"
        return 0, msg, info
    info = {"peaks": peaks}
    msg = "FOD estimation done"
    return 1, msg, info