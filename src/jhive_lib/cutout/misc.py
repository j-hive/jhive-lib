"""TODO
"""

# Imports


from pathlib import Path

import numpy as np
from astropy.io import fits


# Functions


## Settings


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
