# -*- coding: utf-8 -*-
"""
Main function to get white matter bunble using MRTRix and TractSeg:
-run_white_matter_bundle
"""
import glob
import json
import logging
import os
import shutil

from preprocessing import run_preproc_dwi, run_preproc_t1
from processing_fod import run_processing_fod
from processing_tractseg import run_tractseg
from useful import convert_mif_to_nifti, convert_nifti_to_mif, get_shell


def run_white_matter_bundle(out_directory, patient_name, sess_name):
    """
    Get all data and run preprocessing and processing
    """
    mylog = logging.getLogger("custom_logger")
    analysis_directory = os.path.join(
        out_directory, "derivatives", "sub-" + patient_name, "ses-" + sess_name
    )
    preproc_directory = os.path.join(analysis_directory, "preprocessing")
    # Get diffusion, fmap and T1w
    session_path = os.path.join(
        out_directory, "sub-" + patient_name, "ses-" + sess_name
    )
    all_sequences = glob.glob(os.path.join(session_path, "*", "*.nii.gz"))
    sequences_found = []

    all_sequences_dwi = [
        seq for seq in all_sequences if "dwi" in seq.split("/")[-1]
    ]
    if len(all_sequences_dwi) == 0:
        msg = (
            "Diffusion image not found, "
            "please use a DICOM directory with diffusion image"
        )
        return 0, msg
    if len(all_sequences_dwi) != 1:
        msg = (
            "Too many diffusion sequences in DICOM directoty, "
            "please select only one"
        )
        return 0, msg
    in_dwi_nifti = all_sequences_dwi[0]
    sequences_found.append("DWI")

    all_sequences_t1 = [
        seq for seq in all_sequences if "T1w" in seq.split("/")[-1]
    ]
    if len(all_sequences_t1) > 1:
        msg = (
            "Too many anat sequences in DICOM directoty, "
            "please select only one"
        )
        return 0, msg
    if len(all_sequences_t1) == 0:
        in_t1w_nifti = None
    else:
        in_t1w_nifti = all_sequences_t1[0]
        sequences_found.append("T1w")

    all_sequences_pepolar = [
        seq for seq in all_sequences if "epi" in seq.split("/")[-1]
    ]
    if len(all_sequences_pepolar) > 1:
        msg = (
            "Too many pepolar sequences in DICOM directory, "
            "please select only one"
        )
        return 0, msg
    if len(all_sequences_pepolar) == 0:
        in_pepolar_nifti = None
    else:
        in_pepolar_nifti = all_sequences_pepolar[0]
        sequences_found.append("pepolar")

    # Conversion into mif format (mrtrix format) and get info
    result, msg, in_dwi = convert_nifti_to_mif(
        in_dwi_nifti, preproc_directory, diff=True
    )
    if result == 0:
        return 0, msg

    in_dwi_json = in_dwi_nifti.replace("nii.gz", "json")
    with open(in_dwi_json, encoding="utf-8") as my_json:
        data = json.load(my_json)
        try:
            readout_time = str(data["TotalReadoutTime"])
        except Exception:
            # For Philips data
            readout_time = str(data["EstimatedTotalReadoutTime"])
        pe_dir = str(data["PhaseEncodingDirection"])

    result, msg, shell = get_shell(in_dwi)
    shell = [bval for bval in shell if bval != "0" and bval != ""]
    if len(shell) > 1:
        SHELL = True
    else:
        SHELL = False
    in_t1w = None
    if in_t1w_nifti:
        shutil.copy(in_t1w_nifti, preproc_directory)
        result, msg, in_t1w = convert_nifti_to_mif(
            in_t1w_nifti, preproc_directory, diff=False
        )
        if result == 0:
            return 0, msg

    in_pepolar = None
    if in_pepolar_nifti:
        result, msg, in_pepolar = convert_nifti_to_mif(
            in_pepolar_nifti, preproc_directory, diff=False
        )
        if result == 0:
            return 0, msg

    msg = (
        "\n Conversion done, "
        f"the following sequences have been found: {sequences_found}"
    )
    mylog.info(msg)

    mylog.info("\n----------Start PROCESSING----------")
    print("It will take time...")
    # Preprocessing
    if in_pepolar:
        RPE = "pair"
        result, msg, info = run_preproc_dwi(
            in_dwi,
            pe_dir,
            readout_time,
            rpe=RPE,
            shell=SHELL,
            in_pepolar=in_pepolar,
        )
    else:
        result, msg, info = run_preproc_dwi(
            in_dwi, pe_dir, readout_time, shell=SHELL
        )
    if result == 0:
        print("\nIssue during preprocessing")
        return 0, msg
    dwi_preproc = info["dwi_preproc"]
    brain_mask = info["brain_mask"]

    # DWI response and FOD
    result, msg, info = run_processing_fod(dwi_preproc, brain_mask)
    if result == 0:
        print("\nIssue during FOD estimation")
        return 0, msg
    peaks = info["peaks"]
    result, msg, peaks_nii = convert_mif_to_nifti(
        peaks, analysis_directory, diff=False
    )

    # T1 coregistration
    if in_t1w:
        result, msg, info = run_preproc_t1(
            in_t1w.replace("mif", "nii.gz"), dwi_preproc
        )
        in_t1_coreg = info["in_t1_coreg"]
        shutil.copy(in_t1_coreg, analysis_directory)
    # Copy DWI preproc into TractSeg folder
    # to have all the useful data in one folder
    shutil.copy(dwi_preproc, analysis_directory)

    # Tractseg
    mylog.info("\n----------Start TractSeg----------")
    result, msg = run_tractseg(peaks_nii)
    if result == 0:
        print("\nIssue during TracSeg")
        return 0, msg
    msg = "\nProcessing done"
    mylog.info(msg)
    return 1, msg
