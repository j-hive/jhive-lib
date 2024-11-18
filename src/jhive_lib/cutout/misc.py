"""Miscellaneous utility functions.
"""

# Imports


from datetime import datetime
from pathlib import Path

import numpy as np
from astropy.io import fits


# Constants


DEFAULT_CATALOG_VERSION = "dja-v7.2"
"""Default cataloging version, corresponding to `{F}-{I}-fix_phot_apcorr.fits
photometric catalog FITS table files.
"""


# Functions


## Path


def get_alternate_filter_names(filter: str) -> list[str]:
    """Get a list of alternate filter names for a filter.

    Attempts to match any of the following filter name formats.
    1. f200w-clear
    2. f200w-clearp
    3. clear-f200w
    4. clearp-f200w
    5. f200w
    6. 200

    Parameters
    ----------
    filter : str
        Unresolved filter name.

    Returns
    -------
    list[str]
        List of possible alternate filter names.
    """

    return [
        filter,
        f"{filter}-clear",
        f"{filter}-clearp",
        f"clear-{filter}",
        f"clearp-{filter}",
        f"f{filter}m",
        f"f{filter}w",
        f"f{filter}n",
        filter.split("-")[0],
        filter.split("-")[-1],
        filter.split("-"),
    ]


def get_alternate_end_tags() -> list[str]:
    """Get a list of alternate end tags for a FIL file.

    The following files are FIL (field, image version, filter) files, and have
    an end tag before their respective labels.
    1. Exposure Map (`exp`)
    2. Science (`sci`)
    3. Weights Map (`wht`)

    An end tag is `drc` or `drz`.

    Returns
    -------
    list[str]
        List of known end tags.
    """
    return ["drc", "drz"]


## Setting


def get_priority_setting(
    name: str, cli_settings: dict, file_settings: dict
) -> bool | int | Path | list[str] | list[int] | None:
    """Get a setting's value from CLI call or YAML file, in preference of the
    CLI setting value, and None if not found.

    Parameters
    ----------
    name : str
        Name of setting.
    cli_settings : dict
        Settings passed from CLI call.
    file_settings : dict
        Settings read from YAML file.

    Returns
    -------
    bool | int | Path | list[str] | list[int] | None
        Resolved prioritized setting, if found.
    """
    # Return setting from CLI call if set
    if cli_settings[name] is not None:
        return cli_settings[name]

    # Return setting from YAML file if set
    elif name in file_settings:
        return file_settings[name]

    # Return setting from YAML file if set with space separators
    elif name.replace("_", " ") in file_settings:
        return file_settings[name.replace("_", " ")]

    # Return None if unset


def get_priority_sub_setting(
    sub: str, name: str, cli_settings: dict, file_settings: dict
) -> bool | None:
    """Get the priority value for a stage or remake setting from values passed
    from a terminal call and a settings file.

    Parameters
    ----------
    sub : str
        Sub-setting, one of 'stage' or 'remake'.
    name : str
        Name of stage or product.
    cli_settings : dict
        Settings passed from CLI call.
    file_settings : dict
        Settings passed from YAML file.

    Returns
    -------
    bool | None
        Priority stage or remake setting, if found in either CLI call or YAML
        file.
    """
    # Get key prefix from sub-setting name
    if sub == "stages":
        prefix = "skip"
    else:
        prefix = "remake"

    # Return opposite of flag from CLI call if set
    if cli_settings[f"{prefix}_{name}"] is not None:
        return not cli_settings[f"{prefix}_{name}"]

    # Return flag from YAML file if set
    elif sub in file_settings:
        if name in file_settings[sub]:
            return True
        else:
            return False

    # Return None if unset


def validate_batch_settings(
    process_count: int | None,
    process_id: int | None,
    first_object: int | None,
    last_object: int | None,
):
    """Validate batch mode settings for a MorphFITS program run.

    Parameters
    ----------
    process_count : int | None
        Number of processes in batch, must be greater than 0.
    process_id : int | None
        ID of process in batch, must be greater than 0 and less than total
        number of processes.
    first_object : int | None
        ID of first object in batch range, must be greater than 0 and less than
        last (possible) object.
    last_object : int | None
        ID of last object in batch range, must be greater than first (possible)
        object and less than last possible object.
    """
    # Terminate if invalid number of processes
    if process_count is not None:
        assert process_count > 0, f"Invalid # processes {process_count}."

    # Terminate if invalid process ID
    if process_id is not None:
        assert process_id >= 0, f"Invalid process ID {process_id}."
        if process_count is not None:
            assert (
                process_id < process_count
            ), f"Invalid process ID {process_id} for # processes {process_count}."

    # Terminate if invalid first object
    if first_object is not None:
        assert first_object > 0, f"Invalid first object ID {first_object}."

    # Terminate if invalid last object
    if last_object is not None:
        assert last_object > 0, f"Invalid last object ID {last_object}."

    # Terminate if invalid object range
    if (first_object is not None) and (last_object is not None):
        assert (
            first_object <= last_object
        ), f"Invalid object range {first_object} to {last_object}."


def get_unique_batch_limits(
    process_id: int, n_process: int, n_items: int
) -> tuple[int, int]:
    """Produce the minimum and maximum items for a process given the number of
    items to process, the number of processes, and the process id. The min and
    max indices will be unique based on only these three parameters.

    Parameters
    ----------
    process_id : int
        The process id (ranging from 0 to n_process-1)
    n_process : int
        The number of processes
    n_items : int
        The number of items to process

    Returns
    -------
    tuple[int, int]
        The min and max index to process, of the form [min, max)

    """

    # Checking if valid process
    if process_id >= n_process:
        raise ValueError(
            f"process_id ({process_id}) can not be greater than {n_process - 1}"
        )

    # Setting number of items in this process
    n_items_process = n_items // n_process
    if process_id < (n_items % n_process):
        n_items_process += 1

    # Setting Start, Stop Indices
    start_index = process_id * (n_items // n_process) + min(
        process_id, n_items % n_process
    )
    stop_index = start_index + n_items_process

    return start_index, stop_index


## Data


def get_str_from_datetime(date_time: datetime) -> str:
    """Get a string representation of a datetime, in the format
    'YYYYMMDDTHHMMSS'.

    Parameters
    ----------
    date_time : datetime
        Datetime to convert to str.

    Returns
    -------
    str
        String representation of datetime.
    """
    return date_time.strftime("%Y%m%dT%H%M%S")


def get_str_from_process_id(process_id: int) -> str:
    """Get a string representation of a process ID, in the format '01', with one
    leading zero if the number is one digit.

    Parameters
    ----------
    process_id : int
        Number to convert to string.

    Returns
    -------
    str
        Process ID as string with leading zero.
    """
    return str(process_id).rjust(2, "0")


def get_unique(items: list) -> list:
    """Get the unique elements in a list of elements, as a sorted list.

    Parameters
    ----------
    items : list
        List of elements to be sorted.

    Returns
    -------
    list
        Sorted list of unique elements.
    """
    not_nan_items = []

    # Remove any NaNs from list
    for item in items:
        if isinstance(item, float) and np.isnan(item):
            continue
        else:
            not_nan_items.append(item)

    # Return unique items in list, sorted
    return sorted(set(not_nan_items))


def get_normalized(
    data: np.ndarray, scale: int | float = 1.0, dtype: type = float
) -> np.ndarray:
    """Get a numpy array normalized from its min to max, as a numpy array from 0
    to scale.

    Parameters
    ----------
    data : np.ndarray
        Array to be normalized.
    scale : float, optional
        Scale to normalize to, by default 1.0 so that the final range is 0 to 1.
    dtype : type, optional
        Type of data of normalized array, by default float.

    Returns
    -------
    np.ndarray
        Array normalized from 0 to 1.
    """
    return np.array((data - data.min()) / data.ptp() * scale, dtype=int)
