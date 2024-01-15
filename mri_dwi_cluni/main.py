# -*- coding: utf-8 -*-
"""
Launch DWI preprocessing and TractSeg processing

mrtrix: https://mrtrix.readthedocs.io
TracSeg: https://github.com/MIC-DKFZ/TractSeg
"""

import json
import os
import shutil
import sys

from bids_conversion import convert_to_bids
from main_white_matter_bundle import run_white_matter_bundle
from PyQt5 import QtWidgets
from PyQt5.QtCore import QDir
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox
from PyQt5.uic import loadUi


class App(QMainWindow):
    """
    Main windows Qt
    """

    def __init__(self):
        super(App, self).__init__()

        # Get ui
        self.dir_code_path = os.path.realpath(os.path.dirname(__file__))
        ui_file = os.path.join(self.dir_code_path, "interface.ui")
        loadUi(ui_file, self)

        # Connect sigans and slots
        self.pushButton_browser.clicked.connect(self.browse_directory)
        self.pushButton_run.clicked.connect(self.launch_processing)

        # Init variable
        self.dicom_directory = ""
        self.reset_progress_bar()

    def reset_progress_bar(self):
        """Reset progress bar"""
        self.progressBar_run.setRange(0, 100)
        self.progressBar_run.setValue(0)
        self.progressBar_run.setStyleSheet(
            "QProgressBar::chunk { background-color: blue; }"
        )

    def browse_directory(self):
        """Browse DICOM directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select a directory", QDir.homePath()
        )
        if directory:
            self.dicom_directory = directory
            self.textEdit_output_browser.setText(self.dicom_directory)
            self.pushButton_run.setEnabled(True)
            self.reset_progress_bar()

    def launch_processing(self):
        """Launch processing"""
        if self.dicom_directory:
            self.reset_progress_bar()
            try:
                dicom_directory = self.dicom_directory
                # Configuration
                config_file = os.path.join(
                    os.path.dirname(self.dir_code_path),
                    "config",
                    "config.json",
                )
                with open(config_file, encoding="utf-8") as my_json:
                    data = json.load(my_json)
                    bids_config_file = data["BidsConfigFile"]
                    out_directory = data["OutputDirectory"]
                    working_directory = data["WorkingDirectory"]
                self.progressBar_run.setValue(5)

                # BIDS conversion
                print("\n----------CONVERSION----------")
                result, msg, info = convert_to_bids(
                    dicom_directory, bids_config_file, out_directory
                )
                if result == 0:
                    self.error(msg)
                    raise Exception(msg)
                patient_name = info["sub_name"]
                sess_name = info["sess_name"]
                self.progressBar_run.setValue(15)

                # Create analysis directories
                analysis_directory = os.path.join(
                    out_directory,
                    "derivatives",
                    "sub-" + patient_name,
                    "ses-" + sess_name,
                )
                preproc_directory = os.path.join(
                    analysis_directory, "preprocessing"
                )

                if os.path.exists(preproc_directory):
                    # Check if subject / session already processed
                    if len(os.listdir(preproc_directory)) > 1:
                        msg = (
                            "Data already processed for this subject/session,"
                            "would you like to repeat the analysis"
                        )
                        response = self.show_confirmation_box(msg)
                        if response == QMessageBox.Cancel:
                            print("Processing cancelled")
                            return
                        else:
                            # Remove old data
                            shutil.rmtree(analysis_directory)

                if not os.path.exists(analysis_directory):
                    os.makedirs(analysis_directory)
                if not os.path.exists(preproc_directory):
                    os.mkdir(preproc_directory)

                self.progressBar_run.setValue(10)

                # Change working directory
                # (mrtriw will create temp directory in it)
                os.chdir(working_directory)

                # Launch processing
                result, msg = run_white_matter_bundle(
                    out_directory, patient_name, sess_name
                )
                if result == 0:
                    self.error(msg)
                    raise Exception(msg)

                # Clean tmp folder
                shutil.rmtree(os.path.join(out_directory, "tmp_dcm2bids"))
                self.progressBar_run.setValue(100)
                self.progressBar_run.setStyleSheet(
                    "QProgressBar::chunk { background-color: green; }"
                )
                print("\n Processing done")
            except Exception as e:
                self.error(e)

        else:
            msg = "No dicom directory selected"
            self.progressBar_run.setStyleSheet(
                "QProgressBar::chunk { background-color: red; }"
            )
            self.show_error_message_box(msg)

    def error(self, message):
        """Error function"""
        print(f"Error during processing: {message}")
        self.progressBar_run.setStyleSheet(
            "QProgressBar::chunk { background-color: red; }"
        )
        self.show_error_message_box(str(message))

    def show_error_message_box(self, error_message):
        """Box with error message"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText("Error during processing:")
        msg_box.setDetailedText(error_message)
        msg_box.exec_()

    def show_confirmation_box(self, message):
        """Box to confirm an action"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Confirmation")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        return msg_box.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainwindow = App()
    widget = QtWidgets.QStackedWidget()
    widget.addWidget(mainwindow)
    widget.setFixedWidth(400)
    widget.setFixedHeight(300)
    widget.show()
    sys.exit(app.exec_())
