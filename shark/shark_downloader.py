# Lint as: python3
"""SHARK Downloader"""
# Requirements : Put shark_tank in SHARK directory
#   /SHARK
#     /gen_shark_tank
#       /tflite
#         /albert_lite_base
#         /...model_name...
#       /tf
#       /pytorch
#
#
#

import numpy as np
import os
from pathlib import Path
from shark.parser import shark_args
from web.index import resource_path
import shutil

GSUTIL_PATH = (
    "gsutil" if shutil.which("gsutil") is not None else resource_path("gsutil")
)

input_type_to_np_dtype = {
    "float32": np.float32,
    "float64": np.float64,
    "bool": np.bool_,
    "int32": np.int32,
    "int64": np.int64,
    "uint8": np.uint8,
    "int8": np.int8,
}


# Save the model in the home local so it needn't be fetched everytime in the CI.
home = str(Path.home())
alt_path = os.path.join(os.path.dirname(__file__), "../gen_shark_tank/")
custom_path = shark_args.local_tank_cache
if os.path.exists(alt_path):
    WORKDIR = alt_path
    print(
        f"Using {WORKDIR} as shark_tank directory. Delete this directory if you aren't working from locally generated shark_tank."
    )
if custom_path:
    if not os.path.exists(custom_path):
        os.mkdir(custom_path)

    WORKDIR = custom_path

    print(f"Using {WORKDIR} as local shark_tank cache directory.")
else:
    WORKDIR = os.path.join(home, ".local/shark_tank/")
    print(
        f"shark_tank local cache is located at {WORKDIR} . You may change this by setting the --local_tank_cache= flag"
    )

# Checks whether the directory and files exists.
def check_dir_exists(model_name, frontend="torch", dynamic=""):
    model_dir = os.path.join(WORKDIR, model_name)

    # Remove the _tf keyword from end.
    if frontend in ["tf", "tensorflow"]:
        model_name = model_name[:-3]
    elif frontend in ["tflite"]:
        model_name = model_name[:-7]
    elif frontend in ["torch", "pytorch"]:
        model_name = model_name[:-6]

    if os.path.isdir(model_dir):
        if (
            os.path.isfile(
                os.path.join(
                    model_dir,
                    model_name + dynamic + "_" + str(frontend) + ".mlir",
                )
            )
            and os.path.isfile(os.path.join(model_dir, "function_name.npy"))
            and os.path.isfile(os.path.join(model_dir, "inputs.npz"))
            and os.path.isfile(os.path.join(model_dir, "golden_out.npz"))
            and os.path.isfile(os.path.join(model_dir, "hash.npy"))
        ):
            print(
                f"""The models are present in the {WORKDIR}. If you want a fresh 
                download, consider deleting the directory."""
            )
            return True
    return False


# Downloads the torch model from gs://shark_tank dir.
def download_torch_model(
    model_name, dynamic=False, tank_url="gs://shark_tank/latest"
):
    model_name = model_name.replace("/", "_")
    dyn_str = "_dynamic" if dynamic else ""
    os.makedirs(WORKDIR, exist_ok=True)
    model_dir_name = model_name + "_torch"

    def gs_download_model():
        gs_command = (
            GSUTIL_PATH
            + ' -o "GSUtil:parallel_process_count=1" -m cp -r '
            + tank_url
            + "/"
            + model_dir_name
            + ' "'
            + WORKDIR
            + '"'
        )
        if os.system(gs_command) != 0:
            raise Exception("model not present in the tank. Contact Nod Admin")

    if not check_dir_exists(model_dir_name, frontend="torch", dynamic=dyn_str):
        gs_download_model()
    else:
        if not _internet_connected():
            print(
                "No internet connection. Using the model already present in the tank."
            )
        else:
            model_dir = os.path.join(WORKDIR, model_dir_name)
            local_hash = str(np.load(os.path.join(model_dir, "hash.npy")))
            gs_hash = (
                GSUTIL_PATH
                + ' -o "GSUtil:parallel_process_count=1" -m cp '
                + tank_url
                + "/"
                + model_dir_name
                + "/hash.npy"
                + " "
                + os.path.join(model_dir, "upstream_hash.npy")
            )
            if os.system(gs_hash) != 0:
                raise Exception("hash of the model not present in the tank.")
            upstream_hash = str(
                np.load(os.path.join(model_dir, "upstream_hash.npy"))
            )
            if local_hash != upstream_hash:
                if shark_args.update_tank == True:
                    gs_download_model()
                else:
                    print(
                        "Hash does not match upstream in gs://shark_tank/. If you are using SHARK Downloader with locally generated artifacts, this is working as intended."
                    )

    model_dir = os.path.join(WORKDIR, model_dir_name)
    with open(
        os.path.join(model_dir, model_name + dyn_str + "_torch.mlir"),
        mode="rb",
    ) as f:
        mlir_file = f.read()

    function_name = str(np.load(os.path.join(model_dir, "function_name.npy")))
    inputs = np.load(os.path.join(model_dir, "inputs.npz"))
    golden_out = np.load(os.path.join(model_dir, "golden_out.npz"))

    inputs_tuple = tuple([inputs[key] for key in inputs])
    golden_out_tuple = tuple([golden_out[key] for key in golden_out])
    return mlir_file, function_name, inputs_tuple, golden_out_tuple


# Downloads the tflite model from gs://shark_tank dir.
def download_tflite_model(
    model_name, dynamic=False, tank_url="gs://shark_tank/latest"
):
    dyn_str = "_dynamic" if dynamic else ""
    os.makedirs(WORKDIR, exist_ok=True)
    model_dir_name = model_name + "_tflite"

    def gs_download_model():
        gs_command = (
            GSUTIL_PATH
            + ' -o "GSUtil:parallel_process_count=1" -m cp -r '
            + tank_url
            + "/"
            + model_dir_name
            + ' "'
            + WORKDIR
            + '"'
        )
        if os.system(gs_command) != 0:
            raise Exception("model not present in the tank. Contact Nod Admin")

    if not check_dir_exists(
        model_dir_name, frontend="tflite", dynamic=dyn_str
    ):
        gs_download_model()
    else:
        if not _internet_connected():
            print(
                "No internet connection. Using the model already present in the tank."
            )
        else:
            model_dir = os.path.join(WORKDIR, model_dir_name)
            local_hash = str(np.load(os.path.join(model_dir, "hash.npy")))
            gs_hash = (
                GSUTIL_PATH
                + ' -o "GSUtil:parallel_process_count=1" cp '
                + tank_url
                + "/"
                + model_dir_name
                + "/hash.npy"
                + " "
                + os.path.join(model_dir, "upstream_hash.npy")
            )
            if os.system(gs_hash) != 0:
                raise Exception("hash of the model not present in the tank.")
            upstream_hash = str(
                np.load(os.path.join(model_dir, "upstream_hash.npy"))
            )
            if local_hash != upstream_hash:
                if shark_args.update_tank == True:
                    gs_download_model()
                else:
                    print(
                        "Hash does not match upstream in gs://shark_tank/. If you are using SHARK Downloader with locally generated artifacts, this is working as intended."
                    )

    model_dir = os.path.join(WORKDIR, model_dir_name)
    with open(
        os.path.join(model_dir, model_name + dyn_str + "_tflite.mlir"),
        mode="rb",
    ) as f:
        mlir_file = f.read()

    function_name = str(np.load(os.path.join(model_dir, "function_name.npy")))
    inputs = np.load(os.path.join(model_dir, "inputs.npz"))
    golden_out = np.load(os.path.join(model_dir, "golden_out.npz"))

    inputs_tuple = tuple([inputs[key] for key in inputs])
    golden_out_tuple = tuple([golden_out[key] for key in golden_out])
    return mlir_file, function_name, inputs_tuple, golden_out_tuple


def download_tf_model(
    model_name, tuned=None, tank_url="gs://shark_tank/latest"
):
    model_name = model_name.replace("/", "_")
    os.makedirs(WORKDIR, exist_ok=True)
    model_dir_name = model_name + "_tf"

    def gs_download_model():
        gs_command = (
            GSUTIL_PATH
            + ' -o "GSUtil:parallel_process_count=1" -m cp -r '
            + tank_url
            + "/"
            + model_dir_name
            + ' "'
            + WORKDIR
            + '"'
        )
        if os.system(gs_command) != 0:
            raise Exception("model not present in the tank. Contact Nod Admin")

    if not check_dir_exists(model_dir_name, frontend="tf"):
        gs_download_model()
    else:
        if not _internet_connected():
            print(
                "No internet connection. Using the model already present in the tank."
            )
        else:
            model_dir = os.path.join(WORKDIR, model_dir_name)
            local_hash = str(np.load(os.path.join(model_dir, "hash.npy")))
            gs_hash = (
                GSUTIL_PATH
                + ' -o "GSUtil:parallel_process_count=1" cp '
                + tank_url
                + "/"
                + model_dir_name
                + "/hash.npy"
                + " "
                + os.path.join(model_dir, "upstream_hash.npy")
            )
            if os.system(gs_hash) != 0:
                raise Exception("hash of the model not present in the tank.")
            upstream_hash = str(
                np.load(os.path.join(model_dir, "upstream_hash.npy"))
            )
            if local_hash != upstream_hash:
                if shark_args.update_tank == True:
                    gs_download_model()
                else:
                    print(
                        "Hash does not match upstream in gs://shark_tank/. If you are using SHARK Downloader with locally generated artifacts, this is working as intended."
                    )

    model_dir = os.path.join(WORKDIR, model_dir_name)
    suffix = "_tf.mlir" if tuned is None else "_tf_" + tuned + ".mlir"
    filename = os.path.join(model_dir, model_name + suffix)
    if not os.path.isfile(filename):
        filename = os.path.join(model_dir, model_name + "_tf.mlir")

    with open(filename, mode="rb") as f:
        mlir_file = f.read()

    function_name = str(np.load(os.path.join(model_dir, "function_name.npy")))
    inputs = np.load(os.path.join(model_dir, "inputs.npz"))
    golden_out = np.load(os.path.join(model_dir, "golden_out.npz"))

    inputs_tuple = tuple([inputs[key] for key in inputs])
    golden_out_tuple = tuple([golden_out[key] for key in golden_out])
    return mlir_file, function_name, inputs_tuple, golden_out_tuple


def _internet_connected():
    import requests as req

    try:
        req.get("http://1.1.1.1")
        return True
    except:
        return False
