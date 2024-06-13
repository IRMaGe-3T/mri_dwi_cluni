# -*- coding: utf-8 -*-
"""
Functions for preprocessing DWI data:
    - get_dwifslpreproc_command
    - run_preproc_dwi
    - run_preproc_t1

"""

import logging
import os
import shutil

from useful import check_file_ext, convert_mif_to_nifti, execute_command

EXT = {"NIFTI_GZ": "nii.gz", "NIFTI": "nii"}


def get_dwifslpreproc_command(
    in_dwi, dwi_out, pe_dir, readout_time, b0_pair=None, rpe=None, shell=False
):
    """
    Get dwifslpreproc command.
    """
    command = ["dwifslpreproc", in_dwi, dwi_out]

    if not rpe:
        command += [
            "-rpe_none",
            "-pe_dir",
            pe_dir,
            "-readout_time",
            readout_time,
        ]
    elif rpe == "pair":
        command += [
            "-rpe_pair",
            "-se_epi",
            b0_pair,
            "-pe_dir",
            pe_dir,
            "-readout_time",
            readout_time,
        ]
    elif rpe == "all":
        command += [
            "-rpe_all",
            "-pe_dir",
            pe_dir,
            "-readout_time",
            readout_time,
        ]
    if shell is True:
        command += ["-eddy_options", "--slm=linear --data_is_shelled"]
    else:
        command += ["-eddy_options", "--slm=linear "]
    return command


def run_preproc_dwi(
    in_dwi, pe_dir, readout_time, rpe=None, shell=True, in_pepolar=None
):
    """
    Run preproc for whole brain diffusion using MRtrix command
    """
    info = {}
    mylog = logging.getLogger("custom_logger")
    mylog.info("Launch preprocessing DWI")
    # Get files name
    dir_name = os.path.dirname(in_dwi)
    valid_bool, in_ext, file_name = check_file_ext(in_dwi, {"MIF": "mif"})

    # Denoise
    dwi_denoise = os.path.join(dir_name, file_name + "_denoise.mif")
    cmd = ["dwidenoise", in_dwi, dwi_denoise]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch mrdegibbs (exit code {result})"
        return 0, msg, info

    # DeGibbs / Unringing
    dwi_degibbs = dwi_denoise.replace("_denoise.mif", "_denoise_degibbs.mif")
    cmd = ["mrdegibbs", dwi_denoise, dwi_degibbs]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch mrdegibbs (exit code {result})"
        return 0, msg, info

    # Create b0 pair for motion distortion correction
    if in_pepolar:
        # Average b0 pepolar if needed
        cmd = ["mrinfo", in_pepolar, "-ndim"]
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not get info for {in_pepolar}"
            return 0, msg, info
        ndim = sdtoutl.decode("utf-8").replace("\n", "").split(" ")
        in_pepolar_mean = in_pepolar.replace(".mif", "_mean.mif")
        if ndim == "4":
            cmd = ["mrmath", in_pepolar, "mean", in_pepolar_mean, "-axis", "3"]
            result, stderrl, sdtoutl = execute_command(cmd)
            if result != 0:
                msg = f"Can not lunch copy (exit code {result})"
                return 0, msg, info
        else:
            shutil.copy(in_pepolar, in_pepolar_mean)
        # Extract b0 from dwi and average data
        in_dwi_b0 = in_dwi.replace(".mif", "_bzero.mif")
        cmd = ["dwiextract", in_dwi, in_dwi_b0, "-bzero"]
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not lunch dwiextract (exit code {result})"
            return 0, msg, info
        in_dwi_b0_mean = in_dwi_b0.replace(".mif", "_mean.mif")
        cmd = ["mrmath", in_dwi_b0, "mean", in_dwi_b0_mean, "-axis", "3"]
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not lunch mrmath (exit code {result})"
            return 0, msg, info
        # Concatenate both b0 mean
        b0_pair = os.path.join(dir_name, "b0_pair.mif")
        cmd = ["mrcat", in_dwi_b0_mean, in_pepolar_mean, b0_pair]
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not lunch mrcat (exit code {result})"
            return 0, msg, info

    # Motion distortion correction
    if rpe == "all":
        # In this case issue with dwifslpreproc
        # use directly corrected image for in_dwi
        dwi_out = in_dwi
        mylog.info("Motion distorsion correction not done")
    else:
        # fslpreproc (topup and Eddy)
        dwi_out = dwi_degibbs.replace(".mif", "_fslpreproc.mif")
        if in_pepolar:
            cmd = get_dwifslpreproc_command(
                dwi_degibbs, dwi_out, pe_dir, readout_time, b0_pair, rpe, shell
            )
        else:
            cmd = get_dwifslpreproc_command(
                dwi_degibbs,
                dwi_out,
                pe_dir,
                readout_time,
                b0_pair=None,
                rpe=rpe,
                shell=shell,
            )
        result, stderrl, sdtoutl = execute_command(cmd)
        if result != 0:
            msg = f"Can not lunch dwifslpreproc (exit code {result})"
            return 0, msg, info

    # Bias correction
    dwi_unbias = os.path.join(dir_name, dwi_out.replace(".mif", "_unbias.mif"))
    cmd = ["dwibiascorrect", "ants", dwi_out, dwi_unbias]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch bias correction (exit code {result})"
        return 0, msg

    # Brain mask
    dwi_mask = os.path.join(dir_name, "dwi_brain_mask.mif")
    cmd = ["dwi2mask", dwi_unbias, dwi_mask]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = "Can not lunch mask (exit code {result})"
        return 0, msg

    info = {"dwi_preproc": dwi_unbias, "brain_mask": dwi_mask}
    msg = "Preprocessing DWI done"
    mylog.info(msg)
    return 1, msg, info


def run_preproc_t1(in_t1, in_dwi):
    """
    Coregister T1w to DWI
    """
    info = {}
    out_directory = os.path.dirname(in_t1)
    mylog = logging.getLogger("custom_logger")
    mylog.info("Launch preprocessing T1w")
    # Extract b0 from dwi and average data
    in_dwi_b0 = in_dwi.replace(".mif", "_bzero.mif")
    cmd = ["dwiextract", in_dwi, in_dwi_b0, "-bzero"]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch dwiextract (exit code {result})"
        return 0, msg, info
    in_dwi_b0_mean = in_dwi_b0.replace(".mif", "_mean.mif")
    cmd = ["mrmath", in_dwi_b0, "mean", in_dwi_b0_mean, "-axis", "3"]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch mrmath (exit code {result})"
        return 0, msg, info
    result, msg, in_dwi_b0_mean_nii = convert_mif_to_nifti(
        in_dwi_b0_mean, out_directory, diff=False
    )
    # Creating tissue boundaries
    tissue_type = in_t1.replace(".nii.gz", "_5tt.nii.gz")
    cmd = ["5ttgen", "fsl", in_t1, tissue_type]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch 5ttgen (exit code {result})"
        return 0, msg, info
    grey_matter = tissue_type.replace(".nii.gz", "_gm.nii.gz")
    cmd = ["fslroi", tissue_type, grey_matter, "0", "1"]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch fslroi (exit code {result})"
        return 0, msg, info
    # Coregistration with DWI
    transfo_mat = os.path.join(out_directory, "diff2struct_fsl.mat")
    cmd = [
        "flirt",
        "-in",
        in_dwi_b0_mean_nii,
        "-ref",
        grey_matter,
        "-interp",
        "nearestneighbour",
        "-dof",
        "6",
        "-omat",
        transfo_mat,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch flirt (exit code {result})"
        return 0, msg, info

    diff2struct = os.path.join(out_directory, "diff2struct_mrtrix.txt")
    cmd = [
        "transformconvert",
        transfo_mat,
        in_dwi_b0_mean_nii,
        tissue_type,
        "flirt_import",
        diff2struct,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch transformconvert (exit code {result})"
        return 0, msg, info
    in_t1_coreg = in_t1.replace(".nii.gz", "_coreg_dwi.mif")
    cmd = [
        "mrtransform",
        in_t1,
        "-linear",
        diff2struct,
        "-inverse",
        in_t1_coreg,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = "Can not lunch mrtransform (exit code {result})"
        return 0, msg, info
    tissue_type_coreg = tissue_type.replace(".nii.gz", "_coreg_dwi.mif")
    cmd = [
        "mrtransform",
        tissue_type,
        "-linear",
        diff2struct,
        "-inverse",
        tissue_type_coreg,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = "Can not lunch mrtransform (exit code {result})"
        return 0, msg, info

    # Create seed
    seed_boundary = os.path.join(out_directory, "gmwmSeed_coreg_dwi.nii.gz")
    cmd = ["5tt2gmwmi", tissue_type_coreg, seed_boundary]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch 5tt2gmwmi (exit code {result})"
        return 0, msg, info
    info = {"in_t1_coreg": in_t1_coreg}
    msg = "Preprocessing T1 done"
    mylog.info(msg)
    return 1, msg, info
