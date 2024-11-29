"""Settings ingestion and creation utility functions.
"""

# Imports


import shutil
import tempfile
import itertools
import logging
from pathlib import Path
from datetime import datetime
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    StringConstraints,
    NonNegativeInt,
    PositiveInt,
    PositiveFloat,
)

from . import logs, misc, science


# Classes


class FICL(BaseModel):
    """Model representing a single observation science frame.

    Corresponds to the field, image version, catalog version, and filter of the
    frame.

    Attributes
    ----------
    field : str
        Field of observation, as a lowercase string.
    image_version : str
        Image processing version, as a lowercase string.
    catalog_version : str
        Cataloging version, as a lowercase string.
    filter : str
        Filter name, as a lowercase string.
    pixscale : tuple[float, float]
        Pixel scale along x and y axes, respectively, in arcseconds per pixel,
        as a tuple of positive floats.
    objects : list[int]
        Integer IDs of galaxies or cluster targets as listed in this FICL's
        corresponding photometric catalog, as a list of positive integers, by
        default empty.
    failed : list[int]
        Integer IDs of objects which failed to run, as a list of positive
        integers, by default empty.
    """

    field: Annotated[str, StringConstraints(to_lower=True)]
    image_version: Annotated[str, StringConstraints(to_lower=True)]
    catalog_version: Annotated[str, StringConstraints(to_lower=True)]
    filter: Annotated[str, StringConstraints(to_lower=True)]
    pixscale: tuple[PositiveFloat, PositiveFloat]
    objects: list[PositiveInt]
    failed: list[PositiveInt] = []

    def __init__(self, **kwargs):
        temp_logger.info("Loading FICL.")

        # Validate required files
        assert kwargs["catalog"].is_file(), "photometric catalog missing"
        assert kwargs["science"].is_file(), "science frame missing"

        # Get values for each primitive setting
        field = kwargs.get("field")
        image_version = kwargs.get("image_version")
        catalog_version = kwargs.get("catalog_version")
        filter = kwargs.get("filter")
        objects = kwargs.get("objects")
        process_id = kwargs.get("process_id")
        process_count = kwargs.get("process_count")
        first_object = kwargs.get("first_object")
        last_object = kwargs.get("last_object")

        # Get values for each data setting
        pixscale = science.get_pixscale(path=kwargs["science"])
        ficl_objects = misc.get_objects(
            path=kwargs["catalog"],
            process_id=process_id,
            process_count=process_count,
            objects=objects,
            first_object=first_object,
            last_object=last_object,
        )

        # Initialize dict to unpack
        settings = {
            "field": field,
            "image_version": image_version,
            "catalog_version": catalog_version,
            "filter": filter,
            "pixscale": pixscale,
            "objects": ficl_objects,
        }

        # Initialize instance
        super().__init__(**settings)

    def __str__(self) -> str:
        return "_".join(
            [self.field, self.image_version, self.catalog_version, self.filter]
        )

    def __eq__(self, other) -> bool:
        return (isinstance(other, FICL)) and (str(self) == str(other))

    def __dict__(self) -> dict[str, str | list[int] | tuple[float, float]]:
        return {
            "field": self.field,
            "image version": self.image_version,
            "catalog version": self.catalog_version,
            "filter": self.filter,
            "pixscale": misc.get_str_from_pixscale(self.pixscale),
            "objects": self.objects,
            "failed": self.failed,
        }

    def remove(self, objects: list[int]):
        """Remove objects from this FICL's configuration.

        Does nothing if an object is not in FICL's list.

        Parameters
        ----------
        objects : list[int]
            Integer IDs of objects to remove from FICL.
        """
        for object in objects:
            try:
                self.objects.remove(object)
                self.failed.append(object)
            except:
                continue


class StageSettings(BaseModel):
    """Stages to run, as flags.

    Attributes
    ----------
    setup : bool
        Setup program run, by default True.
    product : bool
        Make product files, by default True.
    main : bool
        Run main program, by default True.
    cleanup : bool
        Remove failed files, by default True.
    """

    setup: bool = True
    product: bool = True
    main: bool = True
    cleanup: bool = True

    def __init__(self, **kwargs):
        temp_logger.info("Loading stage settings.")

        # Get values for each setting
        setup = StageSettings.get("setup", **kwargs)
        product = StageSettings.get("product", **kwargs)
        main = StageSettings.get("main", **kwargs)
        cleanup = StageSettings.get("cleanup", **kwargs)

        # Initialize dict to unpack
        settings = {}

        # Add each configured setting
        if setup is not None:
            settings["setup"] = setup
        if product is not None:
            settings["product"] = product
        if main is not None:
            settings["main"] = main
        if cleanup is not None:
            settings["cleanup"] = cleanup

        # Initialize instance
        super().__init__(**settings)

    def __dict__(self) -> list[str]:
        # Add each active stage to list
        settings = []
        if self.setup:
            settings.append("setup")
        if self.product:
            settings.append("product")
        if self.main:
            settings.append("main")
        if self.cleanup:
            settings.append("cleanup")

        # Return list representation
        return settings

    def get(key: str, **kwargs) -> bool | None:
        """Get the value for a setting, preferring the value passed through the
        CLI over the YAML.

        Parameters
        ----------
        key : str
            Name of setting to get.

        Returns
        -------
        bool | None
            Stage setting, if found.
        """
        # Get stage setting from CLI
        if f"skip_{key}" in kwargs:
            return not kwargs[f"skip_{key}"]

        # Get stage setting from YAML
        if "stages" in kwargs:
            return key in kwargs["stages"]


class RemakeSettings(BaseModel):
    """Files to remake and overwrite, as flags.

    Attributes
    ----------
    products : bool
        Remake product files, by default False.
    main : bool
        Remake main files, by default False.
    """

    products: bool = False
    main: bool = False

    def __init__(self, **kwargs):
        temp_logger.info("Loading remake settings.")

        # Get values for each setting
        products = RemakeSettings.get("products", **kwargs)
        main = RemakeSettings.get("main", **kwargs)

        # Initialize dict to unpack
        settings = {}

        # Add each configured setting
        if products is not None:
            settings["products"] = products
        if main is not None:
            settings["main"] = main

        # Initialize instance
        super().__init__(**settings)

    def __dict__(self) -> list[str]:
        # Add each remake to list
        settings = []
        if self.products:
            settings.append("products")
        if self.main:
            settings.append("main")

        # Return list representation
        return settings

    def get(key: str, **kwargs) -> bool | None:
        """Get the value for a setting, preferring the value passed through the
        CLI over the YAML.

        Parameters
        ----------
        key : str
            Name of setting to get.

        Returns
        -------
        bool | None
            Remake setting, if found.
        """
        # Get remake setting from CLI
        if f"remake_{key}" in kwargs:
            return kwargs[f"remake_{key}"]

        # Get remake setting from YAML
        if ("remake" in kwargs) and (key in kwargs["remake"]):
            return True


class RuntimeSettings(BaseModel):
    """Local and program configurations.

    Attributes
    ----------
    date_time : datetime
        Date time at launch.
    process_id : int
        ID of process in batch, as a non-negative integer, by default 0.
    process_count : int
        Number of processes in batch, as a positive integer, by default 1.
    log_level : str
        Level at which to log, one of standard Python levels, by default info.
    progress_bar : bool
        Display progress as a loading bar, by default False.
    stages : StageSettings
        Stages to run.
    remake : RemakeSettings
        Files to remake and overwrite.
    ficls : list[FICL]
        FICLs over which to run program, by default empty.
    """

    date_time: datetime
    process_id: NonNegativeInt = 0
    process_count: PositiveInt = 1
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    progress_bar: bool = False
    stages: StageSettings
    remake: RemakeSettings
    ficls: list[FICL] = []

    def __init__(self, **kwargs):
        temp_logger.info("Loading runtime settings.")

        # Get values for each primitive setting
        date_time = datetime.now()
        process_id = kwargs.get("process_id")
        process_count = kwargs.get("process_count")
        first_object = kwargs.get("first_object")
        last_object = kwargs.get("last_object")
        log_level = kwargs.get("log_level")
        progress_bar = kwargs.get("progress_bar")

        # Get values for each sub-setting
        stages = StageSettings(**kwargs)
        remake = RemakeSettings(**kwargs)

        # Initialize dict to unpack
        settings = {"date_time": date_time, "stages": stages, "remake": remake}

        # Add each configured setting
        if process_id is not None:
            settings["process_id"] = process_id
        if process_count is not None:
            settings["process_count"] = process_count
        if log_level is not None:
            settings["log_level"] = log_level
        if progress_bar is not None:
            settings["progress_bar"] = progress_bar

        # Initialize instance
        super().__init__(**settings)

        # Validate batch settings
        assert (
            self.process_id < process_count
        ), f"process ID {self.process_id} > # processes {self.process_count}"

        # Get values for each model
        # NOTE Child classes of this class MUST pass these kwargs to the init
        # function of its super class, for each FICL
        # Catalog path for FICL, with kw: "F_I_C_L_catalog"
        # Science path for FICL, with kw: "F_I_C_L_science"
        ficls = []
        fields = kwargs.get("fields")
        imvers = kwargs.get("image_versions")
        catvers = kwargs.get("catalog_versions")
        filters = kwargs.get("filters")
        objects = kwargs.get("objects")

        # Iterate over each permutation of FICL settings
        for ficl_permutation in itertools.product(fields, imvers, catvers, filters):
            # Skip permutation if missing catalog or science path
            ficl_str = "_".join(ficl_permutation)
            if (f"{ficl_str}_catalog" not in kwargs) or (
                f"{ficl_str}_science" not in kwargs
            ):
                continue

            # Initialize dict to unpack
            ficl_attributes = {
                "field": ficl_permutation[0],
                "image_version": ficl_permutation[1],
                "catalog_version": ficl_permutation[2],
                "filter": ficl_permutation[3],
                "objects": objects,
                "process_id": self.process_id,
                "process_count": self.process_count,
                "first_object": first_object,
                "last_object": last_object,
                "catalog": kwargs[f"{ficl_str}_catalog"],
                "science": kwargs[f"{ficl_str}_science"],
            }

            # Add FICL if valid
            try:
                ficls.append(FICL(**ficl_attributes))
                temp_logger.info(f"Loaded FICL {ficls[-1]}.")
            except:
                continue

    def __dict__(self) -> dict[str, int | str | datetime | dict | list]:
        # Add primitive attributes to dict
        settings = {
            "started": self.date_time,
            "logging level": self.log_level,
            "progress bar": "on" if self.progress_bar else "off",
        }

        # Add batch mode parameters
        if self.process_count > 1:
            settings["batch mode"] = {
                "process ID": self.process_id,
                "# processes": self.process_count,
            }

        # Add stages as a list of stages ran
        if self.stages is not None:
            settings["stages"] = self.stages.__dict__

        # Add remake flags as a list of products remade
        if self.remake is not None:
            settings["remake"] = self.remake.__dict__

        # Add FICLs as a list of dicts
        settings["ficls"] = []
        for ficl in self.ficls:
            settings["ficls"].append(ficl.__dict__)

        # Return dict representation
        return settings

    def setup(self, paths: list[Path]):
        """Make missing directories.

        Parameters
        ----------
        paths : list[Path]
            Paths to required directories.
        """
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    def setup_logger(self, path: Path) -> logging.Logger:
        """Make missing loggers.

        Parameters
        ----------
        path : Path
            Path to logging file.

        Returns
        -------
        Logger
            Logging object.
        """
        return logs.setup(path=path, level=self.log_level)

    def cleanup(self, paths: list[tuple[Path, list[str]]]):
        """Remove failed directories.

        Parameters
        ----------
        paths : list[tuple[Path, list[str]]]
            Paths paired with required sub-paths, to be removed if any sub-path
            not found.
        """
        for path, required_sub_paths in paths:
            sub_paths = [sub_path.name for sub_path in path.iterdir()]

            for required_sub_path in required_sub_paths:
                if required_sub_path not in sub_paths:
                    shutil.rmtree(path, ignore_errors=True)
                    break

    def write(self, path: Path):
        """Record settings.

        Parameters
        ----------
        path : Path
            Path to which to write settings.
        """
        yaml.dump(self.__dict__, open(path, mode="a"), sort_keys=False)


class ScienceSettings(BaseModel):
    """Scientific algorithm configurations.

    Attributes
    ----------
    minimum : int
        Minimum square image dimensions, in pixels, as a positive integer, by
        default 32.
    scale : float
        Multiplier on initial radius to determine image size, as a positive
        float, by default 20.0.
    """

    minimum: PositiveInt = 32
    scale: PositiveFloat = 20.0

    def __init__(self, **kwargs):
        temp_logger.info("Loading science settings.")

        # Get values for each primitive setting
        minimum = ScienceSettings.get("minimum", **kwargs)
        scale = ScienceSettings.get("scale", **kwargs)

        # Initialize dict to unpack
        settings = {"minimum": minimum, "scale": scale}

        # Add each configured setting
        if minimum is not None:
            settings["minimum"] = minimum
        if scale is not None:
            settings["scale"] = scale

        # Initialize instance
        super().__init__(**settings)

    def __dict__(self) -> dict[str, int | float]:
        # Add primitive attributes to dict
        settings = {"minimum": self.minimum, "scale": self.scale}

        # Return dict representation
        return settings

    def get(key: str, **kwargs) -> bool | None:
        """Get the value for a setting, preferring the value passed through the
        CLI over the YAML.

        Parameters
        ----------
        key : str
            Name of setting to get.

        Returns
        -------
        bool | None
            Science setting, if found.
        """
        # Get science setting from CLI
        if key in kwargs:
            return kwargs[key]

        # Get science setting from YAML
        if ("science" in kwargs) and (key in kwargs["science"]):
            return kwargs["science"][key]

    def write(self, path: Path):
        """Record settings.

        Parameters
        ----------
        path : Path
            Path to which to write settings.
        """
        yaml.dump(self.__dict__, open(path, mode="a"), sort_keys=False)


# Functions


def get_settings(**kwargs) -> tuple[RuntimeSettings, ScienceSettings]:
    """Get settings objects from configurations passed through the CLI call
    and/or YAML configuration file.

    If a setting is configured via both CLI and YAML, the CLI setting is
    preferred.

    Returns
    -------
    tuple[RuntimeSettings, ScienceSettings]
        Settings for the operation and science of this program, respectively.
    """
    # Initialize dict to unpack with non-None CLI settings
    settings = {k: v for k, v in kwargs.items() if v is not None}

    # Merge dict with YAML settings, preferring CLI settings
    if "config" in kwargs:
        config_path = misc.get_path_object(kwargs.get("config"))
        if config_path.is_file():
            file_kwargs = yaml.safe_load(open(config_path, mode="r"))
            settings = file_kwargs | settings

    # Make temporary logger
    temp_file = tempfile.NamedTemporaryFile()
    logs.setup(path=temp_file.name)
    global temp_logger
    temp_logger = logging.getLogger("SETTINGS")

    # Get runtime and science settings
    runtime_settings = RuntimeSettings(**settings)
    science_settings = ScienceSettings(**settings)

    # Remove temporary logger
    temp_logger.handlers.clear()
    temp_file.close()

    # Return runtime and science settings
    return runtime_settings, science_settings
