# -*- coding: utf-8 -*-
"""
Functions to get FOD from DWI data:
    - run_processing_fod
"""
import logging
import os

from useful import execute_command, get_shell


def run_processing_fod(in_dwi, brain_mask, partial_brain=False):
    """
    Get response function estimation and estimate Fiber
    Orientation Distributions (FOD) using MRTrix command
    """
    info = {}
    dir_name = os.path.dirname(in_dwi)
    mylog = logging.getLogger("custom_logger")
    mylog.info("Launch processing FOD")

    # Different processing if multi-shell or single shell
    result, msg, shell = get_shell(in_dwi)
    shell = [bval for bval in shell if float(bval) < 5 and bval != ""]
    if len(shell) > 1:
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
            msg = f"Can not launch dwi2response (exit code {result})"
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
            msg = f"Can not launch FOD (exit code {result})"
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
            msg = f"Can not launch normalise (exit code {result})"
            return 0, msg, info
        wm_fod = wm_fod_norm
    else:
        # DWI response
        wm = os.path.join(dir_name, "response_wm.txt")
        cmd = ["dwi2response", "tournier", in_dwi, wm]
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not launch dwi2response (exit code {result})"
            return 0, msg, info
        # FOD
        wm_fod = os.path.join(dir_name, "wmfod.mif")
        cmd = ["dwi2fod", "csd", in_dwi, "-mask", brain_mask, wm, wm_fod]
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not launch FOD (exit code {result})"
            return 0, msg, info

    # Extract peaks
    peaks = os.path.join(dir_name, "peaks.mif")
    cmd = ["sh2peaks", wm_fod, peaks]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not launch sh2peaks (exit code {result})"
        return 0, msg, info
    info = {"peaks": peaks}
    msg = "FOD estimation done"

     # Tckgen
    if partial_brain:
        msg += " + tckgen done"
        tracto = os.path.join(dir_name, "tracto_5000000.tck")
        cmd = ["tckgen", wm_fod, "-seed_dynamic", wm_fod, "-mask", brain_mask,
        tracto, "-select", "5000000", "-minlength", "20"]
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not launch tckgen (exit code {result})"
            return 0, msg, info
    mylog.info(msg)
    return 1, msg, info
